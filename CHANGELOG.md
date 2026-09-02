# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- `dhm scan <path>` reported "No dependencies found in project" for any repo
  whose manifest (`requirements.txt`, `pyproject.toml`, lockfiles, etc.) was
  not directly at `<path>`'s root. Discovery now searches subdirectories
  (bounded depth, skipping `.git`, `.venv`, `node_modules`, `site-packages`,
  and similar vendor/cache directories) so nested manifests are found.

---

## [0.4.0] - 2026-08-23

### Added
- **Installed-environment scanning** (`dhm scan --installed`, `dhm.scan_installed()`):
  report on the packages actually installed in the current environment (real
  installed versions via `importlib.metadata`), not the latest PyPI release.
- **Lockfile support**: `poetry.lock`, `uv.lock`, and `Pipfile.lock` are now
  parsed (full pinned resolution, including transitive packages with real
  versions).
- **Transitive dependencies** (`--include-transitive`, `scan(..., include_transitive=True)`):
  delivers the previously-inert `include_transitive` behavior. When a lockfile is
  present its full set is used; otherwise the installed-environment requirement
  graph is walked from the direct dependencies. Each report is tagged `is_direct`.
- **CycloneDX SBOM output** (`dhm scan -f cyclonedx`): emit a CycloneDX 1.5 SBOM
  with per-component DHM health properties and OPEN vulnerabilities as CycloneDX
  `vulnerabilities` entries. No new runtime dependency.
- Hashed `requirements.txt` (pip `--hash` with `\` line continuations) now parse
  correctly.

### Fixed
- **Response bodies are now fully read** in `Collector._get_json`: the previous
  `StreamReader.read(n)` could return a partial prefix when the body spanned
  multiple TCP chunks, causing intermittent `JSONDecodeError` (truncated JSON) on
  some packages. The body is now reassembled across chunks with the size cap
  still enforced while streaming.

---

## [0.3.1] - 2026-08-22

Follow-up fixes from an independent code review, for findings still open in 0.3.0.

### Fixed
- Cache `set()` now raises `CacheError` instead of a masking `AttributeError`
  (removed reference to the non-existent `json.JSONEncodeError`).
- Open-vs-fixed vulnerability classification now honors the OSV `introduced`
  lower bound via affected-range membership, eliminating false-positive "open"
  findings for versions below the affected range.
- CVSS severity and score are now computed from the OSV CVSS v3 **vector**
  string (dependency-free CVSS v3.1 base-score calculation) instead of only a
  severity-text approximation; `_parse_severity` no longer `float()`s the vector.
- License scoring uses whole-token SPDX matching instead of substring
  containment, so verbose license text (e.g. containing "DISCLAIMER") no longer
  false-matches "ISC".
- Pinned-version extraction uses `packaging` and preserves pre-release/dev
  suffixes (e.g. `1.0.0rc1`) instead of truncating them with a `[\d.]` regex.
- `scan` docstring no longer claims unsupported `setup.py` parsing.

### Notes
- B2 (`--fail-on` open-only), B5 (`asyncio.run`), response-body size cap, and
  logging/concurrency were already addressed in 0.3.0 and are unchanged.

---

## [0.3.0] - 2026-05-11

### Added
- New `validation.py` module with centralized security validation functions
- Path traversal protection for `-r` includes in requirements.txt parsing
- Recursion depth limit (max 5) to prevent stack overflow from circular includes
- Response size validation (10MB limit) to prevent memory exhaustion attacks
- URL encoding for PyPI API requests to prevent injection attacks

### Changed
- Moved ARCHITECTURE and ROADMAP docs from root to `docs/` directory
- Updated aiohttp dependency to >=3.13.3 (CVE-2025-69228, CVE-2025-69226, CVE-2025-53643)
- Added `packaging>=21.0` dependency for PEP 440-compliant version comparison
- Replaced custom version comparison with `packaging.version.parse()` for correct pre-release handling
- Converted `Optional` type hints to `X | None` syntax for consistency

### Fixed
- Version comparison bug where `1.0.0b2` incorrectly equaled `1.0.0b3`
- Path traversal vulnerability in requirements.txt `-r` includes
- Potential URL injection in PyPI API requests
- Potential memory exhaustion from oversized API responses

### Removed
- Removed `.claude/` from version control (now in .gitignore)
- Removed non-functional `[tool.dhm]` / `[tool.dhm.thresholds]` configuration block from `pyproject.toml` and the corresponding "Configuration" section from `README.md`; the config keys were never read by the tool

---

## [0.1.0] - 2026-01-27

### Added
- Initial release of Dependency Health Monitor
- Core health scoring with weighted components:
  - Security (35%): Vulnerability detection via OSV database
  - Maintenance (30%): Release frequency, repository activity
  - Community (20%): Contributors, stars, PR merge rates
  - Popularity (15%): Download statistics from pypistats.org
- Base-50 scoring philosophy with logarithmic normalization
- Open vs Fixed vulnerability distinction with version comparison
- License scoring with category detection (permissive, copyleft, weak copyleft)
- Confidence levels (HIGH/MEDIUM/LOW) based on data availability
- SQLite caching layer with configurable TTLs:
  - GitHub data: 24 hours
  - PyPI metadata: 1 hour
  - Download stats: 6 hours
  - Vulnerabilities: 6 hours
- CLI commands:
  - `dhm scan` - Scan project dependencies
  - `dhm check <package>` - Check single package health
  - `dhm alternatives <package>` - Find healthier alternatives
  - `dhm cache` - Manage local cache
- Multiple output formats: table, JSON, markdown
- CI/CD integration with `--fail-on` threshold
- Programmatic Python API for library usage

### Grade Thresholds
- A: >= 85 (Excellent)
- B: >= 75 (Good)
- C: >= 65 (Acceptable)
- D: >= 55 (Concerning)
- F: < 55 (Critical)
