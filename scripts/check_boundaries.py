"""Fail CI when implemented module dependencies cross the accepted product boundary."""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    failures = []
    package = ROOT / "analytics/src/mtg_scorer"
    for file in [package / name for name in ("domain.py", "features.py", "scoring.py")]:
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            if any(
                re.search(
                    r"(^|\.)(ingest|publish|requests|urllib|psycopg|duckdb|subprocess|pathlib)(\.|$)",
                    name,
                )
                for name in names
            ):
                failures.append(f"{file.name}: domain/analytical core imports an I/O adapter")
    for file in (package / "normalize").glob("*.py"):
        if re.search(
            r"(?:from|import) mtg_scorer\.(publish|ingest)",
            file.read_text(encoding="utf-8"),
        ):
            failures.append(f"{file.name}: normalization depends on I/O orchestration")
    java_root = ROOT / "api/src/main/java/io/mtgscorer/api"
    dependencies: dict[str, set[str]] = {}
    for file in java_root.rglob("*.java"):
        source = file.read_text(encoding="utf-8")
        owner = file.relative_to(java_root).parts[0]
        for dependency, entry in re.findall(
            r"import (?:static )?io\.mtgscorer\.api\.(\w+)\.(\w+)", source
        ):
            if dependency != owner:
                dependencies.setdefault(owner, set()).add(dependency)
            if owner == "catalog" and dependency == "snapshots" and entry != "SnapshotService":
                failures.append(f"{file.name}: catalog must use the public snapshot resolver")
            if owner == "snapshots" and dependency == "catalog":
                failures.append(f"{file.name}: snapshot module depends on catalog internals")
        if re.search(
            r"ProcessBuilder|java\.net\.(http|URL|URLConnection)|Runtime\.getRuntime|mtg_scorer|read_parquet|buildaround_signal",
            source,
        ):
            failures.append(f"{file.name}: Java request path invokes ingestion/analytical work")

    def visit(module: str, path: set[str]) -> None:
        if module in path:
            failures.append(f"Java module cycle: {module}")
            return
        for dependency in dependencies.get(module, set()):
            visit(dependency, path | {module})

    for module in dependencies:
        visit(module, set())
    for file in (ROOT / "web/src").rglob("*"):
        if file.suffix not in {".ts", ".tsx"} or file.name == "api.generated.ts":
            continue
        source = file.read_text(encoding="utf-8")
        if "api.generated" in source and file.name != "api.ts":
            failures.append(f"{file.name}: generated DTOs must enter through lib/api.ts")
        if re.search(
            r"(?:fetch|axios)\([^\n]*(?:scryfall|topdeck)|"
            r"from [\"'](?:pg|duckdb|child_process|node:child_process)",
            source,
        ):
            failures.append(f"{file.name}: web request path bypasses the Java product API")
    if failures:
        raise SystemExit("\n".join(failures))
    print(
        "Dependency boundaries passed: Python core/normalization, "
        "acyclic Java capabilities, web API entry."
    )


if __name__ == "__main__":
    main()
