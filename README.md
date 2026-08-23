# Dependency Health Monitor (DHM)

Comprehensive health assessments for Python project dependencies.

[![PyPI version](https://badge.fury.io/py/dependency-health-monitor.svg)](https://badge.fury.io/py/dependency-health-monitor)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **Health Scoring**: Weighted composite scores based on security, maintenance, community, and popularity
- **Vulnerability Detection**: Real-time scanning via OSV database with open vs fixed classification
- **Maintenance Analysis**: Identifies abandoned, deprecated, or archived packages
- **License Evaluation**: Categorizes licenses (permissive, copyleft, weak copyleft)
- **Manifests & Lockfiles**: Reads `pyproject.toml`, `requirements*.txt`, `poetry.lock`, `uv.lock`, `Pipfile.lock`
- **Installed-Env Scanning**: `--installed` reports on the versions actually installed, not latest-on-PyPI
- **Transitive Analysis**: `--include-transitive` covers the full dependency graph (direct vs transitive tagged)
- **SBOM Export**: Emit a CycloneDX 1.5 SBOM with health annotations (`-f cyclonedx`)
- **Caching**: SQLite-based caching reduces API calls and improves performance
- **CI/CD Ready**: Exit codes for pipeline integration

## Installation

```bash
pip install dependency-health-monitor
```

Or install from source:

```bash
git clone https://github.com/jeremylaratro/dhm.git
cd dhm
pip install -e ".[dev]"
```

## Quick Start

### Command Line

```bash
# Scan current project
dhm scan

# Check a single package
dhm check requests

# Find alternatives for a problematic package
dhm alternatives urllib3

# Output as JSON for CI/CD
dhm scan -f json -o report.json

# Fail CI if high+ severity issues found
dhm scan --fail-on high

# Include transitive dependencies (uses a lockfile if present, else the installed env)
dhm scan --include-transitive

# Scan what's actually installed in the current environment
dhm scan --installed

# Emit a CycloneDX SBOM (with health annotations) for supply-chain tooling
dhm scan --include-transitive -f cyclonedx -o sbom.cdx.json
```

### Python Library

```python
import asyncio
from dhm import check, scan

async def main():
    # Check a single package
    report = await check("requests")
    print(f"{report.package.name}: Grade {report.health.grade}")
    print(f"  Security: {report.health.security_score:.0f}")
    print(f"  Open vulnerabilities: {len(report.health.open_vulnerabilities)}")

    # Scan a project directory
    reports = await scan(".")
    for r in reports:
        if r.health.has_open_vulnerabilities:
            print(f"⚠️  {r.package.name} has {len(r.health.open_vulnerabilities)} open vulns")

asyncio.run(main())
```

**Synchronous API** (for non-async contexts):

```python
from dhm import check_sync, scan_sync

report = check_sync("flask")
print(f"Flask health: {report.health.grade} ({report.health.overall:.0f}/100)")

reports = scan_sync("/path/to/project")
unhealthy = [r for r in reports if r.health.is_concerning]
```

## Health Score Algorithm

DHM calculates a composite health score using weighted components:

| Component | Weight | Data Sources |
|-----------|--------|--------------|
| Security | 35% | OSV vulnerability database |
| Maintenance | 30% | PyPI release dates, GitHub activity |
| Community | 20% | Contributors, stars, PR merge rates |
| Popularity | 15% | pypistats.org download counts |

**Grade Thresholds:**

| Grade | Score | Meaning |
|-------|-------|---------|
| A | ≥ 85 | Excellent - Well maintained, secure, popular |
| B | ≥ 75 | Good - Minor concerns, generally safe |
| C | ≥ 65 | Acceptable - Some issues, monitor closely |
| D | ≥ 55 | Concerning - Significant issues, consider alternatives |
| F | < 55 | Critical - Major problems, action required |

## Vulnerability Classification

DHM distinguishes between **open** and **fixed** vulnerabilities:

- **Open**: Affects your installed version - action required
- **Fixed**: Was present in older versions but patched in yours - historical only

```python
report = await check("aiohttp", version="3.13.3")

# Only shows vulnerabilities affecting version 3.13.3
for vuln in report.health.open_vulnerabilities:
    print(f"🔴 {vuln.id}: {vuln.title}")
    if vuln.fixed_version:
        print(f"   Fix: Upgrade to {vuln.fixed_version}")
```

## Caching

DHM caches API responses to improve performance and reduce rate limiting:

| Data Type | TTL | Rationale |
|-----------|-----|-----------|
| GitHub repo data | 24 hours | Metrics change slowly |
| PyPI metadata | 1 hour | Releases are occasional |
| Download stats | 6 hours | Updated daily |
| Vulnerabilities | 6 hours | Security-critical, stay current |

```bash
# View cache statistics
dhm cache --stats

# Clear all cached data
dhm cache --clear

# Remove only expired entries
dhm cache --cleanup

# Invalidate specific data
dhm cache --invalidate 'github:%'
```

## CI/CD Integration

```yaml
# GitHub Actions example
- name: Check dependency health
  run: |
    pip install dependency-health-monitor
    dhm scan --fail-on high -f json -o dhm-report.json

- name: Upload report
  uses: actions/upload-artifact@v3
  with:
    name: dependency-health-report
    path: dhm-report.json
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | GitHub API token for higher rate limits (5000/hr vs 60/hr) |

## License

MIT - See [LICENSE](LICENSE) for details.
