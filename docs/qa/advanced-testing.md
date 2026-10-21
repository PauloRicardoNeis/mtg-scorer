# Advanced testing techniques

The suite proves examples; the techniques below prove properties, contracts,
budgets and robustness that examples cannot reach. Each section says what the
project already has, what to add, the tool, where it runs (pull-request lane,
verify stage or weekly lane) and the first concrete checks. Property-based tests
and Schemathesis are the cheapest additions; realistic-size SQL testing is the
most valuable.

## Property-based testing

The project states its invariants in prose, in the measurement contract and in
docstrings. Property-based tests turn those sentences into executable checks over
thousands of generated inputs and shrink any failure to a minimal example.

**Hypothesis (Python).** Add to the `dev` extra; keep the default example budget
on pull requests and raise it (`max_examples=2000`) in the weekly lane through a
settings profile.

- `score_card`: every output stays in [0, 100]; `distinctiveness_delta` equals
  `buildaround_signal − staple` to one decimal; raising any count never lowers
  Evidence; replacing an unknown feature with a known value changes coverage but
  never turns a known score into zero.
- `MaxRatioMethod`: the leader scores exactly 100; every score is at most 100; all
  scores are `None` exactly when every count is zero; permuting the input permutes
  the output identically.
- `select_cohort`: every returned deck and standing belongs to an included event;
  included plus excluded equals the input; an event is included if and only if its
  date is in `[starts_on, ends_before)`, its format matches and its coverage is at
  least the minimum.
- `_top_cut`: with bracket records, membership equals `wins + losses > 0`; with
  standing order, no excluded player has more wins than an included one, or the
  result is `INCONSISTENT_ORDER`.
- `write_score_run`: writing the same document twice returns the same path;
  `results_sha256` ignores `raw_files` and nothing else.
- `name_key` and `canonical_bytes`: idempotent; equal inputs give equal bytes
  regardless of dictionary order.
- Signature, hidden-gem, constructed and overall scores: percentile outputs are a
  permutation-invariant function of the inputs; a card absent from a format is
  `None`, never 0; the overall weight `decks / (decks + 250)` is monotonic in
  decks.
- Wizards and TopDeck parsers: any fixture with one record removed parses to a
  strict subset of facts (no invention of records).

**jqwik (Java).** Test scope dependency; properties live beside the JUnit tests.

- `CursorCodec`: `decode(encode(query, key))` round-trips for any valid query and
  key; any single-field change to the decoded JSON is rejected with
  `invalid_cursor`.
- `CatalogQuery.parse` and `RankingQuery.parse`: sets and colors come back sorted
  and de-duplicated; any value outside the allowed vocabularies is a 400 with
  `invalid_query`.
- `NameKey.normalize`: idempotent, and equal to the Python `name_key` on a shared
  fixture covering full-width characters, `//`, diacritics and whitespace (one
  JSON file consumed by both `test_catalog_validation.py` and `NameKeyTests`).

**fast-check (web).** Dev dependency; runs inside vitest.

- `format.ts`: `signed` carries a sign exactly when `deltaTone` is not neutral;
  `grade` and `gradeTone` cover every number including `NaN` and out-of-range
  values; formatted numbers round-trip through `Intl` for every locale in
  `locales`.
- `urls.ts`: building a search or ranking URL and parsing it back preserves every
  filter and the pinned snapshot or run.
- `translator.ts`: any message with placeholders renders every placeholder once
  for any argument object that supplies them.

## Contract and fuzz testing

In place: the live OpenAPI equals the checked-in contract; the generated TypeScript
client is unchanged; the `CardPage` fixture validates against the spec;
publication schemas are checked both ways.

- **Schemathesis in the verify stage.** After the seed is published:
  `schemathesis run http://127.0.0.1:18081/v3/api-docs --checks all --hypothesis-max-examples 50`.
  Reports any 500, any response that violates its own schema, and any
  undocumented status. Seeds with the published snapshot id so the pinned routes
  are reachable.
