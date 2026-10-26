"""
Graph: START -> retrieval -> gather_context -> diagnose -> policy_check -> execute -> END
"""
import os
from dotenv import load_dotenv
load_dotenv()
import sys
import logging
from pathlib import Path
from typing import TypedDict

# Ensure repo root is accessible for policies.client and executor
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from policies.client import check_policy, PolicyUnavailableError
from executor.executor import execute

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field
from kubernetes import client, config

from rag.retriever import get_runbook, get_similar_incidents

log = logging.getLogger("warden.agent")


# ---------------------------------------------------------------------------
# Structured output schema
# ---------------------------------------------------------------------------

class DiagnosisResult(BaseModel):
    action: str = Field(description="Remediation action to take (e.g. rollout_restart, scale_deployment, restart_pod, rollback_deployment, no_action, escalate)")
    target: str = Field(description="Kubernetes resource name to act on")
    namespace: str = Field(description="Namespace of the target resource")
    reason: str = Field(description="Short explanation of the diagnosis")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    current_replicas: int | None = Field(default=None, description="Current replicas if scaling")
    desired_replicas: int | None = Field(default=None, description="Desired replicas if scaling")


# ---------------------------------------------------------------------------
# Agent state
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    alert: dict
    k8s_context: str
    runbook_context: str
    incident_history: str
    diagnosis: dict
    execution_result: dict  # ← new: executor output


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def retrieval_node(state: AgentState) -> AgentState:
    """Retrieve relevant runbook and similar past incidents from ChromaDB."""
    alert = state["alert"]
    alert_name = alert.get("name", "")
    description = alert.get("description", "")

    runbook = get_runbook(alert_name)
    history = get_similar_incidents(description)

    if runbook:
        log.info("runbook retrieved for: %s", alert_name)
    else:
        log.info("no runbook found for: %s", alert_name)

    state["runbook_context"] = runbook
    state["incident_history"] = history
    return state


def gather_context(state: AgentState) -> AgentState:
    """Pull live pod and event data from Kubernetes for the alerted namespace."""
    alert = state["alert"]
    namespace = alert.get("namespace", "warden-demo")

    lines = []
    try:
        try:
            config.load_incluster_config()
        except Exception:
            config.load_kube_config()

        v1 = client.CoreV1Api()

        pods = v1.list_namespaced_pod(namespace=namespace)
        lines.append(f"=== Pods in {namespace} ===")
        for p in pods.items:
            cs = p.status.container_statuses or []
            for c in cs:
                if c.state.running:
                    state_info = "Running"
                elif c.state.waiting:
                    state_info = f"Waiting:{c.state.waiting.reason or 'Unknown'}"
                elif c.state.terminated:
                    state_info = f"Terminated:{c.state.terminated.reason or 'Unknown'}"
                else:
                    state_info = "Unknown"
                lines.append(
                    f"  {p.metadata.name} | {c.name} | {state_info} | restarts={c.restart_count}"
                )

        events = v1.list_namespaced_event(namespace=namespace)
        warnings = [e for e in events.items if e.type == "Warning"]
        warnings.sort(key=lambda e: e.last_timestamp or e.event_time or "", reverse=True)
        lines.append(f"\n=== Recent Warning Events in {namespace} ===")
        for e in warnings[:10]:
            lines.append(f"  {e.reason}: {e.message} (obj={e.involved_object.name})")

    except Exception as exc:
        log.warning("k8s context gather failed: %s", exc)
        lines.append(f"[k8s unavailable: {exc}]")

    state["k8s_context"] = "\n".join(lines)
    return state


def diagnose(state: AgentState) -> AgentState:
    """Call Groq LLM with alert + k8s context + RAG context -> DiagnosisResult."""
    alert = state["alert"]
    k8s_ctx = state.get("k8s_context", "")
    runbook = state.get("runbook_context", "")
    history = state.get("incident_history", "")

    system_prompt = """You are Warden, an autonomous SRE agent for Kubernetes incident remediation.

Analyse the alert and live cluster context, then return a structured remediation decision.

## Action vocabulary
- rollout_restart   -> deployment-wide issue (OOMKilled, config error, image pull failure across pods)
- scale_deployment  -> capacity or traffic-related issue
- restart_pod       -> single isolated pod misbehaving; rest of deployment is healthy
- no_action         -> transient blip or already self-healed
- escalate          -> unknown cause or automated action risk too high

## Pod scope rule (CRITICAL)
If multiple pods show the same failure, ALWAYS choose rollout_restart over restart_pod.
restart_pod is valid ONLY for a single misbehaving pod in an otherwise healthy deployment.

## OOMKilled rule (CRITICAL)
OOMKilled is ALWAYS a deployment-wide resource issue. NEVER choose restart_pod for OOMKilled.
Always choose rollout_restart with the deployment name as target for OOMKilled alerts.
A single OOMKilled pod will OOM again immediately after restart — rollout_restart is the correct action.

## Target field
- rollout_restart / scale_deployment -> set target to the DEPLOYMENT name
- restart_pod -> set target to the POD name

## Confidence
1.0 = certain. Below 0.4 prefer escalate."""

    human_parts = [
        f"## Alert\n{alert}",
        f"## Live Kubernetes Context\n{k8s_ctx}",
    ]
    if runbook:
        human_parts.append(f"## Runbook\n{runbook}")
    if history:
        human_parts.append(f"## Similar Past Incidents\n{history}")

    human_prompt = "\n\n".join(human_parts)

    llm = ChatGroq(
        model="openai/gpt-oss-120b",
        api_key=os.environ.get("GROQ_API_KEY", ""),
        temperature=0,
    ).with_structured_output(DiagnosisResult)

    result: DiagnosisResult = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt),
    ])
    log.info("diagnosis: %s", result.model_dump())
    state["diagnosis"] = result.model_dump()
    return state


