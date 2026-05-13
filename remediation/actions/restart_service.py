"""
Restart a systemd service.
"""
import subprocess


def execute(unit_name: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ['sudo', 'systemctl', 'restart', unit_name],
            capture_output=True, text=True, timeout=30
        )
        success = result.returncode == 0
        output = result.stdout + result.stderr
        return success, output
    except Exception as e:
        return False, str(e)