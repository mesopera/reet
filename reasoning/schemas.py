"""
Pydantic models for LLM output validation.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional


VALID_FAULT_CATEGORIES = ['hardware', 'os', 'application', 'network', 'database']
VALID_ACTIONS = ['restart_service', 'vacuum_logs', 'reap_zombies', 'trigger_vacuum', None]


class CausalStep(BaseModel):
    timestamp_offset_seconds: float
    component: str
    event: str
    caused_by: Optional[str] = None


class IncidentReport(BaseModel):
    root_cause: str
    root_cause_component: str
    confidence: float = Field(ge=0.0, le=1.0)
    fault_category: str
    hardware_involved: bool
    causal_chain: list[CausalStep]
    auto_remediable: bool
    suggested_action: Optional[str] = None
    plain_language_summary: str
    reasoning: str

    @field_validator('fault_category')
    @classmethod
    def validate_category(cls, v):
        if v not in VALID_FAULT_CATEGORIES:
            raise ValueError(f"fault_category must be one of {VALID_FAULT_CATEGORIES}")
        return v

    @field_validator('suggested_action')
    @classmethod
    def validate_action(cls, v):
        if v not in VALID_ACTIONS:
            raise ValueError(f"suggested_action must be one of {VALID_ACTIONS}")
        return v