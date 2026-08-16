"""
Real process collector — actually watches what zombie_factory changes.
"""
import os
from datetime import datetime
from collector.base_collector import BaseCollector, TelemetryReading


class ProcessCollector(BaseCollector):
    def collect(self) -> list[TelemetryReading]:
        timestamp = datetime.utcnow()
        total = 0
        zombies = 0
        for pid_str in os.listdir('/proc'):
            if not pid_str.isdigit():
                continue
            total += 1
            try:
                with open(f'/proc/{pid_str}/status') as f:
                    if 'State:\tZ' in f.read():
                        zombies += 1
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue
        return [
            TelemetryReading(source='process', component='system', metric='total_process_count',
                              value=float(total), unit='count', timestamp=timestamp, raw={}),
            TelemetryReading(source='process', component='system', metric='zombie_count',
                              value=float(zombies), unit='count', timestamp=timestamp, raw={}),
        ]