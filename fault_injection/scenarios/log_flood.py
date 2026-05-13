"""
Floods journald with log messages.
"""
import subprocess
import threading
import time


class LogFloodScenario:
    def __init__(self, messages_per_second=50, duration_seconds=60):
        self.messages_per_second = messages_per_second
        self.duration_seconds = duration_seconds
        self._stop = threading.Event()
        self._thread = None

    def inject(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._flood, daemon=True)
        self._thread.start()

    def _flood(self):
        interval = 1.0 / self.messages_per_second
        end_time = time.time() + self.duration_seconds
        while not self._stop.is_set() and time.time() < end_time:
            subprocess.run(
                ['logger', '-t', 'fault_injection',
                 'ERROR: simulated fault injection log message'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(interval)

    def cleanup(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def verify_injected(self) -> bool:
        return self._thread is not None and self._thread.is_alive()