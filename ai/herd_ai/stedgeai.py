"""Driving ST Edge AI Core (the `stedgeai` command) for the STM32N6 Neural-ART NPU.

The compiler is not a Python package. ST's online installer puts it under
``C:/ST/STEdgeAI/<version>/Utilities/windows/stedgeai.exe`` (Linux: ``~/STEdgeAI/<version>/Utilities/linux``).
We locate it, build the same command the STM32 model zoo uses for the N6, run it, and copy its text reports next
to the other results so they can be committed.

    stedgeai analyze  --model m.tflite --target stm32n6 --st-neural-art [profile@config.json] --output <dir>
    stedgeai generate ...   -> network.c, network_ecblobs.h, network_atonbuf.xSPI2.raw (weights for external flash)

``--st-neural-art`` without a value uses the tool's built-in default memory profile; the N6 application packages
ship a ``user_neuralart.json`` whose profiles can be selected with ``default@<path>``.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_ROOTS = [Path("C:/ST/STEdgeAI"), Path.home() / "STEdgeAI"]
EXE_NAMES = ("stedgeai.exe", "stedgeai.cmd", "stedgeai.bat", "stedgeai")
SUBDIRS = ("Utilities/windows", "Utilities/linux", "Utilities/mac", "")
TARGET = "stm32n6"


def _version_key(name: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", name)) or (0,)


def _exe_in(folder: Path) -> Path | None:
    for sub in SUBDIRS:
        for exe in EXE_NAMES:
            candidate = folder / sub / exe
            if candidate.is_file():
                return candidate
    return None


def find_stedgeai(roots: Iterable[Path] | None = None) -> Path | None:
    """The compiler executable, or None. Order: STEDGEAI_HOME (install folder or the exe itself), PATH, then the
    newest version folder under the default install roots."""
    env = os.environ.get("STEDGEAI_HOME")
    if env:
        p = Path(env)
        found = p if p.is_file() else _exe_in(p)
        if found:
            return found
    which = shutil.which("stedgeai")
    if which:
        return Path(which)
    for root in (list(roots) if roots is not None else DEFAULT_ROOTS):
        if not root.is_dir():
            continue
        versions = sorted((d for d in root.iterdir() if d.is_dir()), key=lambda d: _version_key(d.name), reverse=True)
        for ver in versions:
            found = _exe_in(ver)
            if found:
                return found
    return None


def version(exe: Path) -> str:
    out = subprocess.run([str(exe), "--version"], capture_output=True, text=True, timeout=120)
    return (out.stdout + out.stderr).strip()


def build_command(exe: Path, action: str, model: Path, output: Path, *, neural_art: str | None = None,
                  name: str = "network", extra: Sequence[str] = ()) -> list[str]:
    """`action` is analyze, generate or validate. `neural_art` is `profile@config.json` or None for the default."""
    cmd = [str(exe), action, "--model", str(model), "--target", TARGET, "--name", name,
           "--output", str(output), "--workspace", str(Path(output) / "st_ai_ws"), "--st-neural-art"]
    if neural_art:
        cmd.append(neural_art)
    cmd.extend(extra)
    return cmd


@dataclass
class RunResult:
    returncode: int
    command: list[str]
    work_dir: Path
    log_path: Path
    filed_dir: Path | None = None
    reports: list[Path] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""


def run(exe: Path, action: str, model: Path, work_dir: Path, *, results_dir: Path | None = None,
        neural_art: str | None = None, name: str = "network", extra: Sequence[str] = (), timeout: int = 3600) -> RunResult:
    """Run one compiler action. Generated files land in `work_dir`; the `*_report.txt` files and a log of the
    command + output are copied to `results_dir/<model stem>/` when `results_dir` is given."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    cmd = build_command(exe, action, Path(model), work_dir, neural_art=neural_art, name=name, extra=extra)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    filed_dir = Path(results_dir) / Path(model).stem if results_dir is not None else None
    log_dir = filed_dir if filed_dir is not None else work_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{action}.log"
    log_path.write_text("$ " + " ".join(cmd) + "\n\n" + proc.stdout + ("\n[stderr]\n" + proc.stderr if proc.stderr else ""),
                        encoding="utf-8")
    reports = sorted(work_dir.glob("*_report.txt"))
    if filed_dir is not None:
        for r in reports:
            shutil.copy2(r, filed_dir / r.name)
        reports = [filed_dir / r.name for r in reports]
    return RunResult(proc.returncode, cmd, work_dir, log_path, filed_dir, reports, proc.stdout, proc.stderr)
