"""The ST Edge AI Core wrapper: find the compiler, build the STM32N6 command, file the reports.

A stub `stedgeai.cmd` stands in for the real compiler so these run without the install."""

from pathlib import Path

import pytest

from herd_ai import stedgeai

STUB = "\n".join([
    "@echo off",
    "if \"%1\"==\"--version\" (echo stedgeai - STM32 Edge AI Core stub 9.9.9 & exit /b 0)",
    "echo args: %* > \"%STUB_LOG%\"",
    "set OUT=.",
    ":loop",
    "if \"%1\"==\"\" goto done",
    "if \"%1\"==\"--output\" set OUT=%2",
    "shift",
    "goto loop",
    ":done",
    "if not exist \"%OUT%\" mkdir \"%OUT%\"",
    "cd /d \"%OUT%\"",
    "echo Exec/report summary (analyze) > network_analyze_report.txt",
    "echo   est. inference time : 7.00 ms >> network_analyze_report.txt",
    "echo generated > network.c",
    "exit /b 0",
    "",
])


@pytest.fixture
def stub(tmp_path: Path, monkeypatch):
    home = tmp_path / "STEdgeAI" / "9.9.9" / "Utilities" / "windows"
    home.mkdir(parents=True)
    exe = home / "stedgeai.cmd"
    exe.write_text(STUB, encoding="ascii")
    monkeypatch.setenv("STUB_LOG", str(tmp_path / "args.txt"))
    monkeypatch.setenv("STEDGEAI_HOME", str(tmp_path / "STEdgeAI" / "9.9.9"))
    monkeypatch.delenv("PATH", raising=False)
    return exe


def test_find_uses_the_env_var_first(stub: Path, tmp_path: Path):
    assert stedgeai.find_stedgeai() == stub


def test_find_scans_the_default_install_root_newest_version_first(stub: Path, tmp_path: Path, monkeypatch):
    monkeypatch.delenv("STEDGEAI_HOME")
    root = tmp_path / "STEdgeAI"
    older = root / "4.0.0" / "Utilities" / "windows"
    older.mkdir(parents=True)
    (older / "stedgeai.cmd").write_text(STUB, encoding="ascii")
    assert stedgeai.find_stedgeai(roots=[root]) == stub  # 9.9.9 beats 4.0.0


def test_find_returns_none_when_nothing_is_installed(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("STEDGEAI_HOME", raising=False)
    monkeypatch.delenv("PATH", raising=False)
    assert stedgeai.find_stedgeai(roots=[tmp_path / "nowhere"]) is None


def test_command_targets_the_n6_npu_with_the_model_zoo_flags(tmp_path: Path):
    cmd = stedgeai.build_command(Path("tool.exe"), "generate", Path("m.tflite"), tmp_path / "out", neural_art="default@ua.json")
    assert cmd[:2] == ["tool.exe", "generate"]
    assert cmd[cmd.index("--model") + 1] == "m.tflite"
    assert cmd[cmd.index("--target") + 1] == "stm32n6"
    assert cmd[cmd.index("--st-neural-art") + 1] == "default@ua.json"
    assert cmd[cmd.index("--output") + 1] == str(tmp_path / "out")
    assert "--name" in cmd and cmd[cmd.index("--name") + 1] == "network"


def test_command_without_a_profile_passes_the_bare_flag(tmp_path: Path):
    cmd = stedgeai.build_command(Path("tool.exe"), "analyze", Path("m.tflite"), tmp_path)
    i = cmd.index("--st-neural-art")
    assert i == len(cmd) - 1 or cmd[i + 1].startswith("--")


def test_run_writes_log_and_files_the_reports(stub: Path, tmp_path: Path):
    model = tmp_path / "yolo_256.tflite"
    model.write_bytes(b"\x00")
    res = stedgeai.run(stub, "analyze", model, tmp_path / "work", results_dir=tmp_path / "results")
    assert res.returncode == 0
    assert (tmp_path / "work" / "network.c").exists(), "generated files stay in the work dir"
    filed = tmp_path / "results" / "yolo_256"
    assert (filed / "network_analyze_report.txt").read_text().lstrip().startswith("Exec/report summary")
    assert "analyze" in (filed / "analyze.log").read_text()
    assert "--target stm32n6" in (tmp_path / "args.txt").read_text()


def test_version_string_comes_from_the_tool(stub: Path):
    assert "9.9.9" in stedgeai.version(stub)
