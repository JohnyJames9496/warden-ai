"""Shared contract between the diagnosis agent (M4), policy engine (M5),
and executor (M7). Any change here affects all three milestones."""

from enum import Enum

from pydantic import BaseModel, Field


class Action(str, Enum):
    restart_pod = "restart_pod"
    rollout_restart = "rollout_restart"
    scale_deployment = "scale_deployment"
    rollback_deployment = "rollback_deployment"
    no_action = "no_action"


class Diagnosis(BaseModel):
    root_cause: str = Field(description="One-sentence root cause")
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(description="Facts from the input supporting the root cause")
    proposed_action: Action
    namespace: str
    target: str = Field(description="Deployment or pod name")
    replicas: int | None = Field(default=None, description="Only for scale_deployment")
