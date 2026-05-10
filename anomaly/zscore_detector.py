"""
Univariate Z-score anomaly detector with rolling window.
"""
from collections import deque
import numpy as np
from collector.base_collector import TelemetryReading


class ZScoreDetector:
    def __init__(self, threshold=3.0, min_window=10, max_window=100):
        self.threshold = threshold
        self.min_window = min_window
        self.windows = {}  # key: (component, metric) -> deque of values

    def _key(self, reading: TelemetryReading):
        return (reading.component, reading.metric)

    def update(self, reading: TelemetryReading):
        k = self._key(reading)
        if k not in self.windows:
            self.windows[k] = deque(maxlen=100)
        self.windows[k].append(reading.value)

    def score(self, reading: TelemetryReading) -> float | None:
        k = self._key(reading)
        if k not in self.windows or len(self.windows[k]) < self.min_window:
            return None
        vals = np.array(self.windows[k])
        mean = np.mean(vals)
        std = np.std(vals)
        if std == 0:
            return 0.0
        return abs((reading.value - mean) / std)

    def is_anomalous(self, reading: TelemetryReading, threshold=None) -> bool:
        t = threshold or self.threshold
        z = self.score(reading)
        if z is None:
            return False
        return z > t