- **Breaking-change classification.** `api_contract.py` says "drift"; `oasdiff
  breaking contracts/catalog-api.openapi.json <live>` says whether the drift
  removes a field, narrows a type or changes a status. Run in the PR lane; a
  breaking change requires a note in the pull request and the `contract-breaking`
  label described in [ci-cd.md](ci-cd.md).
- **Consumer-side fixture rendering.** A vitest that renders the main components
  with the checked-in `card-page.json` and a ranking fixture, so a contract change
  breaks the web unit suite before the browser suite.
- **Score-run and overall-run schemas.** Already validated on write; add a
  negative fixture per schema (one per `required` field removed) so the schema's
  own strictness is tested, as `verify_contracts.py` does for the catalog.

## Database and SQL testing at realistic size

In place: real publication tests with races, failures and rollback; HTTP tests over
the 7-card seed; EXPLAIN ANALYZE recorded, not asserted.

- **Generated realistic dataset.** A deterministic generator (seeded, committed
  as code, never as data) producing a catalog of about 5,000 cards with
  multi-face, unicode and `//` names across 50 sets, plus a synthetic run of a few
  hundred decks. Used by a weekly job and by any developer who asks for it; never
  in the PR lane.
- **Pagination walk.** Walk every page of `/api/v1/cards` under each filter
  combination used by the UI; assert no duplicates, no gaps, stable order across a
  refresh, and that the last cursor is terminal. Same for rankings and compare.
- **Index assertions.** Parse the EXPLAIN JSON that `measure_catalog.py` already
  captures and fail when a `Seq Scan` appears on a published table above a row
  threshold.
- **Migration on populated data.** For each new `V(n)`: publish a snapshot and a
  run on a database at `V(n−1)`, apply `V(n)`, run the HTTP tests. Catches the
  migration that passes empty and fails populated (gap G6).
- **`@JdbcTest` in Java.** Flyway against the CI PostgreSQL for the repository
  classes, so SQL is asserted where it is written. This is the long item in the
  roadmap.

## Performance and load

In place: 100 warm loopback requests with 20 readers at the end of verify; the
one full-catalog measurement on 2026-09-28 (p50 133 ms, p95 181 ms, max 223 ms,
0 errors). The [catalog contract](../catalog-contract.md) proposes a p95 under
300 ms; nothing asserts it.

- **k6 in the weekly lane** against the generated realistic dataset: discovery,
  name search, joint printing filter, card detail, rankings page, compare. Budget
  `p(95) < 300 ms` and `http_req_failed < 0.1%`, with the trend kept as an
  artifact. Fail the weekly job on a 50% regression against the previous run, not
  on the absolute budget, until a hosted environment exists.
- **Publication throughput.** Time `publish_catalog` on the realistic dataset and
  on the retained full export when available locally; assert against the
  2026-09-28 figure (158.9 s for 118,406 records) with generous tolerance.
- **Web vitals.** Lighthouse CI on the four main pages of the production build,
  asserting performance and accessibility scores; weekly.

## Security testing

In place: admin endpoints disabled unless a token is set, tested for unauthorized
requests; role-separated database users tested for denial; Problem Details tested
not to leak internals; `/actuator/env` tested absent; secret scanning on GitHub.

- **Dependency audit** (weekly): `pip-audit`, `npm audit --audit-level=high`,
  OWASP dependency-check for Maven; Dependabot for updates.
- **CodeQL** on Java, JavaScript/TypeScript and Python; free for this public
  repository.
- **OWASP ZAP baseline scan** against the verify stack in the weekly lane:
  headers, cookies, reflected parameters. Expect findings on security headers the
  Next.js app does not yet set (`Content-Security-Policy`, `X-Content-Type-Options`);
  fixing them is a `next.config` change.
- **SBOM**: CycloneDX from `uv export`, `npm sbom` and the Maven CycloneDX plugin,
  uploaded as a CI artifact. Costs nothing and answers "do we ship X" in one grep.
- **Negative authorization matrix** for every admin route as new ones appear:
  no token, wrong token, token in query string, token with trailing whitespace.

