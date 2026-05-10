"""
Collects IPMI sensor data.
"""
import os
from datetime import datetime
from collector.base_collector import BaseCollector, TelemetryReading
from simulator.ipmi_simulator import IpmiSimulator


class IpmiCollector(BaseCollector):
    def __init__(self, simulator=None):
        self.mode = os.getenv('MODE', 'simulate')
        self.simulator = simulator or IpmiSimulator('healthy_baseline')

    def collect(self) -> list[TelemetryReading]:
        if self.mode == 'simulate':
            return self._collect_simulated()
        else:
            return self._collect_real()

    def _collect_simulated(self):
        data = self.simulator.get_reading()
        readings = []
        timestamp = datetime.utcnow()
        
        for sensor in data['sensors']:
            # Skip non-numeric sensors
            if not isinstance(sensor['value'], (int, float)):
                continue
                
            readings.append(TelemetryReading(
                source='ipmi',
                component=sensor['name'].lower().replace(' ', '_'),
                metric='sensor_value',
                value=float(sensor['value']),
                unit=sensor['unit'],
                timestamp=timestamp,
                raw=sensor
            ))
        
        return readings

    def _collect_real(self):
        return []