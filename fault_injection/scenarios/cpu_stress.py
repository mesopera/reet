"""
Creates CPU stress using stress-ng.
"""
import subprocess
import os


class CpuStressScenario:
    def __init__(self, cores=2, duration_seconds=60):
        self.cores = cores
        self.duration_seconds = duration_seconds
        self.process = None

    def inject(self):
        self.process = subprocess.Popen(
            ['stress-ng', '--cpu', str(self.cores),
             '--timeout', str(self.duration_seconds)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    def cleanup(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process.wait()

    def verify_injected(self) -> bool:
        with open('/proc/loadavg') as f:
            load = float(f.read().split()[0])
        return load >= self.cores * 0.5