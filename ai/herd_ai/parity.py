"""Replaying one detection stream through the firmware's C (tracker.c + behavior.c, via
firmware/tests/trace_main.c) and through the Python mirrors, and comparing the output.

Why: the week 7-9 numbers are measured with the Python mirrors on a laptop. This proves the mirrors
produce the same ids, positions, speeds and lingering reports as the C the board runs. The settings
(TRACK_MATCH_DIST, LINGER_RADIUS, the guards, ...) are read from app_config.h so both sides use the
firmware's numbers; `defines` can override them on both sides at once."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from .behavior import LingerDetector
from .mot import GTBox
from .paths import AI_ROOT
from .tracker import Detection, NearestTracker

FIRMWARE = AI_ROOT.parent / "firmware"
APP_CONFIG = FIRMWARE / "stm32" / "App" / "app_config.h"
TRACE_SOURCES = ["tests/trace_main.c", "stm32/App/tracker.c", "stm32/App/behavior.c"]
MSYS_GCC = Path("C:/msys64/ucrt64/bin/gcc.exe")
CONFIG_KEYS = ("TRACK_MATCH_DIST", "TRACK_DROP_MS", "TRACK_MAX", "LINGER_RADIUS", "LINGER_TIME_MS", "LINGER_REQUIRE_MOTION", "LINGER_MIN_SCORE")


def firmware_config(defines: dict[str, int] | None = None) -> dict[str, int]:
    """Integer #defines from app_config.h (and tracker.h's TRACK_MAX), with `defines` on top."""
    cfg: dict[str, int] = {"TRACK_MAX": 8}
    text = APP_CONFIG.read_text(encoding="utf-8") + (FIRMWARE / "stm32" / "App" / "tracker.h").read_text(encoding="utf-8")
    for m in re.finditer(r"^#define\s+([A-Z_0-9]+)\s+\(?(-?\d+)u?\)?", text, re.M):
        cfg[m.group(1)] = int(m.group(2))
    cfg.update(defines or {})
    return {k: cfg[k] for k in CONFIG_KEYS}


def find_gcc() -> Path | None:
    which = shutil.which("gcc") or shutil.which("cc")
    if which:
        return Path(which)
    return MSYS_GCC if MSYS_GCC.exists() else None


def _env_for(gcc: Path) -> dict:
    env = dict(os.environ)
    env["PATH"] = str(gcc.parent) + os.pathsep + env.get("PATH", "")  # the compiler's DLLs live next to it
    return env


def build_trace_tool(out_dir: Path, gcc: Path | None = None, defines: dict[str, int] | None = None) -> Path:
    gcc = gcc or find_gcc()
    if gcc is None:
        raise RuntimeError("no C compiler: install MSYS2 (C:/msys64) or put gcc on PATH")
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = "_".join(f"{k}{v}" for k, v in sorted((defines or {}).items()))
    exe = out_dir / f"trace_tool{('_' + tag) if tag else ''}.exe"
    cmd = [str(gcc), "-std=c11", "-O1", "-Wall", "-Wextra", f"-I{FIRMWARE / 'common'}", f"-I{FIRMWARE / 'stm32' / 'App'}",
           *[f"-D{k}={v}" for k, v in (defines or {}).items()],
           *[str(FIRMWARE / s) for s in TRACE_SOURCES], "-o", str(exe)]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=_env_for(gcc))
    if proc.returncode != 0:
        raise RuntimeError("trace tool build failed:\n" + proc.stdout + proc.stderr)
    return exe


def gt_to_trace(gt: dict[int, list[GTBox]], width: int, height: int, fps: float, max_frames: int | None = None,
                max_boxes: int = 8, score: int = 90) -> list[tuple[int, list[Detection]]]:
    """Ground-truth boxes as a detection stream: (time_ms, detections) per frame, boxes in id order."""
    frames = sorted(gt)
    if max_frames:
        frames = frames[:max_frames]
    out = []
    for fr in frames:
        t = int(round((fr - 1) * 1000.0 / fps))
        dets = []
        for b in sorted(gt[fr], key=lambda b: b.track_id)[:max_boxes]:
            cx, cy = (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2
            dets.append(Detection(int(round(cx / width * 1000)), int(round(cy / height * 1000)),
                                  int(round((b.x2 - b.x1) / width * 1000)), int(round((b.y2 - b.y1) / height * 1000)), score))
        out.append((t, dets))
    return out


def trace_text(stream: list[tuple[int, list[Detection]]]) -> str:
    lines = []
    for t, dets in stream:
        parts = [str(t), str(len(dets))]
        for d in dets:
            parts += [str(d.cx), str(d.cy), str(d.w), str(d.h), str(d.score)]
        lines.append(" ".join(parts))
    return "\n".join(lines) + "\n"


def run_python(stream: list[tuple[int, list[Detection]]], defines: dict[str, int] | None = None) -> list[str]:
    c = firmware_config(defines)
    tracker = NearestTracker(match_dist=c["TRACK_MATCH_DIST"], drop_ms=c["TRACK_DROP_MS"], max_tracks=c["TRACK_MAX"])
    linger = LingerDetector(c["LINGER_RADIUS"], c["LINGER_TIME_MS"], c["TRACK_MAX"],
                            require_motion=bool(c["LINGER_REQUIRE_MOTION"]), min_score=c["LINGER_MIN_SCORE"])
    out = []
    for t, dets in stream:
        tracks = tracker.update(dets, t)
        lid = linger.update(tracks, t)
        out.append(f"{t} L={lid}" + "".join(f" {tr.id}:{int(tr.cx)}:{int(tr.cy)}:{tr.vx}" for tr in tracks))
    return out


def run_c(exe: Path, stream: list[tuple[int, list[Detection]]]) -> list[str]:
    proc = subprocess.run([str(exe)], input=trace_text(stream), capture_output=True, text=True, env=_env_for(exe))
    if proc.returncode != 0:
        raise RuntimeError("trace tool failed: " + proc.stderr)
    return proc.stdout.strip().splitlines()


def compare(exe: Path, stream: list[tuple[int, list[Detection]]], defines: dict[str, int] | None = None) -> dict:
    c_lines, py_lines = run_c(exe, stream), run_python(stream, defines)
    mismatches = [(i, c, p) for i, (c, p) in enumerate(zip(c_lines, py_lines)) if c != p]
    linger_c = sum(1 for ln in c_lines if " L=0" not in ln)
    return {"frames": len(stream), "c_lines": len(c_lines), "py_lines": len(py_lines), "mismatches": mismatches,
            "linger_reports": linger_c, "identical": not mismatches and len(c_lines) == len(py_lines) == len(stream)}
