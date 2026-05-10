"""
Collects SMART telemetry - simulated or real.
"""
import os
from datetime import datetime
from collector.base_collector import BaseCollector, TelemetryReading
from simulator.smart_simulator import SmartSimulator


class SmartCollector(BaseCollector):
    def __init__(self, simulator=None):
        self.mode = os.getenv('MODE', 'simulate')
        self.simulator = simulator or SmartSimulator('healthy_baseline')

    def collect(self) -> list[TelemetryReading]:
        if self.mode == 'simulate':
            return self._collect_simulated()
        else:
            return self._collect_real()

    def _collect_simulated(self):
        data = self.simulator.get_reading()
        readings = []
        timestamp = datetime.utcnow()
        
        for attr_name, attr_data in data['smart_attributes'].items():
            readings.append(TelemetryReading(
                source='smart',
                component='sda',
                metric=attr_name,
                value=float(attr_data['raw_value']),
                unit='count' if attr_name != 'temperature_celsius' else 'celsius',
                timestamp=timestamp,
                raw=attr_data
            ))
        
        return readings

    def _collect_real(self):
        # TODO: Run smartctl -x --json /dev/sda
        # For now just return empty
        return []