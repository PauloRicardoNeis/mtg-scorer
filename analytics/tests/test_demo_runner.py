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
    monkeypatch.setattr(demo, "run", commands.append)
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


def _load_runner(name):
    script = Path(__file__).resolve().parents[2] / "scripts/demo.py"
    spec = importlib.util.spec_from_file_location(name, script)
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    return script, demo


@pytest.mark.parametrize(
    ("only", "in_project_environment", "expected"),
    [
        # Java- and web-only checks need no project Python: no re-exec, the scripts in order.
        (["web"], False, "web"),
        # Python-side checks enter the environment first and keep the selection.
        (["contracts", "python"], False, "reexec"),
        # Inside the environment the layers run in their fixed order, whatever the selection.
        (["contracts", "python"], True, "python-then-contracts"),
    ],
)
def test_check_runs_only_the_selected_layers(
    monkeypatch, tmp_path, only, in_project_environment, expected
):
    script, demo = _load_runner("demo_check")
    environment = tmp_path / "project-venv"
    executable = environment / "bin/python"
    commands, served = [], []
    monkeypatch.setattr(demo, "PYTHON", executable)
    monkeypatch.setattr(demo, "LOCAL", tmp_path / "local")
    monkeypatch.setattr(demo, "COVERAGE_DIR", tmp_path / "local/coverage/python")
    monkeypatch.setattr(demo, "COVERAGE_DATA", tmp_path / "local/coverage/python/.coverage")
    monkeypatch.setattr(demo, "JUNIT", tmp_path / "local/junit")
    monkeypatch.setattr(demo, "ROOT", tmp_path)

    def record(arguments, *, env=None):
        commands.append(arguments)

    monkeypatch.setattr(demo, "run", record)
    monkeypatch.setattr(demo, "serve_and_verify", lambda args: served.append(args.command))
    monkeypatch.setattr(demo.os, "chdir", lambda path: None)
    prefix = environment if in_project_environment else tmp_path / "global-python"
    monkeypatch.setattr(demo.sys, "prefix", str(prefix))
    monkeypatch.setattr(demo.sys, "argv", [str(script), "check", "--only", *only])

    demo.main()

    assert served == []
    if expected == "web":
        scripts = ["format:check", "lint", "test:unit", "build", "typecheck"]
        assert commands == [[demo.NPM, "--prefix", "web", "run", name] for name in scripts]
    elif expected == "reexec":
        assert commands == [[executable, script, "check", "--skip-install", "--only", *only]]
    else:
        assert [command[1:3] for command in commands[:3]] == [
            ["-m", "ruff"],
            ["-m", "ruff"],
            ["-m", "pyright"],
        ]
        offline = commands[3]
        assert offline[:3] == [executable, "-m", "pytest"]
        assert "--cov-append" not in offline
        assert any(str(argument).endswith("pytest-offline.xml") for argument in offline)
        assert [command[1] for command in commands[4:]] == [
            "scripts/verify_contracts.py",
            "scripts/check_boundaries.py",
        ]


def test_database_stages_append_coverage_only_when_the_offline_data_exists(monkeypatch, tmp_path):
    _, demo = _load_runner("demo_stages")
    commands = []
    monkeypatch.setattr(
        demo, "run", lambda arguments, *, env=None: commands.append((arguments, env))
    )
    monkeypatch.setattr(demo, "JUNIT", tmp_path / "junit")
    monkeypatch.setattr(demo, "COVERAGE_DIR", tmp_path)
    monkeypatch.setattr(demo, "COVERAGE_DATA", tmp_path / ".coverage")

    demo.pytest_stage("http", ["analytics/tests/test_x.py"], {"A": "1"}, "-k", "x")
    demo.report_coverage({"A": "1"})
    assert len(commands) == 1
    without, env = commands[0]
    assert "--cov-append" not in without
    assert without[-2:] == ["-k", "x"]
    assert any(str(argument).endswith("pytest-http.xml") for argument in without)
    assert env == {"A": "1", "COVERAGE_FILE": str(tmp_path / ".coverage")}
    assert (tmp_path / "junit").is_dir()

    (tmp_path / ".coverage").write_bytes(b"")
    demo.pytest_stage("http", ["analytics/tests/test_x.py"], {"A": "1"})
    demo.report_coverage({"A": "1"})
    appended = commands[1][0]
    assert "--cov-append" in appended
    assert "--cov-fail-under=0" in appended
    assert "--cov-report=" in appended
    # Reports first, floor last: a red run still ships its XML and HTML.
    assert [command[0][2:4] for command in commands[2:]] == [
        ["coverage", "xml"],
        ["coverage", "html"],
        ["coverage", "report"],
    ]
    assert all("--fail-under=0" in command[0] for command in commands[2:4])
    assert "--fail-under=0" not in commands[4][0]
    assert all(env["COVERAGE_FILE"] == str(tmp_path / ".coverage") for _, env in commands)
