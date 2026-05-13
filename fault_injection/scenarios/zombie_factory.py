"""
Creates zombie processes.
"""
import os
import multiprocessing
import time


def _child_worker():
    # Child exits immediately without being reaped
    os._exit(0)


class ZombieFactoryScenario:
    def __init__(self, count=5):
        self.count = count
        self.parent_process = None
        self.pipe_r = None
        self.pipe_w = None

    def inject(self):
        # Use a pipe to keep parent alive
        self.pipe_r, self.pipe_w = os.pipe()

        def spawn_zombies(pipe_r, count):
            os.close(pipe_r)
            for _ in range(count):
                pid = os.fork()
                if pid == 0:
                    os._exit(0)  # child exits immediately
            # Parent keeps running, never reaps children
            time.sleep(300)

        self.parent_process = multiprocessing.Process(
            target=spawn_zombies,
            args=(self.pipe_r, self.count)
        )
        self.parent_process.start()
        time.sleep(1)  # let zombies form

    def cleanup(self):
        if self.parent_process and self.parent_process.is_alive():
            self.parent_process.terminate()
            self.parent_process.join()
        if self.pipe_w:
            try:
                os.close(self.pipe_w)
            except:
                pass

    def verify_injected(self) -> bool:
        zombie_count = 0
        for pid_str in os.listdir('/proc'):
            if not pid_str.isdigit():
                continue
            try:
                with open(f'/proc/{pid_str}/status') as f:
                    if 'State:\tZ' in f.read():
                        zombie_count += 1
            except:
                continue
        return zombie_count >= 1