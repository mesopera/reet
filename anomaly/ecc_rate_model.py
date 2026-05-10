"""
Detects accelerating ECC error rates.
"""
from dataclasses import dataclass
import numpy as np


@dataclass
class EccRateResult:
    current_rate_per_hour: float
    doubling_time_hours: float | None
    is_accelerating: bool
    urgency_score: float


class EccRateDetector:
    def __init__(self, doubling_window_hours=8):
        self.doubling_window = doubling_window_hours
        self.history = []  # list of (timestamp, ce_count)

    def update(self, reading):
        if reading.metric != 'ce_count':
            return
        self.history.append((reading.timestamp, reading.value))
        # Keep last 24 hours
        if len(self.history) > 1440:
            self.history = self.history[-1440:]

    def compute(self) -> EccRateResult | None:
        if len(self.history) < 10:
            return None

        timestamps = [h[0] for h in self.history]
        values = np.array([h[1] for h in self.history])

        t0 = timestamps[0]
        hours = np.array([(t - t0).total_seconds() / 3600.0 for t in timestamps])

        if hours[-1] == 0:
            return None

        # Rate per hour
        total_elapsed = hours[-1]
        if total_elapsed == 0:
            return None

        current_rate = float(values[-1] - values[0]) / total_elapsed

        # Check if rate doubled within any window
        doubling_time = None
        is_accelerating = False

        if len(self.history) > 20:
            mid = len(self.history) // 2
            first_half_rate = float(values[mid] - values[0]) / max(hours[mid], 0.01)
            second_half_rate = float(values[-1] - values[mid]) / max(hours[-1] - hours[mid], 0.01)

            if first_half_rate > 0 and second_half_rate > first_half_rate * 1.5:
                is_accelerating = True
                if second_half_rate > 0:
                    doubling_time = total_elapsed / 2

        urgency = min(1.0, current_rate / 10.0)

        return EccRateResult(
            current_rate_per_hour=current_rate,
            doubling_time_hours=doubling_time,
            is_accelerating=is_accelerating,
            urgency_score=urgency
        )