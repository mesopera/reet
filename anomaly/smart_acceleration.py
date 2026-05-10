"""
Detects accelerating SMART attribute degradation.
First and second derivative over time.
"""
import numpy as np
from dataclasses import dataclass


MONITORED_ATTRIBUTES = [
    'reallocated_sector_ct',
    'reported_uncorrectable_errors',
    'command_timeout',
    'current_pending_sector_ct',
    'offline_uncorrectable'
]


@dataclass
class AccelerationResult:
    attribute: str
    component: str
    current_value: float
    first_derivative: float   # rate of change per hour
    second_derivative: float  # acceleration
    is_accelerating: bool
    urgency_score: float      # 0.0 - 1.0


class SmartAccelerationDetector:
    def __init__(self):
        # In-memory history per (component, metric)
        self.history = {}  # key -> list of (timestamp, value)

    def update(self, reading):
        if reading.metric not in MONITORED_ATTRIBUTES:
            return
        k = (reading.component, reading.metric)
        if k not in self.history:
            self.history[k] = []
        self.history[k].append((reading.timestamp, reading.value))
        # Keep last 72 hours worth (at 1 reading/min = 4320 max)
        if len(self.history[k]) > 4320:
            self.history[k] = self.history[k][-4320:]

    def compute(self, component: str, attribute: str) -> AccelerationResult | None:
        k = (component, attribute)
        if k not in self.history or len(self.history[k]) < 10:
            return None

        history = self.history[k]
        timestamps = [h[0] for h in history]
        values = np.array([h[1] for h in history])

        # Convert timestamps to hours elapsed
        t0 = timestamps[0]
        hours = np.array([(t - t0).total_seconds() / 3600.0 for t in timestamps])

        if hours[-1] == 0:
            return None

        # First derivative (rate of change per hour)
        first_deriv = np.gradient(values, hours)
        # Second derivative (acceleration)
        second_deriv = np.gradient(first_deriv, hours)

        current_fd = float(first_deriv[-1])
        current_sd = float(second_deriv[-1])
        current_val = float(values[-1])

        # Accelerating if second derivative positive and value above zero
        is_accelerating = current_sd > 0.01 and current_val > 0

        # Urgency: combination of value magnitude and acceleration rate
        raw_urgency = current_sd * current_val
        urgency_score = min(1.0, raw_urgency / 10.0)

        return AccelerationResult(
            attribute=attribute,
            component=component,
            current_value=current_val,
            first_derivative=current_fd,
            second_derivative=current_sd,
            is_accelerating=is_accelerating,
            urgency_score=urgency_score
        )

    def run_all(self) -> list[AccelerationResult]:
        results = []
        for (component, attribute) in self.history:
            result = self.compute(component, attribute)
            if result and result.is_accelerating:
                results.append(result)
        return results