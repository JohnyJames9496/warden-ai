"""
Kubernetes client initialisation for the Warden executor.
Tries in-cluster config first (running inside Kind pod),
falls back to kubeconfig for local dev.
"""

import logging
from kubernetes import client, config

log = logging.getLogger("warden.executor")


def _load_config() -> None:
    try:
        config.load_incluster_config()
        log.debug("k8s: loaded in-cluster config")
    except config.ConfigException:
        config.load_kube_config()
        log.debug("k8s: loaded kubeconfig")


def get_apps_v1() -> client.AppsV1Api:
    _load_config()
    return client.AppsV1Api()


def get_core_v1() -> client.CoreV1Api:
    _load_config()
    return client.CoreV1Api()
