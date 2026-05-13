"""
Simulates NFS hang via log injection (no real NFS needed).
"""
import subprocess
import threading
import time


class NfsHangScenario:
    def __init__(self, duration_seconds=60):
        self.duration_seconds = duration_seconds
        self._stop = threading.Event()
        self._thread = None

    def inject(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._emit_nfs_errors, daemon=True)
        self._thread.start()

    def _emit_nfs_errors(self):
        end_time = time.time() + self.duration_seconds
        while not self._stop.is_set() and time.time() < end_time:
            subprocess.run(
                ['logger', '-t', 'kernel',
                 'nfs: server not responding, timed out'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            time.sleep(2)

    def cleanup(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def verify_injected(self) -> bool:
        return self._thread is not None and self._thread.is_alive()