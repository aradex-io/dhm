# DHM 0.3.1 — Review Reconciliation (22AUG2026)

An independent code/capability review (22AUG2026) was performed against an older
local checkout (0.1.0). By the time fixes were prepared, `main` had independently
advanced to **0.3.0** (a separate three-phase review remediation). This document
records how the two efforts were reconciled into **0.3.1**.

## Findings already fixed in 0.3.0 (no action)

- `--fail-on` counts only OPEN vulnerabilities.
- `asyncio.run` replaces the deprecated `get_event_loop().run_until_complete`.
- Response body is size-capped while streaming (`_get_json`, M-6), with retries.
- Structured logging + bounded concurrency in the report generator.

## Findings still open in 0.3.0 → fixed in 0.3.1

| ID | Fix |
|----|-----|
| B1 | `cache.set()` raised a masking `AttributeError` via non-existent `json.JSONEncodeError` → now `CacheError`. |
| B3 | Open/fixed classification ignored the OSV `introduced` lower bound → added `_is_version_affected` / `_compute_is_fixed` range membership. |
| B4 | CVSS vector was never parsed (dead `_extract_cvss_base_score` stub returning None; `_parse_severity` `float()`-ing the vector) → implemented dependency-free CVSS v3.1 base-score computation, wired into both the score chain and `_parse_severity`. |
| I7 | Substring license matching → whole-token SPDX matching (no "ISC"-in-"DISCLAIMER" false match). |
| I9 | `[\d.]` version regex truncated pre-release suffixes → `packaging`-based `_extract_pinned_version`. |
| I4 | `scan` docstring dropped the false `setup.py` support claim. |

## Deliberately not changed

- I3 (report-level cache write never read): 0.3.0 keeps it, likely for future
  rehydration; left as-is (not a bug).
- Pre-existing mypy findings in 0.3.0 code (14) were not in scope; the reconcile
  did not increase the count.

## Verification

- Full suite: **149 passing** (0.3.0 baseline 131 + 18 new reconcile tests in
  `tests/test_030_followups.py` and updated CVSS tests in `tests/test_vulnerability.py`).
- `ruff check src tests` clean. mypy not regressed (14, was 15).
- CVSS computation validated against canonical FIRST.org vectors (9.8 / 7.5 / 6.1).
