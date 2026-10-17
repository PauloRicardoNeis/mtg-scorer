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


@pytest.mark.parametrize("seed_sample", [False, True])
def test_up_only_publishes_when_sample_was_explicitly_requested(monkeypatch, tmp_path, seed_sample):
    from contextlib import contextmanager
    from types import SimpleNamespace

    script = Path(__file__).resolve().parents[2] / "scripts/demo.py"
    spec = importlib.util.spec_from_file_location("demo_startup", script)
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    seeds, waits = [], []

    @contextmanager
    def server(*args):
        yield SimpleNamespace(poll=lambda: 1)

    class Socket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def connect_ex(self, address):
            return 1

    monkeypatch.setattr(demo, "LOCAL", tmp_path)
    monkeypatch.setattr(demo, "postgres_admin_dsn", lambda: "local")
    monkeypatch.setattr(demo, "database", lambda *args: {})
    monkeypatch.setattr(demo, "grant_runtime_roles", lambda *args: None)
    monkeypatch.setattr(demo, "java", lambda: "java")
    monkeypatch.setattr(demo, "server", server)
    monkeypatch.setattr(demo.shutil, "copyfile", lambda *args: None)
    monkeypatch.setattr(demo.socket, "socket", Socket)
    monkeypatch.setattr(demo, "wait_http", lambda url, _: waits.append(url))
    monkeypatch.setattr(demo, "seed", lambda *args: seeds.append(True))
    with pytest.raises(RuntimeError, match="local server stopped"):
        demo.serve_and_verify(SimpleNamespace(command="up", seed_sample=seed_sample))
    assert seeds == ([True] if seed_sample else [])
    assert any("readiness" in url for url in waits) == seed_sample