# ---------------------------------------------------------------------------
# Policy check
# ---------------------------------------------------------------------------

ACTION_MAPPING = {
    "rollout_restart": "restart",
    "restart_pod": "restart",
    "restart": "restart",
    "scale_deployment": "scale",
    "scale": "scale",
    "rollback_deployment": "rollback",
    "rollback": "rollback",
}


def policy_check(state: AgentState) -> AgentState:
    """Evaluates the proposed remediation action against OPA guardrails."""
    diag = state.get("diagnosis", {})
    if not diag:
        return state

    raw_action = diag.get("action", "")
    opa_action = ACTION_MAPPING.get(raw_action, raw_action)
    namespace = diag.get("namespace", "warden-demo")
    target = diag.get("target", "")

    extra = {}
    if diag.get("current_replicas") is not None:
        extra["current_replicas"] = diag["current_replicas"]
    if diag.get("desired_replicas") is not None:
        extra["desired_replicas"] = diag["desired_replicas"]

    if opa_action == "scale" and "current_replicas" not in extra:
        try:
            apps_v1 = client.AppsV1Api()
            scale_obj = apps_v1.read_namespaced_deployment_scale(name=target, namespace=namespace)
            extra["current_replicas"] = scale_obj.status.replicas or scale_obj.spec.replicas or 1
            diag["current_replicas"] = extra["current_replicas"]
        except Exception as exc:
            log.warning("Could not fetch current_replicas from k8s for %s/%s: %s", namespace, target, exc)

    try:
        decision = check_policy(action=opa_action, namespace=namespace, target=target, **extra)
        allowed = decision.get("allow", False)
        risk = decision.get("risk", "high")
        reasons = decision.get("reasons", [])

        if not allowed:
            policy_status = "denied"
            log.warning("OPA policy DENIED action '%s': %s", opa_action, reasons)
        elif risk == "high":
            policy_status = "needs_approval"
            log.info("OPA policy ALLOWED (risk=high, needs approval) for action '%s'", opa_action)
        else:
            policy_status = "auto_executable"
            log.info("OPA policy ALLOWED (risk=low, auto-executable) for action '%s'", opa_action)

    except Exception as exc:
        log.error("OPA policy check failed (failing closed to needs_approval): %s", exc)
        allowed = False
        risk = "high"
        policy_status = "needs_approval"
        reasons = [f"OPA policy check unavailable (fail-closed): {type(exc).__name__}: {exc}"]

    diag["policy_status"] = policy_status
    diag["allowed"] = allowed
    diag["risk"] = risk
    diag["policy_reasons"] = reasons
    state["diagnosis"] = diag
    return state


# ---------------------------------------------------------------------------
# Executor node
# ---------------------------------------------------------------------------

def execute_node(state: AgentState) -> AgentState:
    """
    Runs the approved remediation action against the cluster.
    - auto_executable  → runs immediately
    - needs_approval   → skips execution, waits for human via Slack/dashboard
    - denied           → skips execution
    """
    diag = state.get("diagnosis", {})
    if not diag:
        state["execution_result"] = {"status": "skipped", "reason": "no diagnosis"}
        return state

    # Skip no_action and escalate — nothing to execute
    action = diag.get("action", "")
    if action in ("no_action", "escalate"):
        log.info("execute_node: action=%s — skipping execution", action)
        state["execution_result"] = {"status": "skipped", "reason": f"action={action}"}
        return state

    result = execute(diag)
    log.info("execution_result: %s", result)
    state["execution_result"] = result
    return state


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

def build_graph():
    g = StateGraph(AgentState)
    g.add_node("retrieval", retrieval_node)
    g.add_node("gather_context", gather_context)
    g.add_node("diagnose", diagnose)
    g.add_node("policy_check", policy_check)
    g.add_node("execute", execute_node)
    g.add_edge(START, "retrieval")
    g.add_edge("retrieval", "gather_context")
    g.add_edge("gather_context", "diagnose")
    g.add_edge("diagnose", "policy_check")
    g.add_edge("policy_check", "execute")
    g.add_edge("execute", END)
    return g.compile()
