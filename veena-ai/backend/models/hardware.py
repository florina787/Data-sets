"""Hardware and runtime detection for the setup wizard."""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import psutil


def _run(cmd: list[str], timeout: float = 5.0) -> str | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True).stdout
    except (subprocess.SubprocessError, OSError):
        return None


def _cpu_name() -> str:
    system = platform.system()
    if system == "Linux":
        try:
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
        except OSError:
            pass
    elif system == "Darwin":
        out = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
        if out:
            return out.strip()
    elif system == "Windows":
        out = _run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"])
        if out:
            return out.strip().splitlines()[0]
    return platform.processor() or platform.machine()


def detect_gpus() -> list[dict[str, Any]]:
    gpus: list[dict[str, Any]] = []
    if shutil.which("nvidia-smi"):
        out = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
        for line in (out or "").strip().splitlines():
            name, mem = [x.strip() for x in line.split(",", 1)]
            gpus.append({"vendor": "NVIDIA", "name": name, "vram_mb": float(mem), "accelerated": True})
    if not gpus and shutil.which("rocm-smi"):
        out = _run(["rocm-smi", "--showproductname", "--showmeminfo", "vram", "--csv"])
        if out:
            m = re.search(r"VRAM Total Memory \(B\),(\d+)", out)
            gpus.append(
                {
                    "vendor": "AMD",
                    "name": "AMD GPU (ROCm)",
                    "vram_mb": int(m.group(1)) / 2**20 if m else None,
                    "accelerated": True,
                }
            )
    system = platform.system()
    if system == "Darwin" and platform.machine() == "arm64":
        # Apple Silicon shares system memory with the GPU; Ollama uses Metal.
        gpus.append(
            {
                "vendor": "Apple",
                "name": "Apple Silicon GPU (unified memory)",
                "vram_mb": psutil.virtual_memory().total / 2**20,
                "accelerated": True,
            }
        )
    if not gpus and system == "Windows":
        out = _run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name + '|' + $_.AdapterRAM }",
            ]
        )
        for line in (out or "").strip().splitlines():
            if "|" in line:
                name, ram = line.rsplit("|", 1)
                vram = int(ram) / 2**20 if ram.strip().isdigit() else None
                # Ollama accelerates NVIDIA (CUDA) and recent AMD (ROCm) cards
                # on Windows; integrated adapters run on the CPU.
                accel = bool(re.search(r"nvidia|radeon rx", name, re.I))
                gpus.append({"vendor": name.split()[0], "name": name.strip(), "vram_mb": vram, "accelerated": accel})
    if not gpus and system == "Linux" and shutil.which("lspci"):
        out = _run(["lspci"]) or ""
        for line in out.splitlines():
            if re.search(r"VGA|3D controller", line):
                gpus.append({"vendor": "unknown", "name": line.split(":", 2)[-1].strip(), "vram_mb": None, "accelerated": False})
    return gpus


def _tool_version(cmd: list[str]) -> str | None:
    if not shutil.which(cmd[0]):
        return None
    out = _run(cmd)
    return out.strip().splitlines()[0] if out else "installed"


def detect(data_dir: Path | None = None) -> dict[str, Any]:
    vm = psutil.virtual_memory()
    disk_path = str(data_dir if data_dir and data_dir.exists() else Path.home())
    du = shutil.disk_usage(disk_path)
    return {
        "os": {"system": platform.system(), "release": platform.release(), "version": platform.version(), "machine": platform.machine()},
        "cpu": {
            "name": _cpu_name(),
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
        },
        "ram_gb": round(vm.total / 2**30, 1),
        "ram_available_gb": round(vm.available / 2**30, 1),
        "disk_free_gb": round(du.free / 2**30, 1),
        "gpus": detect_gpus(),
        "runtimes": {
            "python": sys.version.split()[0],
            "node": _tool_version(["node", "--version"]),
            "ollama": _tool_version(["ollama", "--version"]),
            "tesseract": _tool_version(["tesseract", "--version"]),
            "ffmpeg": _tool_version(["ffmpeg", "-version"]),
        },
    }
