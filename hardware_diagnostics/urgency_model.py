"""
Classifies hardware fault urgency from acceleration data.
"""
from dataclasses import dataclass
from enum import Enum


class UrgencyTier(str, Enum):
    MONITOR = "Monitor"
    SCHEDULE_MAINTENANCE = "Schedule Maintenance"
    HIGH_URGENCY = "High Urgency"
    CRITICAL = "Critical"


@dataclass
class UrgencyAssessment:
    tier: UrgencyTier
    estimated_hours_to_failure: float | None
    rationale: str


def assess(doubling_time_hours: float | None, has_uncorrectable: bool = False,
           current_value: float = 0) -> UrgencyAssessment:
    """
    doubling_time_hours: how fast the fault metric is doubling (None = not accelerating)
    has_uncorrectable: True if any uncorrectable error present (always critical)
    """
    if has_uncorrectable:
        return UrgencyAssessment(
            tier=UrgencyTier.CRITICAL,
            estimated_hours_to_failure=4.0,
            rationale="Uncorrectable error present — data integrity at immediate risk"
        )

    if doubling_time_hours is None:
        return UrgencyAssessment(
            tier=UrgencyTier.MONITOR,
            estimated_hours_to_failure=None,
            rationale="No acceleration detected — attribute is stable or slowly changing"
        )

    if doubling_time_hours < 4:
        return UrgencyAssessment(
            tier=UrgencyTier.CRITICAL,
            estimated_hours_to_failure=doubling_time_hours * 2,
            rationale=f"Error rate doubling every {doubling_time_hours:.1f}h — failure imminent"
        )
    elif doubling_time_hours < 12:
        return UrgencyAssessment(
            tier=UrgencyTier.HIGH_URGENCY,
            estimated_hours_to_failure=doubling_time_hours * 4,
            rationale=f"Error rate doubling every {doubling_time_hours:.1f}h — replace within days"
        )
    elif doubling_time_hours < 72:
        return UrgencyAssessment(
            tier=UrgencyTier.SCHEDULE_MAINTENANCE,
            estimated_hours_to_failure=doubling_time_hours * 8,
            rationale=f"Error rate doubling every {doubling_time_hours:.1f}h — schedule replacement"
        )
    else:
        return UrgencyAssessment(
            tier=UrgencyTier.MONITOR,
            estimated_hours_to_failure=None,
            rationale="Slow acceleration — continue monitoring, no immediate action needed"
        )