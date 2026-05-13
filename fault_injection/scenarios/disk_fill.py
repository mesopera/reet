"""
Fills disk to a target percentage using fallocate.
"""
import os
import shutil
import subprocess
import uuid


class DiskFillScenario:
    def __init__(self, target_percent=0.8, target_dir='/tmp'):
        self.target_percent = target_percent
        self.target_dir = target_dir
        self.fill_file = os.path.join(target_dir, f'fault_fill_{uuid.uuid4().hex}')

    def inject(self):
        usage = shutil.disk_usage(self.target_dir)
        total = usage.total
        current_used = usage.used
        target_used = total * self.target_percent
        bytes_to_fill = int(target_used - current_used)

        if bytes_to_fill <= 0:
            print(f"Disk already at or above {self.target_percent*100}%")
            return

        result = subprocess.run(
            ['fallocate', '-l', str(bytes_to_fill), self.fill_file],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"fallocate failed: {result.stderr}")

    def cleanup(self):
        if os.path.exists(self.fill_file):
            os.remove(self.fill_file)

    def verify_injected(self) -> bool:
        usage = shutil.disk_usage(self.target_dir)
        percent = usage.used / usage.total
        return percent >= (self.target_percent - 0.05)