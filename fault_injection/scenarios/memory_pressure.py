"""
Creates memory pressure using stress-ng.
"""
import subprocess
import psutil


class MemoryPressureScenario:
    def __init__(self, percent_of_ram=0.7, duration_seconds=60):
        self.percent_of_ram = percent_of_ram
        self.duration_seconds = duration_seconds
        self.process = None

    def inject(self):
        total_ram = psutil.virtual_memory().total
        bytes_to_use = int(total_ram * self.percent_of_ram)

        self.process = subprocess.Popen(
            ['stress-ng', '--vm', '1',
             '--vm-bytes', str(bytes_to_use),
             '--timeout', str(self.duration_seconds)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    def cleanup(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process.wait()

    def verify_injected(self) -> bool:
        mem = psutil.virtual_memory()
        return mem.percent >= (self.percent_of_ram * 100 - 10)