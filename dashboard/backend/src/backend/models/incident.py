"""
Incident — the central record. Every other model (Detection, AgentDecision,
PolicyCheck, ApprovalRequest, RemediationAction, AuditLogEntry) links back
to an Incident via incident_id, which is what makes the full trace on the
Incident Detail page possible.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.enums import IncidentSeverity, IncidentStatus
from backend.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from backend.models.agent_decision import AgentDecision
    from backend.models.approval_request import ApprovalRequest
    from backend.models.audit_log_entry import AuditLogEntry
    from backend.models.detection import Detection
    from backend.models.policy_check import PolicyCheck
    from backend.models.remediation_action import RemediationAction


class Incident(Base, TimestampMixin):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Alertmanager fingerprint — used to upsert on re-fires.
    # Nullable so seeded/test incidents without a real alert still work.
    fingerprint: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    service: Mapped[str] = mapped_column(String(255), nullable=False)
    namespace: Mapped[str] = mapped_column(String(255), nullable=False)

    severity: Mapped[IncidentSeverity] = mapped_column(
        Enum(IncidentSeverity, native_enum=False), nullable=False
    )
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus, native_enum=False),
        nullable=False,
        default=IncidentStatus.active,
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    detections: Mapped[list["Detection"]] = relationship(
        back_populates="incident",
        order_by="Detection.created_at",
        cascade="all, delete-orphan",
    )
    agent_decisions: Mapped[list["AgentDecision"]] = relationship(
        back_populates="incident",
        order_by="AgentDecision.created_at",
        cascade="all, delete-orphan",
    )
    policy_checks: Mapped[list["PolicyCheck"]] = relationship(
        back_populates="incident",
        order_by="PolicyCheck.created_at",
        cascade="all, delete-orphan",
    )
    approval_requests: Mapped[list["ApprovalRequest"]] = relationship(
        back_populates="incident",
        order_by="ApprovalRequest.created_at",
        cascade="all, delete-orphan",
    )
    remediation_actions: Mapped[list["RemediationAction"]] = relationship(
        back_populates="incident",
        order_by="RemediationAction.created_at",
        cascade="all, delete-orphan",
    )
    audit_log_entries: Mapped[list["AuditLogEntry"]] = relationship(
        back_populates="incident",
        order_by="AuditLogEntry.created_at",
        cascade="all, delete-orphan",
    )
