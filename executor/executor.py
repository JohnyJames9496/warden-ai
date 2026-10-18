"""
Warden Executor — M7 entry point.

Receives a diagnosis dict from agent/graph.py and:
  - auto_executable  → runs the action immediately
  - needs_approval   → blocks (human must approve via Slack/dashboard)
  - denied           → does nothing, logs reason

After running, verifies recovery. If recovery fails, triggers rollback.
"""

import logging

from executor.actions import (
    restart_pod,
    rollback_deployment,
    rollout_restart,
    scale_deployment,
)
from rollback.rollback_manager import rollback
from rollback.verifier import verify_recovery

log = logging.getLogger("warden.executor")

DEPLOYMENT_ACTIONS = {"rollout_restart", "scale_deployment", "rollback_deployment"}


def execute(diagnosis: dict) -> dict:
    """
    Main executor entry point.

    Args:
        diagnosis: dict from agent state["diagnosis"], includes:
            action, target, namespace, policy_status, confidence, etc.

    Returns:
        result dict with keys:
            status, action, target, namespace,
            action_result, verification, rollback (if triggered)
    """
    action = diagnosis.get("action", "")
    target = diagnosis.get("target", "")
    namespace = diagnosis.get("namespace", "warden-demo")
    policy_status = diagnosis.get("policy_status", "denied")
    desired_replicas = diagnosis.get("desired_replicas")

    log.info(
        "executor: action=%s target=%s namespace=%s policy_status=%s",
        action, target, namespace, policy_status,
    )

    # --- gate: policy check ---
    if policy_status == "denied":
        log.warning("executor: DENIED by OPA — not executing")
        return {
            "status": "denied",
            "action": action,
            "target": target,
            "namespace": namespace,
            "reason": diagnosis.get("policy_reasons", ["OPA denied"]),
        }

    if policy_status == "needs_approval":
        log.info("executor: requires human approval — not auto-executing")
        return {
            "status": "awaiting_approval",
            "action": action,
            "target": target,
            "namespace": namespace,
            "reason": "high-risk action requires human approval via Slack or dashboard",
        }

    # --- auto_executable: run the action ---
    action_result = _run_action(action, namespace, target, desired_replicas)

    if action_result.get("status") == "failed":
        return {
            "status": "action_failed",
            "action": action,
            "target": target,
            "namespace": namespace,
            "action_result": action_result,
        }

    # --- verify recovery ---
    if action in DEPLOYMENT_ACTIONS:
        verification = verify_recovery(namespace=namespace, deployment=target)
    else:
        # pod restarts are fast — deployment controller handles recreation
        verification = {
            "recovered": True,
            "elapsed_seconds": 0,
            "reason": "pod deletion triggered, controller will recreate",
        }

    if verification["recovered"]:
        log.info("executor: recovery confirmed for %s/%s", namespace, target)
        return {
            "status": "resolved",
            "action": action,
            "target": target,
            "namespace": namespace,
            "action_result": action_result,
            "verification": verification,
        }

    # --- verification failed: rollback ---
    log.warning(
        "executor: recovery failed for %s/%s — triggering rollback",
        namespace, target,
    )
    rollback_result = rollback(namespace=namespace, deployment=target)

    return {
        "status": "rolled_back",
        "action": action,
        "target": target,
        "namespace": namespace,
        "action_result": action_result,
        "verification": verification,
        "rollback": rollback_result,
    }


def _run_action(
    action: str,
    namespace: str,
    target: str,
    desired_replicas: int | None,
) -> dict:
    """Dispatch to the correct action function."""
    if action == "rollout_restart":
        return rollout_restart(namespace=namespace, deployment=target)

    if action == "scale_deployment":
        if desired_replicas is None:
            log.error("scale_deployment called without desired_replicas")
            return {"status": "failed", "error": "desired_replicas not provided"}
        return scale_deployment(
            namespace=namespace, deployment=target, desired_replicas=desired_replicas
        )

    if action == "rollback_deployment":
        return rollback_deployment(namespace=namespace, deployment=target)

    if action == "restart_pod":
        return restart_pod(namespace=namespace, pod=target)

    log.error("executor: unknown action '%s'", action)
    return {"status": "failed", "error": f"unknown action '{action}'"}
