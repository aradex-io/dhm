# DHM Application Review — Findings Report

**Date:** 2026-05-11
**Branch:** `claude/app-review-findings-3bxHZ`
**Commit reviewed:** `6077fa3` (HEAD)
**Methodology:** Three-phase review — Scope, Implementation, Display — planned with Opus 4.7 and executed in parallel by Sonnet sub-agents. Read-only static analysis; no runtime instrumentation.

---

## Severity Rubric

| Severity | Meaning |
|----------|---------|
| **Critical** | User receives wrong/dangerous answers from a documented feature; CI integration silently breaks; remote code execution; secret exfiltration; data loss. |
| **High** | Documented feature missing or materially broken; incorrect results in common cases; broken contracts; missing essential validation. |
| **Medium** | Docs ↔ code drift that misleads users; degraded reliability; perf issue; missing tests of risk areas; poor error handling. |
| **Low** | Polish, hygiene, dead code, doc nit, minor UX. |

## Severity Distribution

| Severity | Count |
|----------|------:|
| Critical | 4 |
| High     | 14 |
| Medium   | 22 |
| Low      | 14 |
| **Total**| **54** |

(After cross-phase de-duplication. Some findings were independently identified by two or three reviewers; those are consolidated below with all originating cross-references preserved.)

---

## Quick-Reference Index

