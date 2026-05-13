"""
Captures pre-action system state for rollback reference.
"""
import os
import json
import subprocess
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class SnapshotManager:
    def __init__(self):
        self.snapshot_dir = os.getenv('SNAPSHOT_DIR', 'data/snapshots')
        os.makedirs(self.snapshot_dir, exist_ok=True)

    def take(self, incident_id: str, action_id: str) -> str:
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        path = os.path.join(self.snapshot_dir, f"{incident_id}_{action_id}_{timestamp}")
        os.makedirs(path, exist_ok=True)

        state = {
            'incident_id': incident_id,
            'action_id': action_id,
            'timestamp': timestamp,
            'disk_usage': self._disk_usage(),
            'process_count': self._process_count(),
            'load': self._load()
        }

        with open(os.path.join(path, 'state.json'), 'w') as f:
            json.dump(state, f, indent=2)

        return path

    def _disk_usage(self) -> dict:
        try:
            import shutil
            usage = shutil.disk_usage('/')
            return {'total': usage.total, 'used': usage.used, 'free': usage.free}
        except:
            return {}

    def _process_count(self) -> int:
        try:
            return len(os.listdir('/proc'))
        except:
            return 0

    def _load(self) -> list:
        try:
            with open('/proc/loadavg') as f:
                parts = f.read().split()
                return [float(parts[0]), float(parts[1]), float(parts[2])]
        except:
            return []