"""
Rollback manager for the Warden rollback module.

Uses kubectl rollout undo via K8s Apps API — no custom snapshot needed.
Design decision documented in docs/adr/0003-rollback-design.md.
"""

import logging

from kubernetes.client.rest import ApiException

from executor.k8s_client import get_apps_v1

log = logging.getLogger("warden.rollback.manager")


def rollback(namespace: str, deployment: str) -> dict:
    apps_v1 = get_apps_v1()

    try:
        deploy = apps_v1.read_namespaced_deployment(
            name=deployment, namespace=namespace
        )
        annotations = deploy.metadata.annotations or {}
        current_revision = int(
            annotations.get("deployment.kubernetes.io/revision", "1")
        )

        if current_revision <= 1:
            log.warning(
                "rollback: %s/%s at revision %d — no previous revision",
                namespace, deployment, current_revision,
            )
            return {
                "status": "skipped",
                "reason": f"already at revision {current_revision}, no previous revision available",
                "namespace": namespace,
                "deployment": deployment,
            }

        apps_v1.patch_namespaced_deployment(
            name=deployment,
            namespace=namespace,
            body={
                "metadata": {
                    "annotations": {
                        "deployment.kubernetes.io/revision": str(current_revision - 1)
                    }
                }
            },
        )
        log.info(
            "rollback: triggered %s/%s (revision %d -> %d)",
            namespace, deployment, current_revision, current_revision - 1,
        )
        return {
            "status": "triggered",
            "namespace": namespace,
            "deployment": deployment,
            "from_revision": current_revision,
            "to_revision": current_revision - 1,
        }

    except ApiException as e:
        log.error("rollback failed for %s/%s: %s", namespace, deployment, e)
        return {
            "status": "failed",
            "namespace": namespace,
            "deployment": deployment,
            "error": str(e),
        }
