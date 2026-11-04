import os
import logging

import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from graph import build_graph

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("warden.agent")

api = FastAPI(title="Warden Agent")

DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:8000")

# Build once at startup — not on every request
_graph = build_graph()


class DiagnoseRequest(BaseModel):
    name: str
    namespace: str = "warden-demo"
    severity: str = "critical"
    description: str = ""
    pod: str = ""
    fingerprint: str = ""


def _post_to_dashboard(event: str, req: DiagnoseRequest, diagnosis: dict | None = None) -> None:
    """Fire-and-forget POST to dashboard /internal/ingest. Errors are logged, never raised."""
    payload: dict = {
        "event": event,
        "fingerprint": req.fingerprint,
        "alertname": req.name,
        "service": req.namespace.replace("warden-", "") or req.name,
        "namespace": req.namespace,
        "severity": req.severity,
        "description": req.description,
    }
    if diagnosis is not None:
        payload["diagnosis"] = diagnosis

    try:
        resp = httpx.post(
            f"{DASHBOARD_URL}/internal/ingest",
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        log.info("dashboard_ingest: event=%s status=%d", event, resp.status_code)
    except Exception as exc:
        log.warning("dashboard_ingest failed (non-fatal): %s", exc)


@api.get("/healthz")
def healthz():
    return {"status": "ok"}


@api.post("/diagnose")
def diagnose(req: DiagnoseRequest):
    log.info(
        "diagnose request: fingerprint=%s name=%s namespace=%s",
        req.fingerprint, req.name, req.namespace,
    )

    alert = {
        "name": req.name,
        "namespace": req.namespace,
        "severity": req.severity,
        "description": req.description,
        "pod": req.pod,
    }

    result = _graph.invoke({
        "alert": alert,
        "k8s_context": "",
        "runbook_context": "",
        "incident_history": "",
        "diagnosis": {},
        "execution_result": {},
    })

    diagnosis = result.get("diagnosis", {})

    _post_to_dashboard("diagnosis_complete", req, diagnosis=diagnosis)

    return {"fingerprint": req.fingerprint, "diagnosis": diagnosis}
