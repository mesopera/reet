"""
Real disk usage collector — actually watches what disk_fill changes.
"""
import shutil
from datetime import datetime
from collector.base_collector import BaseCollector, TelemetryReading


class DiskCollector(BaseCollector):
    def __init__(self, path="/tmp"):
        self.path = path

    def collect(self) -> list[TelemetryReading]:
        readings = []
        timestamp = datetime.utcnow()
        try:
            usage = shutil.disk_usage(self.path)
            percent_used = (usage.used / usage.total) * 100
            readings.append(TelemetryReading(
                source='disk', component=self.path, metric='disk_percent_used',
                value=float(percent_used), unit='percent', timestamp=timestamp,
                raw={'total': usage.total, 'used': usage.used, 'free': usage.free}
            ))
        except Exception:
            pass
        return readings