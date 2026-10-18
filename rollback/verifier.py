"""
Post-action verifier for the Warden rollback module.

Polls the cluster until all pods in the deployment are Running and Ready,
or until timeout expires — in which case rollback is triggered.
"""

import logging
import time

from kubernetes.client.rest import ApiException

from executor.k8s_client import get_apps_v1

log = logging.getLogger("warden.rollback.verifier")

POLL_INTERVAL = 5
DEFAULT_TIMEOUT = 120


def verify_recovery(namespace: str, deployment: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    apps_v1 = get_apps_v1()
    start = time.time()

    log.info("verifier: watching %s/%s (timeout=%ds)", namespace, deployment, timeout)

    while True:
        elapsed = time.time() - start

        if elapsed > timeout:
            log.warning(
                "verifier: timeout after %.0fs — %s/%s not recovered",
                elapsed, namespace, deployment,
            )
            return {
                "recovered": False,
                "elapsed_seconds": int(elapsed),
                "reason": f"timeout after {int(elapsed)}s — pods did not become ready",
            }

        try:
            deploy = apps_v1.read_namespaced_deployment(
                name=deployment, namespace=namespace
            )
            desired = deploy.spec.replicas or 1
            ready = deploy.status.ready_replicas or 0
            available = deploy.status.available_replicas or 0

            log.debug(
                "verifier: %s/%s desired=%d ready=%d available=%d",
                namespace, deployment, desired, ready, available,
            )

            if ready >= desired and available >= desired:
                log.info(
                    "verifier: %s/%s recovered in %.0fs",
                    namespace, deployment, elapsed,
                )
                return {
                    "recovered": True,
                    "elapsed_seconds": int(elapsed),
                    "reason": f"all {desired} replicas ready after {int(elapsed)}s",
                }

        except ApiException as e:
            log.warning("verifier: k8s API error (will retry): %s", e)

        time.sleep(POLL_INTERVAL)