### Critical
- [C-1](#c-1---fail-on-fires-on-already-patched-vulnerabilities) `--fail-on` fires on already-patched vulnerabilities (CI breakage)
- [C-2](#c-2-progress-bar--status-text-corrupt-jsonmarkdown-on-stdout) Progress bar / status text corrupt JSON/Markdown on stdout
- [C-3](#c-3-exit-code-1-shared-by-threshold-breach-and-tool-error) Exit code 1 shared by threshold breach and tool error
- [C-4](#c-4-healthgrade-enum-comments-contradict-actual-thresholds) `HealthGrade` enum comments contradict the actual grading thresholds

### High
- [H-1](#h-1-tooldhm-config-block-documented-but-never-read) `[tool.dhm]` config block documented but never read
- [H-2](#h-2-user-guide-claims-setuppy--setupcfg--pipfile-support--none-implemented) User guide claims `setup.py`/`setup.cfg`/`Pipfile` support — none implemented
- [H-3](#h-3-check_sync--scan_sync-deprecated--unsafe-event-loop-pattern) `check_sync` / `scan_sync` deprecated & unsafe event-loop pattern
- [H-4](#h-4-cvss-base-score-always-none-for-osv-advisories) CVSS base score always `None` for OSV advisories
- [H-5](#h-5-withdrawn-osv-advisories-treated-as-active) Withdrawn OSV advisories treated as active
- [H-6](#h-6-vulnerabilityscannerfetch-marks-all-vulns-open-when-version-unknown) `VulnerabilityScanner.fetch()` marks all vulns "open" when version unknown
- [H-7](#h-7-no-rate-limiter--semaphore-on-outbound-http) No rate-limiter / semaphore on outbound HTTP
- [H-8](#h-8-no-retries-on-transient-network-errors) No retries on transient network errors
- [H-9](#h-9-json-vuln-objects-omit-is_open--open_vulnerabilities_count) JSON vuln objects omit `is_open` / `open_vulnerabilities_count`
- [H-10](#h-10-generated_at-not-valid-iso-8601-no-timezone) `generated_at` not valid ISO 8601 (no timezone)
- [H-11](#h-11-scan--f-json--o-prints-json-to-stdout-and-file-simultaneously) `scan -f json -o` prints JSON to stdout AND file simultaneously
- [H-12](#h-12-markdown-formatter-conflates-open-and-fixed-vulnerabilities) Markdown formatter conflates open and fixed vulnerabilities
- [H-13](#h-13-no---debug-flag-bare-error-strings-no-traceback) No `--debug` flag; bare error strings, no traceback
- [H-14](#h-14-dhm-check-nonexistent-pkg-exits-0-with-fake-grade-f-report) `dhm check <nonexistent>` exits 0 with fake grade-F report

### Medium
- [M-1](#m-1-code_quality_score--license_score-computed-but-excluded-from-overall) `code_quality_score` / `license_score` computed but excluded from `overall`
- [M-2](#m-2-is_deprecated-treats-development-status-1---planning-as-deprecated) `is_deprecated` treats "Development Status :: 1 - Planning" as deprecated
- [M-3](#m-3-parsingerror-validationerror-networkerror-not-exported) `ParsingError` / `ValidationError` / `NetworkError` not exported
- [M-4](#m-4-api-reference-faq-claims-python-39-package-requires-310) api-reference FAQ claims Python 3.9+; package requires 3.10+
- [M-5](#m-5-injected-aiohttp-session-has-no-timeout) Injected `aiohttp.ClientSession` has no timeout
- [M-6](#m-6-content-length-only-size-guard) `Content-Length`-only size guard
- [M-7](#m-7-sqlite-blocking-io-from-async-context) SQLite blocking I/O from async context
- [M-8](#m-8-sqlite-without-wal-mode--no-busy-timeout) SQLite without WAL mode / no busy timeout
- [M-9](#m-9-validate_package_name-never-called-from-public-api) `validate_package_name` never called from public API
- [M-10](#m-10-osv-git-range-events-mark-vulns-permanently-open) OSV `GIT` range events mark vulns permanently open
- [M-11](#m-11-_get_fixed_version-returns-first-cross-ecosystem-fix) `_get_fixed_version` returns first cross-ecosystem fix
- [M-12](#m-12-can_parse-operator-precedence-bug) `can_parse` operator-precedence bug
- [M-13](#m-13-known_alternatives--migration_efforts-are-mutable-class-vars) `KNOWN_ALTERNATIVES` / `MIGRATION_EFFORTS` are mutable class vars
- [M-14](#m-14-no-tests-for-collectors-cache-or-vulnerability-matching) No tests for collectors, cache, or vulnerability matching
- [M-15](#m-15-dhm-cache---clear-has-no-confirmation-prompt) `dhm cache --clear` has no confirmation prompt
- [M-16](#m-16-shared-console-writes-info-to-stdout-no-stderr-routing) Shared `Console` writes info to stdout, no stderr routing
- [M-17](#m-17-progress-bar-is-fake-2-step-1010100) Progress bar is fake (2-step 10/10/100)
- [M-18](#m-18-table-format-with---output-uses-different-renderer-than-terminal) `table` format with `--output` uses different renderer than terminal
- [M-19](#m-19-code_quality_score-not-displayed-or-serialized-anywhere) `code_quality_score` not displayed or serialized anywhere
- [M-20](#m-20-_generate_single_report-silently-swallows-all-errors) `_generate_single_report` silently swallows all errors
- [M-21](#m-21-arbitrary-pyproject_jsonschema-claims-not-enforced-elsewhere) Doc-claimed CI/CD example uses wrong `pip install` name
- [M-22](#m-22-needs_attention-flags-packages-with-only-fixed-vulns) `needs_attention` flags packages with only fixed vulns

### Low
- [L-1](#l-1-architecture-26jan2026-shows-unimplemented-collectors) `ARCHITECTURE-26JAN2026.md` shows unimplemented collectors
- [L-2](#l-2-architecturemd-appendix-leaks-developers-absolute-paths) `architecture.md` Appendix leaks developer's absolute paths
- [L-3](#l-3-roadmap-26jan2026-shows-completed-work-as-todo) `ROADMAP-26JAN2026.md` shows completed work as TODO
- [L-4](#l-4-python-313-not-in-ci-matrix--classifiers) Python 3.13 not in CI matrix / classifiers
- [L-5](#l-5-dhm-check--dhm-alternatives-have-no---format---output) `dhm check` / `dhm alternatives` have no `--format` / `--output`
- [L-6](#l-6-asyncioget_event_loop-in-cli-helper) `asyncio.get_event_loop()` in CLI helper
- [L-7](#l-7-healthcalculator-custom-weights-not-validated-for-negatives) `HealthCalculator` custom weights not validated for negatives
- [L-8](#l-8-datetimeutcnow-deprecated-in-python-312) `datetime.utcnow()` deprecated in Python 3.12
- [L-9](#l-9-cachelayer-mkdir-can-raise-permissionerror-outside-contract) `CacheLayer` mkdir can raise `PermissionError` outside contract
- [L-10](#l-10-pypistatsorg-url-not-encoded-no-user-agent) pypistats.org URL not encoded, no User-Agent
- [L-11](#l-11-changelog-accurate-no-action) CHANGELOG accurate (no action)
- [L-12](#l-12-redundant-third-clause-in-requirementstxt-can_parse) Redundant third clause in `RequirementsTxt.can_parse`
- [L-13](#l-13-pip-install-dhm-instead-of-pip-install-dependency-health-monitor) `pip install dhm` instead of `pip install dependency-health-monitor`
- [L-14](#l-14-grade-thresholds-second-occurrence) Grade thresholds — second occurrence (cross-ref to C-4)

---

# Critical

## C-1 — `--fail-on` fires on already-patched vulnerabilities
**Phase:** Display (3-1)
**Location:** `src/dhm/cli/main.py:334`

```python
for vuln in report.health.vulnerabilities:        # all vulns
    if vuln.severity.sort_order <= threshold_order:
        return 1
```

`_check_threshold` iterates **every** vulnerability ever associated with the package, not `open_vulnerabilities`. A project pinned to a patched version of `aiohttp` (whose history contains a HIGH CVE that is already fixed in the installed version) will exit 1 under `--fail-on high`, breaking CI for projects that are objectively safe. This directly contradicts the README's open-vs-fixed feature pitch.

**Fix:** `for vuln in report.health.open_vulnerabilities:`

---

## C-2 — Progress bar / status text corrupt JSON/Markdown on stdout
**Phase:** Display (3-2)
**Location:** `src/dhm/cli/main.py:104-119, 170-177, 208-220`; `src/dhm/cli/output.py:24`

`click.progressbar(file=None)` resolves to `sys.stdout`. The shared `console = Console()` in `output.py` also targets stdout, and `print_error` / `print_success` / `print_info` route through it. The CI pattern advertised by the README — `dhm scan -f json | jq` — receives the progress bar frames, the success banner, and the JSON payload all interleaved on the same fd. `jq` aborts.

**Fix:** Pass `file=sys.stderr` to every `click.progressbar`; create a `stderr_console = Console(stderr=True)` for all status helpers and reserve stdout for structured output.

---

## C-3 — Exit code 1 shared by threshold breach and tool error
**Phase:** Display (3-3)
**Location:** `src/dhm/cli/main.py:138, 142, 183, 240`

`sys.exit(1)` is used for both `--fail-on` threshold violations *and* for caught exceptions (network down, parse failure, unexpected error). A CI pipeline that wants to alert on "tool error" but proceed on "threshold not yet exceeded" cannot distinguish the two cases. README has zero exit-code documentation.

**Fix:** `0` = clean, `1` = threshold breached, `2` = tool/runtime error. Document in `--help` and the README CI section.

---

## C-4 — `HealthGrade` enum comments contradict the actual grading thresholds
**Phases:** Scope (1-1), Implementation (2-17)
**Location:** `src/dhm/core/models.py:14-20` vs. `src/dhm/core/calculator.py:555-564`

```python
# models.py — comments
A = "A"  # Excellent (90-100)
B = "B"  # Good (80-89)
C = "C"  # Acceptable (70-79)
D = "D"  # Concerning (60-69)
F = "F"  # Critical (<60)
```

But `_score_to_grade` thresholds are A≥85, B≥75, C≥65, D≥55, F<55 — and the README, CHANGELOG, `architecture.md`, and `api-reference.md` all agree with `_score_to_grade`. A score of 88 is grade A by the model docs but grade B by the calculator. Developers reading the model first will internalize the wrong thresholds and may write incorrect downstream logic.

**Fix:** Update enum comments to match `_score_to_grade` (or vice versa, but every other doc agrees with the calculator).

---

# High

## H-1 — `[tool.dhm]` config block documented but never read
**Phase:** Scope (1-7)
**Location:** `README.md:152-163`; `pyproject.toml:68-75`; nothing in `src/dhm/`

The README presents a full Configuration section advertising `include_transitive`, `cache_ttl`, `min_grade`, `max_vulnerabilities`, `max_abandoned`. None of these keys are read anywhere in `src/dhm/`. The package's own `pyproject.toml` even contains a sample `[tool.dhm]` block — yet adding it has zero effect on a user's project.

**Fix:** Either implement a `pyproject.toml` loader, or remove the Configuration section until it ships.

---

## H-2 — User guide claims `setup.py` / `setup.cfg` / `Pipfile` support — none implemented
**Phase:** Scope (1-8)
**Location:** `docs/user-guide.md:173-174` vs. `src/dhm/core/resolver.py:344-346`

`DependencyResolver.__init__` registers exactly two parsers: `PyProjectTomlSource` and `RequirementsTxtSource`. The user guide promises four extra formats. Users with `setup.py`-only projects will see "no dependencies found" with no warning that the format is unsupported.

**Fix:** Strike the unsupported formats from the user guide, or add stubs that emit a clear "unsupported format" diagnostic.

---

## H-3 — `check_sync` / `scan_sync` deprecated & unsafe event-loop pattern
**Phases:** Scope (1-4), Implementation (2-F-01)
**Location:** `src/dhm/api.py:158, 179`

```python
return asyncio.get_event_loop().run_until_complete(check(...))
```

`asyncio.get_event_loop()` emits `DeprecationWarning` in 3.10+ and will raise in a future Python. Worse: inside an existing event loop (Jupyter, FastAPI handler, pytest-asyncio test) `run_until_complete` raises `RuntimeError: This event loop is already running`. README sells these as the "for non-async contexts" answer; they are unsafe in the most common non-async-yet-async-adjacent contexts.

**Fix:** Use `asyncio.run(...)` for new-loop semantics; if a loop is already running, raise a typed error pointing the user at the async API.

---

## H-4 — CVSS base score always `None` for OSV advisories
**Phase:** Implementation (2-F-02)
**Location:** `src/dhm/collectors/vulnerability.py:288-296`

```python
if severity_entry.get("type") == "CVSS_V3":
    score_str = severity_entry.get("score", "")
    try: cvss_score = float(score_str)
    except ValueError: pass
```

OSV's `severity[].score` is the **CVSS vector string** (`CVSS:3.1/AV:N/AC:L/...`) — never a float. `float()` always raises; the `pass` swallows it. Result: `cvss_score` is `None` for every real advisory and any downstream consumer relying on numeric severity gets nothing.

**Fix:** Use the `cvss` package to compute base score, or read the numeric value from `database_specific.cvss.score` when present.

---

## H-5 — Withdrawn OSV advisories treated as active
**Phase:** Implementation (2-F-03)
**Location:** `src/dhm/collectors/vulnerability.py:250-308`

`_parse_vulnerability` never inspects the `withdrawn` field. OSV uses `withdrawn` (ISO timestamp) to retract advisories that were issued in error or superseded. DHM treats them as live, producing false-positive vuln reports.

**Fix:** Skip (`return None`) when `data.get("withdrawn")` is set; filter `None` in callers.

---

## H-6 — `VulnerabilityScanner.fetch()` marks all vulns "open" when version unknown
**Phase:** Implementation (2-F-04)
**Location:** `src/dhm/collectors/vulnerability.py:144-148, 449`

`is_fixed_in_installed_version` is only computed when both `version` and `vuln.fixed_version` are known. The public `VulnerabilityScanner.fetch(name)` (line 449) constructs `PackageIdentifier(name=identifier)` with **no version** — every vulnerability returned therefore reports `is_open=True`, masking the open-vs-fixed feature DHM advertises.

**Fix:** Document the version-required contract on `fetch()`; emit a warning when `version is None`; route through `scan_package(PackageIdentifier(name, version))` from `generator.py`.

---

## H-7 — No rate-limiter / semaphore on outbound HTTP
**Phase:** Implementation (2-F-05)
**Location:** `src/dhm/reports/generator.py:124-134`

`asyncio.gather(*[...])` is unbounded. A 100-package scan launches 100 concurrent coroutines, each making 4-5 GitHub calls — potentially 500+ simultaneous requests. GitHub's unauthenticated limit is **60/hour**; even authenticated 5000/hour will trip secondary abuse detection on bursts. There is no per-host semaphore.

**Fix:** Wrap gather with `asyncio.Semaphore(N)` (e.g. 10); add a per-host limit for GitHub (e.g. 5).

---

## H-8 — No retries on transient network errors
**Phase:** Implementation (2-F-06)
**Location:** `src/dhm/collectors/base.py` and all collectors

Every HTTP call is one-shot. A transient 503, RST, or connect timeout immediately raises and the package is silently dropped from the report (see M-20). For a tool whose primary failure mode is "the upstream registry hiccupped", this is brittle.

**Fix:** Exponential-backoff retry (3 attempts) for `aiohttp.ClientError` and 5xx; respect `Retry-After`.

---

## H-9 — JSON vuln objects omit `is_open` / `open_vulnerabilities_count`
**Phase:** Display (3-4)
**Location:** `src/dhm/core/models.py:520-528`

```python
"vulnerabilities": [
    {"id": v.id, "severity": v.severity.value,
     "title": v.title, "fixed_version": v.fixed_version}
    for v in self.health.vulnerabilities
]
```

The flagship "open vs fixed" distinction the README emphasizes is **absent from JSON output**. Consumers cannot tell which vulns require action without re-implementing version comparison. Summary block also lacks `open_vulnerabilities_count`.

**Fix:** Add `"is_open": not v.is_fixed_in_installed_version` to each entry; add `"open_vulnerabilities_count"` to `metadata.summary`.

---

## H-10 — `generated_at` not valid ISO 8601 (no timezone)
**Phase:** Display (3-5)
**Location:** `src/dhm/reports/formatters.py:68`

`datetime.utcnow().isoformat()` produces `"2026-05-11T02:04:00.446844"` — naive, no `Z` / `+00:00`. Strict ISO-8601 parsers (and `Date.parse` in JS) reject it; semantics are ambiguous to anyone not assuming UTC.

**Fix:** `datetime.now(timezone.utc).isoformat()`.

---

## H-11 — `scan -f json -o` prints JSON to stdout AND file simultaneously
**Phase:** Display (3-6)
**Location:** `src/dhm/cli/main.py:124-131`; `src/dhm/reports/generator.py:101-103`

`generator.generate()` always writes to `output_path` when set; `main.py` then unconditionally `click.echo(formatted)` for non-table formats. The README's GitHub Actions example (`-f json -o report.json`) dumps the entire JSON into the CI log on top of writing it to disk.

**Fix:** Skip `click.echo(formatted)` when `--output` is provided.

---

## H-12 — Markdown formatter conflates open and fixed vulnerabilities
**Phase:** Display (3-7)
**Location:** `src/dhm/reports/formatters.py:156, 168-183`

The Rich terminal output (`output.py:89-113`) cleanly separates "OPEN — Action Required" from "Fixed — Historical". The Markdown formatter does not — it lists every vuln under one heading and the summary "With Vulnerabilities" counter includes packages whose vulns are all patched. The format most likely to be saved and shared is the one that misleads.

**Fix:** Mirror the terminal layout in markdown; use `open_vulnerabilities_count` for the summary.

---

## H-13 — No `--debug` flag; bare error strings, no traceback
**Phase:** Display (3-8)
**Location:** `src/dhm/cli/main.py:140-142, 181-183, 238-240`

Three `except Exception as e: print_error(f"... {e}")` blocks. There is no `--debug` / `--verbose` switch on the group or any subcommand. A user seeing "Scan failed: 400" cannot tell whether it was their pyproject, the network, or a DHM bug. `_generate_single_report` silently `pass`es per-package failures with zero diagnostic.

**Fix:** Add `--debug` to the `cli` group; under debug, re-raise; print which packages failed and why.

---

## H-14 — `dhm check <nonexistent-pkg>` exits 0 with fake grade-F report
**Phase:** Display (3-9)
**Location:** `src/dhm/reports/generator.py:265-277`

When `check_package` cannot find the package, it returns a synthetic `HealthScore(overall=0, grade=F, risk_factors=["Package not found or unavailable"])`. The CLI renders this like a real result and exits 0. A user typo (`dhm check requestz`) produces a convincing F report rather than a "package not found" error.

**Fix:** Propagate `PackageNotFoundError`; CLI prints an error and exits 2.

---

# Medium

## M-1 — `code_quality_score` / `license_score` computed but excluded from `overall`
**Phases:** Scope (1-2), Implementation (2-F-16), Display (3-14)
**Location:** `src/dhm/core/calculator.py:151-180`

Both are computed and stored on `HealthScore`, but `overall` only weights security/maintenance/community/popularity. A package with AGPL (license_score=60) is graded identically to one with MIT. `code_quality_score` is also never displayed in the CLI nor serialized to JSON, so users cannot even *see* the orphan number.

**Fix:** Either fold them into the weighted average (and rebalance), drop them from `HealthScore`, or document the exclusion in the README's scoring table and api-reference.

## M-2 — `is_deprecated` treats "Development Status :: 1 - Planning" as deprecated
**Phase:** Scope (1-3)
**Location:** `src/dhm/core/models.py:223-229`

The Trove classifier `"1 - Planning"` indicates an early-stage project, not an abandoned one. DHM's `is_deprecated` includes it, triggering a -20 maintenance penalty for any pre-alpha package. The correct deprecation classifier is `"7 - Inactive"` (already present).

**Fix:** Remove `"1 - Planning"` from the deprecated list.

## M-3 — `ParsingError` / `ValidationError` / `NetworkError` not exported
**Phase:** Scope (1-5)
**Location:** `src/dhm/__init__.py:36-43` vs. `docs/api-reference.md:846-903, 1209`

api-reference shows `from dhm import ParsingError`, but `__init__.py` only re-exports `DHMError`, `PackageNotFoundError`, `RateLimitError`, `RepositoryNotFoundError`, `CacheError`. Users following the docs hit `ImportError`.

**Fix:** Add the three missing exceptions to `__init__.py` imports and `__all__`.

## M-4 — api-reference FAQ claims Python 3.9+; package requires 3.10+
**Phase:** Scope (1-9)
**Location:** `docs/api-reference.md:2011, 1320` vs. `pyproject.toml:12`

The codebase uses `X | Y` union syntax throughout — strictly 3.10+. The Poetry example (`python = "^3.9"`) compounds the misdirection.

**Fix:** Update the FAQ and Poetry example to 3.10+.

## M-5 — Injected `aiohttp.ClientSession` has no timeout
**Phase:** Implementation (2-F-07)
**Location:** `src/dhm/reports/generator.py:118`

`async with aiohttp.ClientSession() as session:` inherits aiohttp's default of **no total timeout** (5-min read only). Per-collector `self.timeout` only applies when the collector creates its own session. A hung server can stall the event loop for minutes.

**Fix:** `aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))`.

## M-6 — `Content-Length`-only size guard
**Phase:** Implementation (2-F-08)
**Location:** `src/dhm/collectors/base.py:89-103`; `src/dhm/core/validation.py:169`

The size validator only fires when the upstream sends `Content-Length`. Chunked-encoded responses skip the check entirely, then `await resp.json()` reads the entire body into RAM.

**Fix:** Stream-read with a hard byte limit, or set `read_bufsize` and bail past `MAX_RESPONSE_SIZE`.

## M-7 — SQLite blocking I/O from async context
**Phase:** Implementation (2-F-09)
**Location:** `src/dhm/cache/sqlite.py:73-91` and all collector callers

`CacheLayer.get/set/delete/invalidate` use the synchronous `sqlite3` module directly inside `async def` functions. Every cache hit blocks the loop. Under concurrent scans this serializes everything that would otherwise be parallel.

**Fix:** Run via `loop.run_in_executor` or migrate to `aiosqlite`.

## M-8 — SQLite without WAL mode / no busy timeout
**Phase:** Implementation (2-F-10)
**Location:** `src/dhm/cache/sqlite.py:79-91`

Default journal mode is DELETE; multiple coroutines writing concurrently produce `OperationalError: database is locked` after the 5-second default busy wait.

**Fix:** `PRAGMA journal_mode=WAL;` after connect; pass `timeout=10` to `sqlite3.connect`.

## M-9 — `validate_package_name` never called from public API
**Phase:** Implementation (2-F-11)
**Location:** `src/dhm/api.py:31-64`; `src/dhm/core/validation.py:25-63`

The validator exists and is correct, but `check()`/`scan()`/`check_packages()` build `PackageIdentifier`s and run them through the pipeline without calling it. Combined with M-23 below, raw names with `/`, `?`, NUL bytes, etc., reach pypistats.org URL interpolation.

**Fix:** Validate at the public-API boundary.

## M-10 — OSV `GIT` range events mark vulns permanently open
**Phase:** Implementation (2-F-12)
**Location:** `src/dhm/collectors/vulnerability.py:391-408`

`_get_fixed_version` returns the first `fixed` event regardless of range type. For `GIT` ranges the value is a commit hash, which `parse_version` rejects, so the vuln is treated as "no fixed version" — permanently open even when a SEMVER fix exists.

**Fix:** Filter ranges to `ECOSYSTEM` / `SEMVER`; ignore `GIT`.

## M-11 — `_get_fixed_version` returns first cross-ecosystem fix
**Phase:** Implementation (2-F-13)
**Location:** `src/dhm/collectors/vulnerability.py:391-408`

Multi-ecosystem advisories (e.g., npm + PyPI) — first match wins, so an npm-style fix version can be reported as the PyPI fix.

**Fix:** Filter `affected[]` by `package.ecosystem == "PyPI"` first.

## M-12 — `can_parse` operator-precedence bug
**Phase:** Implementation (2-F-14)
**Location:** `src/dhm/core/resolver.py:72-80`

```python
return (
    name == "requirements.txt"
    or name.startswith("requirements")
    and name.endswith(".txt")        # binds tighter than `or`
    or name in ("requirements-dev.txt", ...)
)
```

`and` binds tighter than `or`, so any `requirements*.txt` name matches — including `requirementsXYZ.txt`. The third clause is also dead.

**Fix:** Add explicit parens around the `startswith/endswith` clause; drop the redundant tuple check.

## M-13 — `KNOWN_ALTERNATIVES` / `MIGRATION_EFFORTS` are mutable class vars
**Phase:** Implementation (2-F-15)
**Location:** `src/dhm/analyzers/alternatives.py:29-130, 392-398`

`add_known_alternative` mutates the class-level dict. Mutations leak across instances and persist for the process. Concurrent `ReportGenerator` instances race.

**Fix:** Copy class data into instance dicts in `__init__`.

## M-14 — No tests for collectors, cache, or vulnerability matching
**Phase:** Implementation (2-F-21)
**Location:** `tests/`

Suite covers `calculator`, `models`, `resolver` only. Zero tests for: OSV version-range matching (the most error-prone code in the project — see C-1, H-4, H-5, H-6, M-10, M-11), the cache layer, retry/rate-limit paths (which don't exist anyway — H-7, H-8), the sync wrappers, any collector.

**Fix:** Add unit tests for `_is_version_fixed`, `_parse_vulnerability` (with real OSV fixtures including withdrawn / GIT / multi-ecosystem advisories), `CacheLayer` TTL + concurrency, HTTP 429/503 paths.

## M-15 — `dhm cache --clear` has no confirmation prompt
**Phase:** Display (3-10)
**Location:** `src/dhm/cli/main.py:274-276`

Typo `--clear` instead of `--cleanup` immediately wipes everything. With unauthenticated GitHub at 60/hr, an unwanted clear can render the tool unusable for an hour.

**Fix:** `click.confirm(..., abort=True)` with a `--yes/-y` bypass.

## M-16 — Shared `Console` writes info to stdout, no stderr routing
**Phase:** Display (3-11)
**Location:** `src/dhm/cli/output.py:24`

Same root cause as C-2 but separate concern: even when the progress bar is fixed, `print_error` / `print_success` / `print_info` still pollute stdout. There is no `Console(stderr=True)` for diagnostics.

**Fix:** Two consoles — `out_console`, `err_console = Console(stderr=True)` — with all status helpers using the latter.

## M-17 — Progress bar is fake (2-step 10/10/100)
**Phase:** Display (3-12)
**Location:** `src/dhm/cli/main.py:104-118`

`bar.update(10)` → blocking gather → `bar.update(90)`. Bar sits at 10% during the entire scan, then jumps to 100%. Looks like a hang.

**Fix:** Per-package callback into `generate_reports`, advancing the bar; or switch to a Rich `Progress` spinner.

## M-18 — `table` format with `--output` uses different renderer than terminal
**Phase:** Display (3-13)
**Location:** `src/dhm/cli/main.py:124-128`; `src/dhm/reports/generator.py:98-103`

For `--format table`, the terminal gets `print_table()` (Rich, colored, boxed). The file gets `TableFormatter` (plain ASCII). Same flag, two outputs.

**Fix:** Either disable `--output` for `table` (recommend `markdown` instead), or unify renderers.

## M-19 — `code_quality_score` not displayed or serialized anywhere
**Phase:** Display (3-14) — see also M-1
**Location:** `src/dhm/cli/output.py:188-192`; `src/dhm/core/models.py:504-543`

Field exists, defaults to 50, computed by calculator — never shown to humans, never in JSON. Pure dead weight from a user perspective.

**Fix:** Display it (and explain its weight is zero), or delete the field.

## M-20 — `_generate_single_report` silently swallows all errors
**Phase:** Implementation (2-F-24)
**Location:** `src/dhm/reports/generator.py:195, 206, 213`

Bare `except Exception: pass` at every fetch step. PyPI 404, GitHub 403, OSV down — all produce a `HealthScore` with default values (security=100!) which is *actively misleading*. Only `check_package` returns the synthetic F-grade (and that has its own bug — H-14).

**Fix:** Log at `WARNING`; tag the report's `confidence` as `LOW`; include a risk factor describing which collector failed.

## M-21 — Doc-claimed CI/CD example uses wrong `pip install` name
**Phase:** Scope (1-6) — duplicate of L-13 — listed once for the index
**Location:** `docs/api-reference.md:1949`

`pip install dhm` installs an unrelated PyPI package. The correct name is `dependency-health-monitor`. Reclassed Medium because following the docs gives the user a working but wrong tool.

**Fix:** Replace with `pip install dependency-health-monitor`.

## M-22 — `needs_attention` flags packages with only fixed vulns
**Phase:** Implementation (2-F-18)
**Location:** `src/dhm/core/models.py:498-502`

`needs_attention` ORs in `has_vulnerabilities` (any vulnerability ever). `requests`, `flask`, etc. all have historical CVEs and will always be `needs_attention=True`. Same root cause as C-1.

**Fix:** Use `has_open_vulnerabilities`.

---

# Low

## L-1 — `ARCHITECTURE-26JAN2026.md` shows unimplemented collectors
**Phase:** Scope (1-10)
**Location:** `docs/ARCHITECTURE-26JAN2026.md:26-59`

Diagram includes Libraries.io, NVD, Safety DB, IDE plugins — none exist. The newer `architecture.md` is correct. **Fix:** Add a "superseded by `architecture.md`" banner, or delete.

## L-2 — `architecture.md` Appendix leaks developer's absolute paths
**Phase:** Scope (1-11)
**Location:** `docs/architecture.md:1368-1378`; `docs/SCORING_ALGORITHM_ANALYSIS-27JAN2026.md:6-10`

`/home/jay/Documents/cyber/dev/planning_studio/...` peppered through the file table. **Fix:** Replace with relative paths.

## L-3 — `ROADMAP-26JAN2026.md` shows completed work as TODO
**Phase:** Scope (1-12)
**Location:** `docs/ROADMAP-26JAN2026.md:26-79`

Every Phase 1 item is `- [ ]` despite being shipped. **Fix:** Check the boxes or add a "Phase 1 complete" header.

## L-4 — Python 3.13 not in CI matrix / classifiers
**Phase:** Scope (1-14)
**Location:** `pyproject.toml:30-34`; `.github/workflows/main.yml:20`

Matrix stops at 3.12 even though `requires-python = ">=3.10"` admits 3.13 installs. **Fix:** Add 3.13 once tested.

## L-5 — `dhm check` / `dhm alternatives` have no `--format` / `--output`
**Phase:** Display (3-15)

Only `scan` is scriptable. `dhm check` requires screen-scraping. **Fix:** Add `--format` and `--output` to both.

## L-6 — `asyncio.get_event_loop()` in CLI helper
**Phase:** Display (3-16)
**Location:** `src/dhm/cli/main.py:28`

Same deprecation as H-3 but in `cli/main.py`'s `run_async`. **Fix:** `asyncio.run(coro)`.

## L-7 — `HealthCalculator` custom weights not validated for negatives
**Phase:** Implementation (2-F-19)
**Location:** `src/dhm/core/calculator.py:122-129`

Negative weights pass through normalization unchanged. **Fix:** Reject negatives; require positive `total`.

## L-8 — `datetime.utcnow()` deprecated in Python 3.12
**Phase:** Implementation (2-F-20) — see also H-10
**Location:** `src/dhm/reports/formatters.py:68, 142`

**Fix:** `datetime.now(timezone.utc)`.

## L-9 — `CacheLayer` mkdir can raise `PermissionError` outside contract
**Phase:** Implementation (2-F-22)
**Location:** `src/dhm/cache/sqlite.py:45`

`mkdir` not wrapped; the rest of init is. Callers expecting `CacheError` get `PermissionError`. **Fix:** Wrap and re-raise as `CacheError`.

## L-10 — pypistats.org URL not encoded, no User-Agent
**Phase:** Implementation (2-F-23)
**Location:** `src/dhm/collectors/pypi.py:254`

`f"https://pypistats.org/api/packages/{name}/recent"` — raw interpolation. Combined with M-9, untrusted names reach the URL. **Fix:** Apply `encode_package_name_for_url`; add a `User-Agent`.

## L-11 — CHANGELOG accurate (no action)
**Phase:** Scope (1-13)

Reviewed and verified consistent with code. Recorded for completeness.

## L-12 — Redundant third clause in `RequirementsTxt.can_parse`
**Phase:** Implementation (sub-finding of M-12)

After fixing the precedence bug (M-12), the explicit tuple of names becomes dead code. **Fix:** Delete it.

## L-13 — `pip install dhm` instead of `pip install dependency-health-monitor`
Same as M-21 (kept here only as an index pointer; do not double-count).

## L-14 — Grade thresholds — second occurrence
Same as C-4 (kept here only as an index pointer; do not double-count).

---

# Cross-Cutting Themes

1. **The "open vs. fixed vulnerability" feature is the project's flagship differentiator and is structurally compromised.** It is wrong in `--fail-on` (C-1), wrong in `needs_attention` (M-22), missing from JSON (H-9), missing from Markdown (H-12), wrong when version is unknown (H-6), and is undermined by adjacent OSV bugs (H-4, H-5, M-10, M-11). Fixing this cluster should be the top priority — most are one-line changes.

2. **stdout/stderr discipline is missing throughout the CLI.** C-2, H-11, M-16, M-17 all stem from a single shared `Console()` and a habit of `click.echo` next to status text. A 30-line refactor (split consoles; gate `echo` on `--output`) clears multiple criticals/highs.

3. **Async correctness is shaky.** H-3, H-7, H-8, M-5, M-7, M-8, L-6 are all in the async/concurrency layer. The library *is* an async library; these need a focused pass.

4. **Docs ↔ code drift is widespread but mostly cosmetic** except where it actively misleads (H-1 config block, H-2 dependency formats, C-4 grade comments). The dated `*-26JAN2026.md` / `*-27JAN2026.md` / `*-29JAN2026.md` files in `docs/` are a recurring source of drift — consider archiving them under `docs/archive/`.

5. **Test coverage of the highest-risk code is zero.** Vulnerability matching, cache concurrency, retries (none exist), and sync wrappers all live without tests (M-14). Six of the bugs above (C-1, H-4, H-5, H-6, M-10, M-11) would have been caught by basic unit tests of `_parse_vulnerability` and `_is_version_fixed`.

---

# Recommended Sequencing

**Phase A (1-2 days, high leverage):** C-1, C-4, H-6, H-9, M-22, H-12 — fix the open-vs-fixed cluster end-to-end with tests.

**Phase B (1 day):** C-2, C-3, H-11, H-13, M-15, M-16, M-17 — CLI/UX hardening for CI consumers.

**Phase C (2-3 days):** H-3, H-4, H-5, H-7, H-8, M-5, M-7, M-8, M-9, M-10, M-11, M-20 — async/HTTP/cache hardening with tests.

**Phase D (1 day, low risk):** All Lows + doc fixes (H-1, H-2, M-1, M-2, M-3, M-4, M-21).

---

*End of report.*
