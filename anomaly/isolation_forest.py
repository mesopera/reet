"""
Multivariate Isolation Forest anomaly detector.
"""
import os
import pickle
import numpy as np
from sklearn.ensemble import IsolationForest as SKLearnIF


class IsolationForestDetector:
    def __init__(self, contamination=0.05, warmup_readings=200, retrain_every=1000):
        self.contamination = contamination
        self.warmup_readings = warmup_readings
        self.retrain_every = retrain_every
        self.model = None
        self.buffer = []
        self.total_seen = 0
        self.model_path = 'data/isolation_forest.pkl'

    def _feature_vector(self, snapshot_readings: list) -> list:
        """Convert a list of readings into a flat feature vector."""
        metrics = {}
        for r in snapshot_readings:
            key = f"{r.source}_{r.component}_{r.metric}"
            metrics[key] = r.value
        return list(metrics.values())

    def update(self, snapshot_readings: list):
        vec = self._feature_vector(snapshot_readings)
        if not vec:
            return
        self.buffer.append(vec)
        self.total_seen += 1

        # Train after warmup
        if self.total_seen == self.warmup_readings:
            self._train()

        # Retrain periodically
        if self.total_seen > self.warmup_readings and self.total_seen % self.retrain_every == 0:
            self._train()

    def _train(self):
        if len(self.buffer) < 10:
            return
        # Normalize buffer to same length vectors
        max_len = max(len(v) for v in self.buffer)
        padded = [v + [0.0] * (max_len - len(v)) for v in self.buffer]
        self.model = SKLearnIF(contamination=self.contamination, random_state=42)
        self.model.fit(padded)
        self.feature_len = max_len

    def score(self, snapshot_readings: list) -> float | None:
        if self.model is None:
            return None
        vec = self._feature_vector(snapshot_readings)
        if not vec:
            return None
        # Pad to trained feature length
        padded = vec + [0.0] * (self.feature_len - len(vec))
        padded = padded[:self.feature_len]
        score = self.model.score_samples([padded])[0]
        return score

    def is_anomalous(self, snapshot_readings: list) -> bool:
        score = self.score(snapshot_readings)
        if score is None:
            return False
        return score < -0.1