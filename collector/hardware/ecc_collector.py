"""
Collects ECC error counts.
"""
import os
from datetime import datetime
from collector.base_collector import BaseCollector, TelemetryReading
from simulator.ecc_simulator import EccSimulator


class EccCollector(BaseCollector):
    def __init__(self, simulator=None):
        self.mode = os.getenv('MODE', 'simulate')
        self.simulator = simulator or EccSimulator('healthy_baseline')

    def collect(self) -> list[TelemetryReading]:
        if self.mode == 'simulate':
            return self._collect_simulated()
        else:
            return self._collect_real()

    def _collect_simulated(self):
        data = self.simulator.get_reading()
        timestamp = datetime.utcnow()
        
        return [
            TelemetryReading(
                source='ecc',
                component='memory',
                metric='ce_count',
                value=float(data['ce_count']),
                unit='count',
                timestamp=timestamp,
                raw=data
            ),
            TelemetryReading(
                source='ecc',
                component='memory',
                metric='ue_count',
                value=float(data['ue_count']),
                unit='count',
                timestamp=timestamp,
                raw=data
            )
        ]

    def _collect_real(self):
        return []