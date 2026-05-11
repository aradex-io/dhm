# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