## Accessibility

In place: axe-core at 16 call sites across the catalog, rankings, compare and
primitives specs; keyboard checks for the skip link and the `/` shortcut; a
responsive journey.

- **axe in every spec**: the four language journeys run without axe; add one
  check per locale so translated pages are scanned too.
- **Keyboard-only journeys**: complete the discovery and rankings flows with
  `Tab`, `Enter`, `Space` and arrow keys only, asserting focus order and visible
  focus rings. Playwright, PR lane.
- **Reduced motion and high contrast**: run the primitives gallery journey with
  `prefers-reduced-motion: reduce` and `forced-colors: active` emulation.
- **Screen-reader names**: assert `aria-label` and live-region text for the
  rankings table, the toast and the loading states through `getByRole` queries
  (already the style used; make it a checklist item for new components).
- **Lighthouse accessibility score** as a weekly trend.

## Visual regression

In place: four screenshots captured in the catalog journey, not compared.

- Turn them into `toHaveScreenshot` assertions. Fonts are local and the image
  CDN is stubbed, so renders are deterministic; set `maxDiffPixelRatio: 0.01`.
- Store baselines per project (`chromium`), regenerate deliberately with
  `--update-snapshots` and review the diff in the pull request.
- Add the primitives gallery as the visual contract of the design system: one
  screenshot per state block.

## Internationalization

In place: key, placeholder and plural-form parity across 11 locales; 4 language
journeys; `Intl` formatting tests.

- **Pseudo-localization locale** (`en-XA` style: accented, 30% longer, bracketed)
  generated from `en.ts` at test time and rendered through the primitives
  gallery, asserting no overflow or clipping with `toBeInViewport` and bounding
  boxes.
- **Hard-coded string guard**: an ESLint rule (`react/jsx-no-literals` scoped to
  `src/components` and `src/app`) so every user-visible string passes through the
  translator.
- **Locale journey per page**: the language journey visits every page once per
  locale, asserting the `lang` attribute, the title and one translated heading.
- **ICU variance**: dates and numbers are compared with normalized spaces today;
  pin Node's ICU version in CI (it follows the Node version, which is pinned) and
  note it in the runbook.

## Data quality and score semantics

In place: schema and relationship validation before a run file is written; row
count and "every method scored every card" checks on promotion; replay refusal on
differing results under the same id.

- **Validator parity with the database.** A test that parses every
  `CHECK (...)` in `V4` to `V9` and asserts `score_validation.py` rejects a run
  file violating each. Closes gap G8.
- **Sentinel calibration tests** from the measurement contract, run when a probe
  directory is present and skipped otherwise: a ubiquitous removal spell outscores
  a narrow engine on Staple; one unsupported deck never yields high Evidence; more
  eligible observations raise Evidence without moving Staple beyond a stated
  tolerance; a card absent from a format has no Overall contribution from it.
- **Run-to-run drift report.** When a cohort is re-scored, compare the new run's
  percentiles with the active run's and list cards that moved more than 20 points;
  print in the publication summary. Not a gate; a review aid.
- **Cohort file schema.** The cohort rules have no JSON Schema; add one and
  validate every file in `analytics/cohorts` in the build stage.

## Resilience

In place: the browser suite revokes a real table grant and verifies the error and
recovery; publication tests cover failed loads and abandoned attempts; the import
job test covers a disconnected worker.

- **Slow API**: Playwright route delays on `/api/v1/*` to assert the loading
  states and that no request is duplicated.
- **Database unavailable at API start**: covered by `ApiApplicationTests`
  (datasource on port 1); add readiness returning 503 and recovery when the
  database appears, using the CI service.
- **Partial publication**: kill the publisher mid-`COPY` (close the connection
  from a second session) and assert staging stays invisible and the next attempt
  succeeds. The abandoned-attempt test is close to this; make the cut point
  explicit.
- **Backup and restore drill** (manual, quarterly): `pg_dump` the demo database,
  restore to a fresh cluster, run the HTTP tests against it. Documented in the
  runbook once the first drill has been done.
