"""
Collects real /proc metrics.
"""
from datetime import datetime
from collector.base_collector import BaseCollector, TelemetryReading


class ProcCollector(BaseCollector):
    def collect(self) -> list[TelemetryReading]:
        readings = []
        timestamp = datetime.utcnow()
        
        # Read /proc/meminfo
        try:
            with open('/proc/meminfo', 'r') as f:
                meminfo = {}
                for line in f:
                    parts = line.split(':')
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip().split()[0]
                        meminfo[key] = int(value)
            
            readings.append(TelemetryReading(
                source='proc',
                component='memory',
                metric='mem_available_kb',
                value=float(meminfo.get('MemAvailable', 0)),
                unit='KB',
                timestamp=timestamp,
                raw=meminfo
            ))
        except Exception as e:
            pass
        
        # Read /proc/loadavg
        try:
            with open('/proc/loadavg', 'r') as f:
                load = f.read().split()
                readings.append(TelemetryReading(
                    source='proc',
                    component='cpu',
                    metric='load_1min',
                    value=float(load[0]),
                    unit='load',
                    timestamp=timestamp,
                    raw={'loadavg': load}
                ))
        except Exception as e:
            pass
        
        return readings