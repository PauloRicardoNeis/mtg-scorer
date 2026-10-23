"""The weekly job summary reads each mutation tool's report into one table."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/mutation_summary.py"


@pytest.fixture(scope="module")
def summary():
    spec = importlib.util.spec_from_file_location("mutation_summary", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # Dataclasses resolve their module through sys.modules while the class is created.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_each_tool_report_is_read_and_scored_the_same_way(summary, tmp_path, capsys) -> None:
    mutmut = tmp_path / "mutmut-cicd-stats.json"
    mutmut.write_text(
        json.dumps({"total": 10, "killed": 6, "timeout": 1, "survived": 2, "no_tests": 1}),
        encoding="utf-8",
    )
    pit = tmp_path / "mutations.xml"
    pit.write_text(
        "<mutations>"
        + "".join(
            f"<mutation status='{status}'><mutatedClass>c</mutatedClass></mutation>"
            for status in ("KILLED", "KILLED", "TIMED_OUT", "SURVIVED", "NO_COVERAGE", "RUN_ERROR")
        )
        + "</mutations>",
        encoding="utf-8",
    )
    stryker = tmp_path / "mutation.json"
    stryker.write_text(
        json.dumps(
            {
                "files": {
                    "a.ts": {"mutants": [{"status": s} for s in ("Killed", "Timeout", "Survived")]},
                    "b.ts": {"mutants": [{"status": s} for s in ("NoCoverage", "Ignored")]},
                }
            }
        ),
        encoding="utf-8",
    )

    exit_code = summary.main(
        ["--mutmut", str(mutmut), "--pit", str(pit), "--stryker", str(stryker)]
    )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert out.startswith("## Mutation scores")
    # Timeouts count as killed; "no tests" and "no coverage" count as tested, not killed.
    assert "| Python (analytics core) | mutmut | 70.0% | 7 | 2 | 1 | 0 |" in out
    assert "| Java (api) | PIT | 60.0% | 3 | 1 | 1 | 1 |" in out
    assert "| Web (lib, components, i18n) | Stryker | 50.0% | 2 | 1 | 1 | 1 |" in out


def test_a_missing_report_is_reported_and_the_rest_still_summarized(summary, tmp_path, capsys):
    stryker = tmp_path / "mutation.json"
    stryker.write_text(json.dumps({"files": {}}), encoding="utf-8")

    exit_code = summary.main(["--pit", str(tmp_path / "absent.xml"), "--stryker", str(stryker)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "missing report" in captured.err
    assert "| Web (lib, components, i18n) | Stryker | n/a | 0 | 0 | 0 | 0 |" in captured.out


def test_no_report_at_all_is_a_failure(summary, tmp_path, capsys) -> None:
    assert summary.main(["--mutmut", str(tmp_path / "none.json")]) == 1
    assert "no mutation report found" in capsys.readouterr().err
