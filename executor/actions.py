"""
Remediation actions for the Warden executor.

Every function here mutates cluster state. Only called after:
  1. OPA has allowed the action (policy_status != "denied")
  2. Human approval received (if policy_status == "needs_approval")
"""

import logging
from datetime import datetime, timezone

from kubernetes.client.rest import ApiException

from executor.k8s_client import get_apps_v1, get_core_v1

log = logging.getLogger("warden.executor.actions")


def rollout_restart(namespace: str, deployment: str) -> dict:
    """
    Trigger a rolling restart of a deployment.
    Equivalent to: kubectl rollout restart deployment/<name> -n <namespace>
    Patches the pod template annotation with a timestamp — forces K8s
    to cycle all pods one by one without downtime.
    """
    apps_v1 = get_apps_v1()
    now = datetime.now(timezone.utc).isoformat()

    patch = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "kubectl.kubernetes.io/restartedAt": now
                    }
                }
            }
        }
    }

    try:
        apps_v1.patch_namespaced_deployment(
            name=deployment, namespace=namespace, body=patch,
        )
        log.info("rollout_restart: patched %s/%s", namespace, deployment)
        return {
            "action": "rollout_restart",
            "target": deployment,
            "namespace": namespace,
            "status": "triggered",
        }
    except ApiException as e:
        log.error("rollout_restart failed: %s", e)
        return {
            "action": "rollout_restart",
            "target": deployment,
            "namespace": namespace,
            "status": "failed",
            "error": str(e),
        }


def scale_deployment(namespace: str, deployment: str, desired_replicas: int) -> dict:
    """
    Scale a deployment to the desired replica count.
    Equivalent to: kubectl scale deployment/<name> --replicas=N -n <namespace>
    """
    apps_v1 = get_apps_v1()

    try:
        apps_v1.patch_namespaced_deployment_scale(
            name=deployment,
            namespace=namespace,
            body={"spec": {"replicas": desired_replicas}},
        )
        log.info("scale_deployment: %s/%s -> %d replicas", namespace, deployment, desired_replicas)
        return {
            "action": "scale_deployment",
            "target": deployment,
            "namespace": namespace,
            "replicas": desired_replicas,
            "status": "triggered",
        }
    except ApiException as e:
        log.error("scale_deployment failed: %s", e)
        return {
            "action": "scale_deployment",
            "target": deployment,
            "namespace": namespace,
            "status": "failed",
            "error": str(e),
        }


def rollback_deployment(namespace: str, deployment: str) -> dict:
    """
    Roll back a deployment to its previous revision.
    Equivalent to: kubectl rollout undo deployment/<name> -n <namespace>
    Uses K8s native rollout history — no custom snapshot needed.
    """
    apps_v1 = get_apps_v1()

    try:
        deploy = apps_v1.read_namespaced_deployment(
            name=deployment, namespace=namespace
        )
        annotations = deploy.metadata.annotations or {}
        current_revision = int(
            annotations.get("deployment.kubernetes.io/revision", "1")
        )
        target_revision = max(1, current_revision - 1)

        apps_v1.patch_namespaced_deployment(
            name=deployment,
            namespace=namespace,
            body={
                "metadata": {
                    "annotations": {
                        "deployment.kubernetes.io/revision": str(target_revision)
                    }
                }
            },
        )
        log.info(
            "rollback_deployment: %s/%s -> revision %d",
            namespace, deployment, target_revision,
        )
        return {
            "action": "rollback_deployment",
            "target": deployment,
            "namespace": namespace,
            "revision": target_revision,
            "status": "triggered",
        }
    except ApiException as e:
        log.error("rollback_deployment failed: %s", e)
        return {
            "action": "rollback_deployment",
            "target": deployment,
            "namespace": namespace,
            "status": "failed",
            "error": str(e),
        }


def restart_pod(namespace: str, pod: str) -> dict:
    """
    Delete a single pod so the Deployment controller recreates it.
    Only for a single misbehaving pod — use rollout_restart for
    deployment-wide issues.
    """
    core_v1 = get_core_v1()

    try:
        core_v1.delete_namespaced_pod(name=pod, namespace=namespace)
        log.info("restart_pod: deleted %s/%s", namespace, pod)
        return {
            "action": "restart_pod",
            "target": pod,
            "namespace": namespace,
            "status": "triggered",
        }
    except ApiException as e:
        log.error("restart_pod failed: %s", e)
        return {
            "action": "restart_pod",
            "target": pod,
            "namespace": namespace,
            "status": "failed",
            "error": str(e),
        }
