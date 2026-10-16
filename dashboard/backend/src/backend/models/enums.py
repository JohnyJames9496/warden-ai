"""
Shared enums for model status fields. Kept in one place so the same set of
values is used consistently across models, API schemas, and the frontend
contract (these string values are what the API actually returns as JSON).
"""

import enum


class IncidentSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class IncidentStatus(str, enum.Enum):
    active = "active"
    awaiting_approval = "awaiting_approval"
    remediating = "remediating"
    resolved = "resolved"
    rejected = "rejected"


class PolicyVerdict(str, enum.Enum):
    approved = "approved"
    denied = "denied"


class ApprovalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


# The whitelisted remediation actions — nothing outside this set.
class ActionType(str, enum.Enum):
    restart_pod = "restart_pod"
    rollout_restart = "rollout_restart"
    scale_deployment = "scale_deployment"
    rollback_deployment = "rollback_deployment"
    toggle_feature_flag = "toggle_feature_flag"


class ActionStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    succeeded = "succeeded"
    failed = "failed"
