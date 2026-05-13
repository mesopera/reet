"""
Vacuum journal logs to free disk space.
"""
import subprocess


def execute(max_size: str = '500M') -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ['sudo', 'journalctl', f'--vacuum-size={max_size}'],
            capture_output=True, text=True, timeout=30
        )
        success = result.returncode == 0
        output = result.stdout + result.stderr
        return success, output
    except Exception as e:
        return False, str(e)