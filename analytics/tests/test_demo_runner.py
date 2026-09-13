"""The demo must enter its environment even when Python executables share a target."""

import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize("in_project_environment", [False, True])
def test_runner_selects_environment_by_prefix(monkeypatch, tmp_path, in_project_environment):
    script = Path(__file__).resolve().parents[2] / "scripts/demo.py"
    spec = importlib.util.spec_from_file_location("demo_runner", script)
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)

    environment = tmp_path / "project-venv"
    executable = environment / "bin/python"
    commands = []
    served = []
    monkeypatch.setattr(demo, "PYTHON", executable)
    monkeypatch.setattr(demo, "LOCAL", tmp_path / "local")
    monkeypatch.setattr(demo, "ROOT", tmp_path)
    monkeypatch.setattr(demo, "run", lambda arguments: commands.append(arguments))
    monkeypatch.setattr(demo, "serve_and_verify", lambda args: served.append(args.command))
    monkeypatch.setattr(demo.os, "chdir", lambda path: None)
    # Matching binary paths do not establish that the virtualenv is active.
    monkeypatch.setattr(demo.sys, "executable", str(executable))
    prefix = environment if in_project_environment else tmp_path / "global-python"
    monkeypatch.setattr(demo.sys, "prefix", str(prefix))
    monkeypatch.setattr(demo.sys, "argv", [str(script), "verify", "--skip-install", "--skip-build"])
    monkeypatch.setenv("NEXT_TELEMETRY_DISABLED", "1")

    demo.main()

    if in_project_environment:
        assert commands == []
        assert served == ["verify"]
    else:
        assert commands == [[executable, script, "verify", "--skip-install", "--skip-build"]]
        assert served == []
