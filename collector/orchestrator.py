"""
Runs all collectors in parallel and aggregates results.
"""
import uuid
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from collector.hardware.smart_collector import SmartCollector
from collector.hardware.ipmi_collector import IpmiCollector
from collector.hardware.ecc_collector import EccCollector
from collector.os_layer.proc_collector import ProcCollector


@dataclass
class CollectionSnapshot:
    run_id: str
    timestamp: datetime
    readings: list
    errors: dict


class TelemetryOrchestrator:
    def __init__(self):
        self.collectors = [
            SmartCollector(),
            IpmiCollector(),
            EccCollector(),
            ProcCollector()
        ]

    def collect(self) -> CollectionSnapshot:
        run_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        all_readings = []
        errors = {}
        
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(c.collect): c.__class__.__name__ for c in self.collectors}
            
            for future in futures:
                collector_name = futures[future]
                try:
                    readings = future.result()
                    # Set shared timestamp
                    for r in readings:
                        r.timestamp = timestamp
                    all_readings.extend(readings)
                except Exception as e:
                    errors[collector_name] = str(e)
        
        print(f"Collected {len(all_readings)} readings from {len(self.collectors)} sources")
        if errors:
            print(f"Errors: {errors}")
        
        return CollectionSnapshot(
            run_id=run_id,
            timestamp=timestamp,
            readings=all_readings,
            errors=errors
        )


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    
    orch = TelemetryOrchestrator()
    snapshot = orch.collect()
    
    print(f"\nRun ID: {snapshot.run_id}")
    print(f"Timestamp: {snapshot.timestamp}")
    print(f"Total readings: {len(snapshot.readings)}")
    print("\nSample readings:")
    for r in snapshot.readings[:5]:
        print(f"  {r.source}/{r.component}/{r.metric} = {r.value} {r.unit}")