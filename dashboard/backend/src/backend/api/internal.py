"""
Internal ingest endpoint — called by detector/receiver and agent/main.py.
Never expose this route to the internet. No auth needed; runs inside the cluster.

Two events:
  alert_fired        → create Incident + Detection rows
  diagnosis_complete → update Incident status, add AgentDecision + PolicyCheck,
                       and ApprovalRequest if policy_status == needs_approval
"""

from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.models.agent_decision import AgentDecision
from backend.models.approval_request import ApprovalRequest
from backend.models.audit_log_entry import AuditLogEntry
from backend.models.detection import Detection
from backend.models.enums import (
    ActionType,
    ApprovalStatus,
    IncidentSeverity,
    IncidentStatus,
    PolicyVerdict,
)
from backend.models.incident import Incident
from backend.models.policy_check import PolicyCheck

router = APIRouter(prefix="/internal", tags=["internal"])

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class DiagnosisPayload(BaseModel):
    action: str
    target: str
    namespace: str
    reason: str
    confidence: float
    policy_status: str
    allowed: bool
    risk: str
    policy_reasons: list[str] = []
    current_replicas: int | None = None
    desired_replicas: int | None = None


class IngestRequest(BaseModel):
    event: Literal["alert_fired", "diagnosis_complete"]
    fingerprint: str
    alertname: str
    service: str
    namespace: str
    severity: str
    summary: str = ""
    description: str = ""
    started_at: str = ""
    diagnosis: DiagnosisPayload | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SEVERITY_MAP = {
    "critical": IncidentSeverity.critical,
    "high": IncidentSeverity.high,
    "medium": IncidentSeverity.medium,
    "low": IncidentSeverity.low,
}

_ACTION_MAP: dict[str, ActionType] = {
    "rollout_restart": ActionType.rollout_restart,
    "restart_pod": ActionType.restart_pod,
    "scale_deployment": ActionType.scale_deployment,
    "rollback_deployment": ActionType.rollback_deployment,
}


def _get_or_create_incident(db: Session, req: IngestRequest) -> Incident:
    incident = (
        db.query(Incident)
        .filter(Incident.fingerprint == req.fingerprint)
        .first()
    )
    if incident:
        return incident

    severity = _SEVERITY_MAP.get(req.severity.lower(), IncidentSeverity.high)
    incident = Incident(
        fingerprint=req.fingerprint,
        title=req.alertname,
        service=req.service,
        namespace=req.namespace,
        severity=severity,
        status=IncidentStatus.active,
    )
    db.add(incident)
    db.flush()
    return incident


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/ingest", status_code=202)
def ingest(req: IngestRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        if req.event == "alert_fired":
            return _handle_alert_fired(db, req)
        if req.event == "diagnosis_complete":
            return _handle_diagnosis_complete(db, req)
        return {"status": "ignored", "reason": f"unknown event: {req.event}"}
    except Exception:
        db.rollback()
        raise


def _handle_alert_fired(db: Session, req: IngestRequest) -> dict:
    incident = _get_or_create_incident(db, req)

    db.add(Detection(
        incident_id=incident.id,
        source="prometheus-alertmanager",
        signal=req.alertname,
        raw_payload={
            "fingerprint": req.fingerprint,
            "alertname": req.alertname,
            "service": req.service,
            "severity": req.severity,
            "summary": req.summary,
            "description": req.description,
            "started_at": req.started_at,
        },
    ))
    db.add(AuditLogEntry(
        incident_id=incident.id,
        actor="detector",
        action="alert_fired",
        detail={"alertname": req.alertname, "fingerprint": req.fingerprint},
    ))

    db.commit()
    return {"status": "ok", "event": "alert_fired", "incident_id": incident.id}


def _handle_diagnosis_complete(db: Session, req: IngestRequest) -> dict:
    if req.diagnosis is None:
        return {"status": "ignored", "reason": "missing diagnosis payload"}

    diag = req.diagnosis
    incident = _get_or_create_incident(db, req)

    action_type = _ACTION_MAP.get(diag.action, ActionType.rollout_restart)

    agent_decision = AgentDecision(
        incident_id=incident.id,
        reasoning_trace=[{"step": "diagnose", "output": diag.reason}],
        proposed_action=action_type,
        target=diag.target,
        confidence=diag.confidence,
    )
    db.add(agent_decision)
    db.flush()

    verdict = PolicyVerdict.approved if diag.allowed else PolicyVerdict.denied
    policy_reason = (
        "; ".join(diag.policy_reasons) if diag.policy_reasons
        else f"risk={diag.risk}"
    )
    policy_check = PolicyCheck(
        incident_id=incident.id,
        agent_decision_id=agent_decision.id,
        verdict=verdict,
        reason=policy_reason,
        policy_name="warden.remediation",
    )
    db.add(policy_check)
    db.flush()

    if diag.policy_status == "needs_approval":
        incident.status = IncidentStatus.awaiting_approval
        db.add(ApprovalRequest(
            incident_id=incident.id,
            policy_check_id=policy_check.id,
            status=ApprovalStatus.pending,
        ))
    elif diag.policy_status == "auto_executable":
        incident.status = IncidentStatus.remediating

    incident.updated_at = datetime.now(UTC)

    db.add(AuditLogEntry(
        incident_id=incident.id,
        actor="agent",
        action="diagnosis_complete",
        detail={
            "action": diag.action,
            "target": diag.target,
            "confidence": diag.confidence,
            "policy_status": diag.policy_status,
        },
    ))

    db.commit()
    return {
        "status": "ok",
        "event": "diagnosis_complete",
        "incident_id": incident.id,
        "policy_status": diag.policy_status,
    }
