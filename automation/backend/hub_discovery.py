"""List YKUSH serial numbers through the vendor CLI without switching ports."""
import os
from pathlib import Path
import re
import shutil
import subprocess


def resolve_command(command):
    executable = shutil.which(command)
    if executable is None and command == "ykushcmd":
        for root in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
            if root:
                candidate = Path(root) / "YEPKIT LDA" / "ykushcmd" / "ykushcmd.exe"
                if candidate.is_file():
                    executable = str(candidate)
                    break
    if executable is None:
        raise FileNotFoundError("ykushcmd not found. Set hub.cmd in automation/backend/config.json.")
    return executable


def available_hubs(driver, command="ykushcmd"):
    if driver not in ("ykush", "ykush3"):
        raise ValueError("Expected ykush or ykush3")
    executable = resolve_command(command)
    args = [executable] + (["ykush3"] if driver == "ykush3" else []) + ["-l"]
    result = subprocess.run(args, capture_output=True, text=True, errors="replace", timeout=10,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"ykushcmd exited with {result.returncode}")
    serials = re.findall(r"serial\s+number\s*:\s*([^\s]+)", result.stdout, re.IGNORECASE)
    return [{"serial": serial} for serial in dict.fromkeys(serials)]
