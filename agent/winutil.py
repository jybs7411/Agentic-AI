"""Small Windows helpers shared by several modules."""

import os
import subprocess

CREATE_NO_WINDOW = 0x08000000  # don't flash a black console window


def run_powershell(script: str, timeout: int = 60, env_extra: dict = None):
    """Run a PowerShell script hidden. Returns (exit_code, stdout, stderr) as text (UTF-8 safe)."""
    prefix = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $ProgressPreference='SilentlyContinue'; "
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-Command", prefix + script],
        capture_output=True,
        timeout=timeout,
        env=env,
        creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", errors="replace").strip(),
        proc.stderr.decode("utf-8", errors="replace").strip(),
    )
