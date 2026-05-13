"""
Reap zombie processes by signaling their parents.
"""
import os
import signal


def execute() -> tuple[bool, str]:
    zombies_found = 0
    reaped = 0

    try:
        for pid_str in os.listdir('/proc'):
            if not pid_str.isdigit():
                continue
            try:
                with open(f'/proc/{pid_str}/status') as f:
                    status = f.read()
                if 'State:\tZ' in status:
                    zombies_found += 1
                    # Get parent PID
                    for line in status.split('\n'):
                        if line.startswith('PPid:'):
                            ppid = int(line.split()[1])
                            os.kill(ppid, signal.SIGCHLD)
                            reaped += 1
                            break
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue

        return True, f"Found {zombies_found} zombies, signaled {reaped} parents"
    except Exception as e:
        return False, str(e)