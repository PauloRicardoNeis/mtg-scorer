"""Cross-platform local catalog setup and deterministic verification. Run from any directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
PYTHON = Path(os.environ.get("UV_PROJECT_ENVIRONMENT", ROOT / "analytics/.venv")) / (
    "Scripts/python.exe" if os.name == "nt" else "bin/python"
)
SEED = ROOT / "analytics/seeds/scryfall-layouts-v1"
PG_URL = "https://get.enterprisedb.com/postgresql/postgresql-17.11-3-windows-x64-binaries.zip"
PG_HASH = "4b8db0930c38f6ef845db919551dedda3b6b845aeb0927b3d79a6e8e9e4537cf"


def run(arguments: list[str | Path], *, env: dict[str, str] | None = None) -> None:
    subprocess.run([str(value) for value in arguments], cwd=ROOT, env=env, check=True)


def java() -> Path:
    executable = (
        Path(os.environ.get("JAVA_HOME", "")) / "bin" / ("java.exe" if os.name == "nt" else "java")
    )
    if not executable.is_file():
        raise RuntimeError("Set JAVA_HOME to a JDK 21 installation before running this command.")
    return executable


def maven(*arguments: str) -> None:
    java()
    command = [ROOT / "api/mvnw.cmd"] if os.name == "nt" else ["bash", ROOT / "api/mvnw"]
    run(
        [
            *command,
            "-f",
            ROOT / "api/pom.xml",
            "--batch-mode",
            "--no-transfer-progress",
            *arguments,
        ]
    )


def install() -> None:
    run([sys.executable, "-m", "pip", "install", "uv==0.8.22"])
    run(
        [
            sys.executable,
            "-m",
            "uv",
            "sync",
            "--project",
            ROOT / "analytics",
            "--locked",
            "--extra",
            "dev",
        ]
    )
    npm = "npm.cmd" if os.name == "nt" else "npm"
    run([npm, "--prefix", ROOT / "web", "ci", "--no-audit", "--no-fund"])
    run(["node", ROOT / "web/node_modules/playwright/cli.js", "install", "chromium"])


def postgres_admin_dsn() -> str:
    """Use a supplied local service, native PostgreSQL, or verified portable Windows binaries."""
    if os.environ.get("CATALOG_ADMIN_DSN"):
        return os.environ["CATALOG_ADMIN_DSN"]
    import psycopg

    dsn = "host=127.0.0.1 port=55432 user=postgres dbname=postgres connect_timeout=2"
    try:
        with psycopg.connect(dsn):
            return dsn
    except psycopg.OperationalError:
        pass
    configured = os.environ.get("POSTGRES_BIN")
    pg_bin = Path(configured) if configured else LOCAL / "tools/postgresql-17.11/pgsql/bin"
    suffix = ".exe" if os.name == "nt" else ""
    if not (pg_bin / f"initdb{suffix}").exists():
        available = shutil.which("initdb")
        if available:
            pg_bin = Path(available).parent
        elif os.name == "nt" and configured is None:
            LOCAL.joinpath("tools").mkdir(parents=True, exist_ok=True)
            archive = LOCAL / "tools/postgresql-17.11.zip"
            if not archive.exists():
                temporary = archive.with_suffix(".download")
                with (
                    urllib.request.urlopen(PG_URL, timeout=60) as response,
                    temporary.open("wb") as output,
                ):
                    shutil.copyfileobj(response, output)
                if hashlib.file_digest(temporary.open("rb"), "sha256").hexdigest() != PG_HASH:
                    raise RuntimeError(
                        "PostgreSQL archive checksum mismatch; no binaries were executed."
                    )
                temporary.rename(archive)
            with archive.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != PG_HASH:
                    raise RuntimeError("PostgreSQL archive checksum mismatch.")
            with zipfile.ZipFile(archive) as zipped:
                zipped.extractall(LOCAL / "tools/postgresql-17.11")
        else:
            raise RuntimeError(
                "Provide PostgreSQL 17 via POSTGRES_BIN or CATALOG_ADMIN_DSN "
                "(see docs/local-catalog.md)."
            )
    data = LOCAL / "postgres-data"
    if not (data / "PG_VERSION").exists():
        run(
            [
                pg_bin / f"initdb{suffix}",
                "-D",
                data,
                "-U",
                "postgres",
                "--auth=trust",
                "--encoding=UTF8",
                "--locale=C",
            ]
        )
    # A persistent Windows postgres child must not inherit the caller's output pipe.
    # Otherwise PowerShell waits for that pipe even after verification has completed.
    with (LOCAL / "postgres-start.log").open("w", encoding="utf-8") as startup_log:
        subprocess.run(
            [
                str(value)
                for value in [
                    pg_bin / f"pg_ctl{suffix}",
                    "-D",
                    data,
                    "-l",
                    LOCAL / "postgres.log",
                    "-o",
                    "-h 127.0.0.1 -p 55432",
                    "start",
                ]
            ],
            cwd=ROOT,
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=startup_log,
            stderr=subprocess.STDOUT,
            close_fds=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    return dsn


def database(admin: str, name: str) -> dict[str, str]:
    import psycopg
    from psycopg import sql

    with psycopg.connect(admin, autocommit=True) as connection:
        for role in ("catalog_api_local", "catalog_publisher_local"):
            if not connection.execute(
                "SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)
            ).fetchone():
                connection.execute(
                    sql.SQL("CREATE ROLE {} LOGIN PASSWORD 'local-catalog-only'").format(
                        sql.Identifier(role)
                    )
                )
        if not connection.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone():
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    parts = psycopg.conninfo.conninfo_to_dict(admin)
    env = os.environ.copy()
    host, port = parts.get("host", "127.0.0.1"), parts.get("port", "5432")
    env.update(
        {
            "CATALOG_JDBC_URL": f"jdbc:postgresql://{host}:{port}/{name}",
            "CATALOG_DB_USER": "catalog_api_local",
            "CATALOG_DB_PASSWORD": "local-catalog-only",
            "CATALOG_MIGRATE": "true",
            "CATALOG_MIGRATION_USER": parts.get("user", "postgres"),
            "CATALOG_MIGRATION_PASSWORD": parts.get("password", ""),
            "CATALOG_TEST_ADMIN_DSN": psycopg.conninfo.make_conninfo(admin, dbname=name),
            "CATALOG_TEST_PUBLISH_DSN": psycopg.conninfo.make_conninfo(
                admin,
                dbname=name,
                user="catalog_publisher_local",
                password="local-catalog-only",
            ),
            "TEST_DATABASE_DSN": psycopg.conninfo.make_conninfo(admin, dbname=name),
            "CATALOG_TEST_PYTHON": str(PYTHON),
            "NEXT_TELEMETRY_DISABLED": "1",
        }
    )
    return env


def grant_runtime_roles(admin: str) -> None:
    import psycopg

    with psycopg.connect(admin) as connection:
        connection.execute("GRANT catalog_reader TO catalog_api_local")
        connection.execute("GRANT catalog_publisher TO catalog_publisher_local")


@contextmanager
def server(command: list[str | Path], env: dict[str, str], log: Path):
    with log.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            [str(value) for value in command],
            cwd=ROOT,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            yield process
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def wait_http(url: str, process: subprocess.Popen, timeout: float = 45) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Local server exited; inspect the named log in .local/.")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for local server at {url}; inspect .local logs.")


def seed(env: dict[str, str], output_root: Path) -> Path:
    import psycopg
    from mtg_scorer.publish.artifact import export_catalog
    from mtg_scorer.publish.postgres import publish_catalog, rollback_catalog

    artifact = export_catalog(SEED, output_root, created_at="2026-09-08T00:46:15Z")
    result = publish_catalog(artifact, SEED, env["CATALOG_TEST_PUBLISH_DSN"])
    with psycopg.connect(env["CATALOG_TEST_PUBLISH_DSN"]) as connection:
        active = connection.execute(
            "SELECT catalog_snapshot_id FROM catalog.active_catalog"
        ).fetchone()[0]
    if active != artifact.name:
        rollback_catalog(env["CATALOG_TEST_PUBLISH_DSN"], artifact.name, active)
    print(json.dumps(result), flush=True)
    return artifact


def serve_and_verify(args: argparse.Namespace) -> None:
    admin = postgres_admin_dsn()
    verify = args.command == "verify"
    name = "mtg_verify_" + uuid4().hex[:12] if verify else "mtg_catalog_demo"
    env = database(admin, name)
    api_port = "18081" if verify else "18080"
    web_port = "3301" if verify else "3300"
    for port in (api_port, web_port):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", int(port))) == 0:
                raise RuntimeError(
                    f"Port {port} is already in use. "
                    "Stop that local preview before starting this run."
                )
    api_url, web_url = f"http://127.0.0.1:{api_port}", f"http://127.0.0.1:{web_port}"
    env.update(
        SERVER_PORT=api_port,
        CATALOG_API_URL=api_url,
        CATALOG_TEST_API_URL=api_url,
        WEB_TEST_URL=web_url,
    )
    run_dir = LOCAL / name
    run_dir.mkdir(parents=True, exist_ok=True)
    runtime_jar = run_dir / ("api-" + uuid4().hex[:8] + ".jar")
    shutil.copyfile(ROOT / "api/target/mtg-scorer-api-0.1.0-SNAPSHOT.jar", runtime_jar)
    with server(
        [java(), "-jar", runtime_jar],
        env,
        run_dir / "api.log",
    ) as api_process:
        wait_http(api_url + "/actuator/health/liveness", api_process)
        grant_runtime_roles(admin)
        if verify:
            run([PYTHON, ROOT / "scripts/api_contract.py", "--url", api_url], env=env)
            run(
                [
                    PYTHON,
                    "-m",
                    "pytest",
                    "analytics/tests/test_catalog_http.py",
                    "-q",
                    "-k",
                    "initial_catalog",
                ],
                env={**env, "CATALOG_TEST_EMPTY": "1"},
            )
            print("Checkpoint: real PostgreSQL publication and failure tests", flush=True)
            run(
                [
                    PYTHON,
                    "-m",
                    "pytest",
                    "analytics/tests/test_postgres_publication.py",
                    "-q",
                ],
                env=env,
            )
        artifact = seed(env, run_dir / "catalog")
        wait_http(api_url + "/actuator/health/readiness", api_process)
        if verify:
            print(
                "Checkpoint: Python -> PostgreSQL -> Java contracts and refresh",
                flush=True,
            )
            run(
                [PYTHON, "-m", "pytest", "analytics/tests/test_catalog_http.py", "-q"],
                env=env,
            )
        with server(
            [
                "node",
                ROOT / "web/node_modules/next/dist/bin/next",
                "start",
                ROOT / "web",
                "--hostname",
                "127.0.0.1",
                "--port",
                web_port,
            ],
            env,
            run_dir / "web.log",
        ) as web_process:
            wait_http(web_url + "/", web_process)
            if verify:
                run(
                    [
                        "npm.cmd" if os.name == "nt" else "npm",
                        "--prefix",
                        ROOT / "web",
                        "run",
                        "test:e2e",
                    ],
                    env=env,
                )
                run(
                    [
                        PYTHON,
                        ROOT / "scripts/measure_catalog.py",
                        "--artifact",
                        artifact,
                        "--output",
                        run_dir / "measurements.json",
                    ],
                    env=env,
                )
                print(
                    f"Verification passed. Evidence and retained disposable database: {run_dir}",
                    flush=True,
                )
            else:
                print(
                    f"Catalog ready: {web_url}/cards | API: {api_url}/swagger-ui.html\n"
                    f"Logs: {run_dir}\nCtrl+C stops these API/web processes; "
                    "PostgreSQL and immutable data are retained.",
                    flush=True,
                )
                while api_process.poll() is None and web_process.poll() is None:
                    time.sleep(1)
                raise RuntimeError("A local server stopped; inspect logs.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["install", "up", "verify"])
    parser.add_argument(
        "--skip-install", action="store_true", help="Use existing locked dependencies"
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Use existing verified Java/web builds",
    )
    args = parser.parse_args()
    LOCAL.mkdir(exist_ok=True)
    os.chdir(ROOT)
    os.environ["NEXT_TELEMETRY_DISABLED"] = "1"
    if not args.skip_install:
        install()
    if args.command == "install":
        return
    # POSIX virtualenv executables can resolve to the global Python binary.
    # Compare environment roots so imports use the installed project dependencies.
    if Path(sys.prefix).resolve() != PYTHON.parent.parent.resolve():
        run(
            [
                PYTHON,
                Path(__file__),
                args.command,
                "--skip-install",
                *(["--skip-build"] if args.skip_build else []),
            ]
        )
        return
    if not args.skip_build:
        print("Checkpoint: Python/language checks and production builds", flush=True)
        run([PYTHON, "-m", "ruff", "check", "analytics", "scripts"])
        run([PYTHON, "-m", "ruff", "format", "--check", "analytics", "scripts"])
        run([PYTHON, "-m", "pytest", "analytics/tests", "-q"])
        run([PYTHON, "scripts/verify_contracts.py"])
        run([PYTHON, "scripts/check_boundaries.py"])
        maven("verify")
        npm = "npm.cmd" if os.name == "nt" else "npm"
        run([npm, "--prefix", "web", "run", "format:check"])
        run([npm, "--prefix", "web", "run", "build"])
        run([npm, "--prefix", "web", "run", "typecheck"])
    serve_and_verify(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Local API and web stopped.")
