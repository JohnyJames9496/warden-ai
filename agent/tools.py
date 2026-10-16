"""Read-only evidence-gathering tools for the diagnosis agent.
Each function only performs GET-style reads — no tool here can mutate
cluster state. That boundary is intentional: diagnosis must be safe to
run before any policy engine (M5) or approval gate (M6) exists.

Requires, on EC2, in a separate background shell:
  kubectl port-forward -n monitoring svc/prometheus-operated 9090:9090 &
  kubectl port-forward -n monitoring svc/tempo 3200:3200 &
"""
from dotenv import load_dotenv
load_dotenv()
import requests
from kubernetes import client, config

PROMETHEUS_URL = "http://localhost:9090"
TEMPO_URL = "http://localhost:3200"


def _get_core_v1():
    """Lazy-init k8s client — safe to call in-cluster or with kubeconfig."""
    try:
        config.load_incluster_config()
    except Exception:
        config.load_kube_config()
    return client.CoreV1Api()


def query_prometheus(promql: str, minutes: int = 30) -> str:
    """Run a PromQL instant query and summarize it as text for the LLM."""
    try:
        resp = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": promql},
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json()["data"]["result"]
        if not result:
            return f"Prometheus query '{promql}' returned no data."
        lines = [f"Prometheus query: {promql}"]
        for series in result[:5]:
            labels = series["metric"]
            value = series["value"][1]
            lines.append(f"  {labels} = {value}")
        return "\n".join(lines)
    except Exception as exc:
        return f"Prometheus query failed: {type(exc).__name__}: {exc}"


def get_k8s_context(namespace: str, target: str) -> str:
    """Pod status, restart counts, and recent logs for a deployment or pod."""
    try:
        core_v1 = _get_core_v1()
        pods = core_v1.list_namespaced_pod(
            namespace=namespace, label_selector=f"app={target}"
        ).items
        if not pods:
            return f"No pods found in {namespace} matching app={target}."

        lines = [f"K8s context for {namespace}/{target} ({len(pods)} pod(s)):"]
        for pod in pods:
            name = pod.metadata.name
            phase = pod.status.phase
            restarts = sum(cs.restart_count for cs in (pod.status.container_statuses or []))
            reason = ""
            if pod.status.container_statuses:
                last_state = pod.status.container_statuses[0].last_state
                if last_state and last_state.terminated:
                    reason = f", last termination reason: {last_state.terminated.reason}"
            lines.append(f"  {name}: phase={phase}, restarts={restarts}{reason}")

        first_pod = pods[0].metadata.name
        try:
            logs = core_v1.read_namespaced_pod_log(
                name=first_pod, namespace=namespace, tail_lines=20
            )
            lines.append(f"\nRecent logs ({first_pod}):\n{logs.strip()[-1000:]}")
        except Exception as log_exc:
            lines.append(f"\nCould not fetch logs: {log_exc}")

        return "\n".join(lines)
    except Exception as exc:
        return f"K8s context query failed: {type(exc).__name__}: {exc}"


def query_tempo(service_name: str, limit: int = 5) -> str:
    """Recent traces for a service, via Tempo's TraceQL search API."""
    try:
        resp = requests.get(
            f"{TEMPO_URL}/api/search",
            params={"q": f'{{resource.service.name="{service_name}"}}', "limit": limit},
            timeout=10,
        )
        resp.raise_for_status()
        traces = resp.json().get("traces", [])
        if not traces:
            return f"No recent traces found for service {service_name}."
        lines = [f"Recent traces for {service_name}:"]
        for t in traces:
            lines.append(
                f"  traceID={t.get('traceID')} rootService={t.get('rootServiceName')} "
                f"duration={t.get('durationMs')}ms"
            )
        return "\n".join(lines)
    except Exception as exc:
        return f"Tempo query failed: {type(exc).__name__}: {exc}"


def gather_evidence(namespace: str, target: str, promql: str) -> str:
    """Combine all three sources into one evidence string for the diagnosis prompt."""
    sections = [
        query_prometheus(promql),
        get_k8s_context(namespace, target),
        query_tempo(target),
    ]
    return "\n\n".join(sections)
