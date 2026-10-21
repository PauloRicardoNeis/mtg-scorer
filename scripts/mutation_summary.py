"""Summarize mutation-testing reports as one Markdown table, for the weekly job summary.

Reads whichever reports exist: mutmut's ``mutants/mutmut-cicd-stats.json``, PIT's
``mutations.xml`` and Stryker's ``mutation.json``. The score is the share of mutants the
tests killed (timeouts count as killed) among those that were tested, which is how each
tool defines it. Exit code 0 whenever at least one report was read.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree


@dataclass(frozen=True)
class Summary:
    layer: str
    tool: str
    killed: int
    survived: int
    no_coverage: int
    other: int

    @property
    def tested(self) -> int:
        return self.killed + self.survived + self.no_coverage

    @property
    def score(self) -> float | None:
        return None if not self.tested else 100 * self.killed / self.tested


def mutmut_summary(path: Path) -> Summary:
    """mutmut's CI/CD stats: killed and timeouts count as killed, "no tests" as uncovered."""

    stats = json.loads(path.read_text(encoding="utf-8"))
    killed = int(stats.get("killed", 0)) + int(stats.get("timeout", 0))
    survived = int(stats.get("survived", 0))
    no_tests = int(stats.get("no_tests", 0) or stats.get("no tests", 0))
    other = int(stats.get("suspicious", 0)) + int(stats.get("skipped", 0))
    return Summary("Python (analytics core)", "mutmut", killed, survived, no_tests, other)


def pit_summary(path: Path) -> Summary:
    """PIT's mutations.xml: one <mutation status=...> element per mutant."""

    statuses = Counter(
        element.get("status", "")
        for element in ElementTree.parse(path).getroot().iter("mutation")  # noqa: S314 -- PIT's own report
    )
    killed = statuses["KILLED"] + statuses["TIMED_OUT"]
    survived = statuses["SURVIVED"]
    no_coverage = statuses["NO_COVERAGE"]
    other = sum(statuses.values()) - killed - survived - no_coverage
    return Summary("Java (api)", "PIT", killed, survived, no_coverage, other)


def stryker_summary(path: Path) -> Summary:
    """Stryker's mutation.json (mutation-testing-report-schema): files -> mutants[] -> status."""

    report = json.loads(path.read_text(encoding="utf-8"))
    statuses = Counter(
        mutant["status"] for file in report["files"].values() for mutant in file["mutants"]
    )
    killed = statuses["Killed"] + statuses["Timeout"]
    survived = statuses["Survived"]
    no_coverage = statuses["NoCoverage"]
    other = sum(statuses.values()) - killed - survived - no_coverage
    return Summary("Web (lib, components, i18n)", "Stryker", killed, survived, no_coverage, other)


def markdown(summaries: list[Summary]) -> str:
    lines = [
        "| Layer | Tool | Score | Killed | Survived | No coverage | Other |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for s in summaries:
        score = "n/a" if s.score is None else f"{s.score:.1f}%"
        lines.append(
            f"| {s.layer} | {s.tool} | {score} | {s.killed} | {s.survived} | "
            f"{s.no_coverage} | {s.other} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mutmut", type=Path, help="mutants/mutmut-cicd-stats.json")
    parser.add_argument("--pit", type=Path, help="target/pit-reports/mutations.xml")
    parser.add_argument("--stryker", type=Path, help="reports/mutation/mutation.json")
    parser.add_argument("--title", default="## Mutation scores")
    args = parser.parse_args(argv)
    summaries = []
    for path, reader in (
        (args.mutmut, mutmut_summary),
        (args.pit, pit_summary),
        (args.stryker, stryker_summary),
    ):
        if path is None:
            continue
        if not path.is_file():
            print(f"missing report: {path}", file=sys.stderr)
            continue
        summaries.append(reader(path))
    if not summaries:
        print("no mutation report found", file=sys.stderr)
        return 1
    print(args.title)
    print()
    print(markdown(summaries), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
