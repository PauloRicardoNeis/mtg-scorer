# Quality assurance and testing

Test and QA documentation for the whole repository: the Python analytics
application, the Java API, the Next.js web application, the shared contracts, the
scripts that tie them together and the CI pipeline. Written on 2026-10-20 against
branch `feat/all-formats`; every number says where and when it was measured.

| Document | Question it answers |
| --- | --- |
| [Current state](current-state.md) | What is tested today, with which tools, where each check runs, how long it takes and what it covers |
| [Test strategy and plan](test-strategy.md) | Which kind of test belongs in which layer, the design rules every test follows, and the definition of done for each kind of change |
| [Gaps and risks](gaps-and-risks.md) | What can break without a check noticing, ranked by severity, with the fix for each |
| [Static analysis](static-analysis.md) | Linters, type checkers, formatters and architecture rules in place, and the ones worth adding per layer |
| [Mutation testing](mutation-testing.md) | The 2026-10-18 pilot, the tool per layer, how to read a run, and every surviving mutant with the test that kills it |
| [Advanced testing](advanced-testing.md) | Property-based, contract and fuzz, performance, security, accessibility, visual, internationalization, data-quality and resilience testing |
| [CI/CD](ci-cd.md) | The pipeline as it runs today, the proposed two-lane layout, the gates to add and how dependencies get updated |
| [Metrics and process](metrics-and-process.md) | The four numbers to track, the pull-request and review checklists, the flaky-test policy and the weekly cadence |
| [Roadmap](roadmap.md) | Four phases with a measurable gate between each, effort per item and the gap each item closes |
| [Runbook](runbook.md) | The exact commands to run every check locally, the environment each needs and how to read the reports |

## How the documents relate

`current-state.md` is the inventory; `gaps-and-risks.md` is what the inventory
lacks; every other document proposes how to close a gap, and `roadmap.md` orders
those proposals. The test strategy is the standing rule set that outlives the
roadmap. The runbook is the one to open when something must be run.

## Related material

- [Repository README, Development section](../../README.md#development): the
  coverage floors and the one-command verification.
- [Analytics README](../../analytics/README.md) and [API README](../../api/README.md):
  how each application is built and tested on its own.
- [Measurement contract](../measurement-contract.md): the semantic invariants the
  scoring tests protect.
- [ADR 0001](../adr/0001-polyglot-application-boundary.md): the boundary that
  `scripts/check_boundaries.py` enforces.
- The 2026-10-19 Claude doc
  [MTG Scorer QA Assessment and Test Plan](https://claude.ai/code/artifact/09faa640-0e31-42bc-92f8-5049190066ba),
  which this folder supersedes; its mutation-pilot appendix is reproduced in
  [mutation-testing.md](mutation-testing.md).

## Keeping these documents current

- A change to a test suite, a tool version or a CI step updates
  `current-state.md` and, when a command changes, `runbook.md`.
- A closed gap is marked closed in `gaps-and-risks.md` with the commit that closed
  it, and its roadmap item is ticked.
- Measured numbers carry the date and the machine or CI run they came from. A
  number without a date is a target, not a measurement.
