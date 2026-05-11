# Dependency Health Monitor (DHM) User Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [CLI Usage](#cli-usage)
5. [Programmatic Usage](#programmatic-usage)
6. [Understanding Health Scores](#understanding-health-scores)
7. [Configuration](#configuration)
8. [Cache Management](#cache-management)
9. [CI/CD Integration](#cicd-integration)
10. [Troubleshooting](#troubleshooting)

---

## Introduction

### What is DHM?

Dependency Health Monitor (DHM) is a comprehensive health assessment tool for Python project dependencies. It helps you identify risky dependencies before they become problems by aggregating data from multiple sources:

- **PyPI**: Package metadata, release dates, download statistics
- **OSV Database**: Security vulnerabilities (CVEs, GitHub Security Advisories)
- **GitHub**: Repository activity, community engagement, maintenance status
- **pypistats.org**: Download counts and popularity metrics

### Why Use DHM?

**Problem**: Modern Python projects depend on dozens of packages. How do you know if they're:
- Secure (no unpatched vulnerabilities)?
- Maintained (not abandoned)?
- Trustworthy (active community, good practices)?
- Compatible (license issues)?

**Solution**: DHM calculates a composite health score (0-100 with letter grades A-F) based on:

| Component | Weight | What It Measures |
|-----------|--------|------------------|
| **Security** | 35% | Known vulnerabilities (CRITICAL penalties for open CVEs) |
| **Maintenance** | 30% | Release frequency, last update, deprecation status |
| **Community** | 20% | Contributors, stars, issue resolution, PR merge rates |
| **Popularity** | 15% | Download counts, watchers (indicates production usage) |

### Key Features

- **Vulnerability Detection**: Real-time scanning via OSV database with distinction between open vs fixed vulnerabilities
- **Maintenance Analysis**: Identifies abandoned, deprecated, or archived packages
- **License Evaluation**: Categorizes licenses (permissive, copyleft, weak copyleft)
- **Smart Caching**: SQLite-based caching reduces API calls and improves performance
- **CI/CD Ready**: Exit codes for pipeline integration (fail builds on high-severity issues)
- **Multiple Interfaces**: CLI for terminal usage, Python API for scripts and automation

---

## Installation

### Basic Installation

Install from PyPI (recommended):

```bash
pip install dependency-health-monitor
```

Verify installation:

```bash
dhm --version
```

### Development Installation

Install from source with development dependencies:

```bash
git clone https://github.com/jeremylaratro/dhm.git
cd dhm
pip install -e ".[dev]"
```

This includes testing tools (pytest, mypy, ruff) for contributors.

### Optional: GitHub Token

DHM works without configuration, but GitHub API has strict rate limits:
- **Without token**: 60 requests/hour
- **With token**: 5,000 requests/hour

Create a GitHub token (read-only permissions sufficient):

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scope: `public_repo` (read access to public repositories)
4. Copy the token

Set as environment variable:

```bash
# Linux/macOS
export GITHUB_TOKEN="your_token_here"

# Windows (PowerShell)
$env:GITHUB_TOKEN="your_token_here"

# Or add to ~/.bashrc or ~/.zshrc for persistence
echo 'export GITHUB_TOKEN="your_token_here"' >> ~/.bashrc
```

Or pass directly to commands:

```bash
dhm scan --github-token YOUR_TOKEN
```

---

## Quick Start

### Check a Single Package

Check the health of any PyPI package:

```bash
dhm check requests
```

**Output example:**

```
requests (2.31.0)
─────────────────────────────────────────
Grade: B (78/100)

Component Scores:
  Security:    100 ████████████████████
  Maintenance:  75 ███████████████
  Community:    70 ██████████████
  Popularity:   85 █████████████████

Status: ACTIVE
Positive Factors:
  ✓ Highly popular (10M+ monthly downloads)
  ✓ Active contributor community
  ✓ Recently updated

Risk Factors:
  (none)

Open Vulnerabilities: 0
Fixed Vulnerabilities: 2
```

### Scan Your Project

Scan all dependencies in your project:

```bash
# Scan current directory
dhm scan

# Scan specific project
dhm scan /path/to/project

# Scan with JSON output
dhm scan -f json -o report.json
```

**Supports multiple dependency formats:**
- `pyproject.toml` (modern Python projects)
- `requirements.txt`

**Output example (table format):**

```
Package       Version  Grade  Security  Maintenance  Vulnerabilities
───────────────────────────────────────────────────────────────────
requests      2.31.0   B      100       75           0 open, 2 fixed
flask         3.0.0    A      100       90           0 open
urllib3       1.26.5   F      40        60           2 open (HIGH)
click         8.1.7    A      100       85           0 open
```

### Find Alternatives

Find healthier alternatives to a problematic package:

```bash
dhm alternatives urllib3
```

**Output example:**

```
Alternatives for urllib3 (current score: 40, grade: F)
────────────────────────────────────────────────────────

Package          Score  Grade  Migration  Rationale
─────────────────────────────────────────────────────────────────────
httpx            92     A      medium     Modern async HTTP client
requests         78     B      low        Widely used, stable API
aiohttp          85     A      medium     Async support, active dev
```

---

## CLI Usage

### Commands Overview

DHM provides four main commands:

```bash
dhm check <package>      # Check single package health
dhm scan [path]          # Scan project dependencies
dhm alternatives <pkg>   # Find healthier alternatives
dhm cache [options]      # Manage cache
```

### `dhm check` - Check Single Package

**Basic usage:**

```bash
dhm check requests
```

**Check specific version:**

```bash
dhm check requests -v 2.28.0
```

This is useful for checking older versions you're currently using.

**With GitHub token:**

```bash
dhm check --github-token YOUR_TOKEN django
```

**Real-world examples:**

```bash
# Check if a package has known vulnerabilities
dhm check pillow

# Check a package before adding it to your project
dhm check fastapi

# Verify a specific version you're locked to
dhm check numpy -v 1.24.0
```

### `dhm scan` - Scan Project Dependencies

**Basic usage:**

```bash
# Scan current directory
dhm scan

# Scan specific project
dhm scan /path/to/my-project

# Scan parent directory
dhm scan ..
```

**Output formats:**

```bash
# Table format (default, best for terminal viewing)
dhm scan -f table

# JSON format (for parsing, CI/CD, programmatic use)
dhm scan -f json

# Markdown format (for documentation, GitHub issues)
dhm scan -f markdown
```

**Save to file:**

```bash
# Save JSON report
dhm scan -f json -o dhm-report.json

# Save markdown report
dhm scan -f markdown -o SECURITY-REPORT.md
```

**Disable caching (force fresh data):**

```bash
dhm scan --no-cache
```

**Exit codes for CI/CD:**

```bash
# Exit non-zero if any CRITICAL vulnerabilities found
dhm scan --fail-on critical

# Exit non-zero if HIGH or above severity issues
dhm scan --fail-on high

# Exit non-zero if MEDIUM or above severity issues
dhm scan --fail-on medium

# Exit non-zero if LOW or above severity issues
dhm scan --fail-on low
```

**Complete example:**

```bash
# Pre-deployment check with strict criteria
dhm scan --fail-on high -f json -o security-scan.json
```

### `dhm alternatives` - Find Better Packages

**Basic usage:**

```bash
dhm alternatives requests
```

**Real-world scenarios:**

```bash
# Package has vulnerabilities - find alternatives
dhm alternatives pillow

# Package is abandoned - find maintained alternative
dhm alternatives nose

# Exploring options for new feature
dhm alternatives celery
```

**How it works:**

DHM uses heuristics to find similar packages:
- Searches PyPI for packages with similar names/descriptions
- Filters by same category (web frameworks, HTTP clients, etc.)
- Ranks by health score
- Estimates migration effort based on API similarity

### `dhm cache` - Manage Cache

**View cache statistics:**

```bash
dhm cache --stats
```

**Output example:**

```
Cache Statistics:
  Database: /home/user/.dhm/cache.db
  Size: 1.2 MB
  Total entries: 145
  Valid entries: 120
  Expired entries: 25

  Entries by type:
    github: 45 (24h TTL)
    pypi: 50 (1h TTL)
    pypistats: 15 (6h TTL)
    osv: 10 (6h TTL)

  To refresh all data, use: dhm cache --clear
```

**Clear all cached data:**

```bash
dhm cache --clear
```

**Remove only expired entries:**

```bash
dhm cache --cleanup
```

**Invalidate specific data types:**

```bash
# Clear only GitHub data (force refresh from API)
dhm cache --invalidate 'github:%'

# Clear only PyPI data
dhm cache --invalidate 'pypi:%'

# Clear only vulnerability data
dhm cache --invalidate 'osv:%'

# Clear specific package data
dhm cache --invalidate 'pypi:requests'
```

**When to clear cache:**

- After major package releases (to get latest metadata)
- When GitHub rate limit resets (to retry failed requests)
- When you suspect stale data
- Before critical security scans (ensure fresh vulnerability data)

---

## Programmatic Usage

### Python API Overview

DHM provides both **async** and **sync** APIs for integration into your Python applications.

**Async API** (recommended for modern async applications):
- `check()` - Check single package
- `scan()` - Scan project
- `check_packages()` - Check multiple packages

**Sync API** (for scripts, notebooks, non-async contexts):
- `check_sync()` - Check single package
- `scan_sync()` - Scan project

### Async Examples

#### Check a Single Package

```python
import asyncio
from dhm import check

async def main():
    # Check latest version
    report = await check("requests")

    print(f"Package: {report.package.name}")
    print(f"Version: {report.package.version}")
    print(f"Grade: {report.health.grade}")
    print(f"Overall Score: {report.health.overall:.1f}/100")
    print(f"Security Score: {report.health.security_score:.1f}/100")

    # Check for vulnerabilities
    if report.health.has_open_vulnerabilities:
        print(f"\n⚠️  Found {len(report.health.open_vulnerabilities)} open vulnerabilities:")
        for vuln in report.health.open_vulnerabilities:
            print(f"  - {vuln.id} ({vuln.severity}): {vuln.title}")
            if vuln.fixed_version:
                print(f"    Fix: Upgrade to {vuln.fixed_version}")
    else:
        print("\n✓ No open vulnerabilities")

asyncio.run(main())
```

#### Check Specific Version

```python
import asyncio
from dhm import check

async def main():
    # Check the version you're currently using
    report = await check("aiohttp", version="3.8.0")

    print(f"Checking aiohttp v{report.package.version}")
    print(f"Health: {report.health.grade} ({report.health.overall:.0f}/100)")

    # Check if update available
    if report.update_available:
        print(f"Update available: {report.update_available}")

    # Check maintenance status
    print(f"Maintenance: {report.health.maintenance_status}")

    # Show risk factors
    if report.health.risk_factors:
        print("\nRisk Factors:")
        for risk in report.health.risk_factors:
            print(f"  ⚠️  {risk}")

asyncio.run(main())
```

#### Scan a Project

```python
import asyncio
from dhm import scan

async def main():
    # Scan current directory
    reports = await scan(".")

    print(f"Found {len(reports)} dependencies\n")

    # Group by health grade
    by_grade = {}
    for report in reports:
        grade = report.health.grade.value
        by_grade.setdefault(grade, []).append(report)

    # Show summary
    for grade in ["F", "D", "C", "B", "A"]:
        count = len(by_grade.get(grade, []))
        if count > 0:
            print(f"Grade {grade}: {count} packages")

    # Show concerning packages
    concerning = [r for r in reports if r.health.is_concerning]
    if concerning:
        print(f"\n⚠️  {len(concerning)} packages need attention:")
        for report in concerning:
            print(f"  - {report.package.name}: {report.health.grade}")
            for risk in report.health.risk_factors[:2]:  # Show first 2 risks
                print(f"      {risk}")

asyncio.run(main())
```

#### Check Multiple Packages

```python
import asyncio
from dhm import check_packages

async def main():
    # Check a list of packages
    packages = ["requests", "flask", "django", "fastapi"]
    reports = await check_packages(packages)

    # Sort by health score (worst first)
    reports.sort(key=lambda r: r.health.overall)

    print("Dependency Health Report")
    print("=" * 60)

    for report in reports:
        print(f"{report.package.name:20} {report.health.grade} ({report.health.overall:5.1f})")

        # Show vulnerabilities
        open_vulns = report.health.open_vulnerabilities
        if open_vulns:
            print(f"  ⚠️  {len(open_vulns)} open vulnerabilities")

asyncio.run(main())
```

#### Advanced: Filter by Criteria

```python
import asyncio
from dhm import scan

async def main():
    reports = await scan(".")

    # Find packages with CRITICAL vulnerabilities
    critical = [
        r for r in reports
        if r.health.critical_vulnerabilities
    ]

    if critical:
        print("🚨 CRITICAL vulnerabilities found:")
        for report in critical:
            print(f"\n{report.package.name} v{report.package.version}")
            for vuln in report.health.critical_vulnerabilities:
                print(f"  {vuln.id}: {vuln.title}")
                if vuln.fixed_version:
                    print(f"  → Upgrade to {vuln.fixed_version}")

    # Find abandoned packages (no update in 2+ years)
    from dhm import MaintenanceStatus
    abandoned = [
        r for r in reports
        if r.health.maintenance_status == MaintenanceStatus.ABANDONED
    ]

    if abandoned:
        print(f"\n⚠️  {len(abandoned)} abandoned packages:")
        for report in abandoned:
            print(f"  - {report.package.name}")

    # Find packages with poor security scores
    insecure = [r for r in reports if r.health.security_score < 60]

    if insecure:
        print(f"\n🔓 {len(insecure)} packages with security concerns:")
        for report in insecure:
            score = report.health.security_score
            print(f"  - {report.package.name}: {score:.0f}/100")

asyncio.run(main())
```

### Synchronous Examples

#### Basic Sync Usage

```python
from dhm import check_sync, scan_sync

# Check single package
report = check_sync("flask")
print(f"Flask health: {report.health.grade} ({report.health.overall:.0f}/100)")

# Scan project
reports = scan_sync("/path/to/project")
print(f"Scanned {len(reports)} packages")

# Filter unhealthy
unhealthy = [r for r in reports if r.health.is_concerning]
for report in unhealthy:
    print(f"⚠️  {report.package.name}: {report.health.grade}")
```

#### Jupyter Notebook Example

```python
# Perfect for notebooks (no async needed)
from dhm import check_sync

# Quick check
report = check_sync("pandas")

# Display results
print(f"Package: {report.package.name} v{report.package.version}")
print(f"Grade: {report.health.grade}")
print(f"Security: {report.health.security_score:.0f}/100")
print(f"Maintenance: {report.health.maintenance_score:.0f}/100")
print(f"Community: {report.health.community_score:.0f}/100")
print(f"Popularity: {report.health.popularity_score:.0f}/100")

# Check PyPI metadata
if report.pypi:
    print(f"\nDownloads (last month): {report.pypi.downloads_last_month:,}")
    print(f"License: {report.pypi.license}")
    print(f"Last release: {report.pypi.release_date}")

# Check GitHub metadata
if report.repository:
    print(f"\nStars: {report.repository.stars:,}")
    print(f"Contributors: {report.repository.contributors_count}")
    print(f"Open issues: {report.repository.open_issues}")
```

#### Script Example: Pre-Commit Hook

```python
#!/usr/bin/env python3
"""Pre-commit hook to check dependency health."""

import sys
from dhm import scan_sync

def main():
    # Scan project
    reports = scan_sync(".")

    # Check for critical issues
    has_critical = False

    for report in reports:
        # Fail on critical vulnerabilities
        if report.health.critical_vulnerabilities:
            print(f"❌ {report.package.name} has CRITICAL vulnerabilities!")
            has_critical = True

        # Fail on grade F packages
        if report.health.grade.value == "F":
            print(f"❌ {report.package.name} has grade F (score: {report.health.overall:.0f})")
            has_critical = True

    if has_critical:
        print("\n🚫 Commit blocked due to dependency health issues.")
        print("Run 'dhm scan' for details.")
        sys.exit(1)

    print("✓ All dependencies passed health check")
    sys.exit(0)

if __name__ == "__main__":
    main()
```

### Using with GitHub Token

```python
import asyncio
import os
from dhm import check

async def main():
    # Read token from environment
    token = os.getenv("GITHUB_TOKEN")

    # Pass to check function
    report = await check("django", github_token=token)

    print(f"Django: {report.health.grade}")

asyncio.run(main())
```

### Disable Caching

```python
from dhm import check_sync

# Force fresh data (bypass cache)
report = check_sync("requests", use_cache=False)
```

---

## Understanding Health Scores

### Overall Score Calculation

DHM calculates a **weighted composite score** from four components:

```
Overall = (Security × 0.35) + (Maintenance × 0.30) + (Community × 0.20) + (Popularity × 0.15)
```

**Why these weights?**
- **Security (35%)**: Most critical - vulnerabilities can compromise your application
- **Maintenance (30%)**: Abandoned packages won't fix bugs or vulnerabilities
- **Community (20%)**: Active communities indicate sustainable projects
- **Popularity (15%)**: Popular packages are battle-tested but can still have issues

### Letter Grades

Scores are converted to letter grades for quick assessment:

| Grade | Score Range | Meaning | Action |
|-------|-------------|---------|--------|
| **A** | 85-100 | Excellent | Safe to use, low risk |
| **B** | 75-84 | Good | Generally safe, minor concerns |
| **C** | 65-74 | Acceptable | Usable but monitor closely |
| **D** | 55-64 | Concerning | Investigate issues, consider alternatives |
| **F** | 0-54 | Critical | High risk, action required |

### Component Scores Explained

#### Security Score (0-100)

**What it measures:**
- Known vulnerabilities from OSV database
- Severity of vulnerabilities (CRITICAL, HIGH, MEDIUM, LOW)
- Whether vulnerabilities affect your installed version

**Scoring:**

Starting at 100 (perfect security), deductions for vulnerabilities:

| Severity | Open Vulnerability | Fixed Vulnerability |
|----------|-------------------|---------------------|
| CRITICAL | -40 points | -4 points |
| HIGH | -25 points | -2.5 points |
| MEDIUM | -10 points | -1 point |
| LOW | -5 points | -0.5 points |

**Example:**
- Package with 1 CRITICAL open vulnerability: **60/100**
- Package with 2 HIGH open vulnerabilities: **50/100**
- Package with historical vulnerabilities (all fixed): **90-95/100**

**Understanding fixed vs open:**
- **Open**: Affects your installed version - **IMMEDIATE ACTION REQUIRED**
- **Fixed**: Was present in older versions - shows responsive maintainers

#### Maintenance Score (0-100)

**What it measures:**
- Time since last release
- Release frequency
- Deprecation status
- Repository archive status
- Commit frequency (if GitHub data available)

**Scoring (starts at 50, base neutral):**

| Factor | Points |
|--------|--------|
| Released within 30 days | +20 |
| Released within 90 days | +15 |
| Released within 180 days | +10 |
| Released within 365 days | +5 |
| No release in 2+ years | -10 |
| 10+ total releases | +10 |
| 5+ total releases | +5 |
| Active commits (>1/day) | +15 |
| Some commits (>0.1/day) | +10 |
| Archived repository | -30 |
| Deprecated | -20 |

**Maintenance Status:**

| Status | Criteria | Risk |
|--------|----------|------|
| ACTIVE | Updated within 90 days | Low |
| STABLE | Updated within 1 year | Low |
| SLOW | Updated within 2 years | Medium |
| MINIMAL | Updated within 3 years | High |
| ABANDONED | No updates in 3+ years | Critical |
| ARCHIVED | Repository archived | Critical |
| DEPRECATED | Officially deprecated | Critical |

#### Community Score (0-100)

**What it measures:**
- Number of contributors
- GitHub stars
- Forks
- Pull request merge rate
- Issue close rate

**Scoring (starts at 50, logarithmic normalization):**

DHM uses **logarithmic scaling** for smooth scoring:
- Package with 10 contributors ≈ same score as 9 or 11
- Package with 1000 stars ≈ same score as 999 or 1001
- Avoids arbitrary cutoffs

| Factor | Max Points | Range |
|--------|-----------|--------|
| Contributors | +20 | 1→200 (log scale) |
| Stars | +20 | 10→50,000 (log scale) |
| Forks | +10 | 1→500 (log scale) |
| PR merge rate | +10 | 0→100% (linear) |
| Single maintainer | -10 | Penalty |
| Archived | -25 | Penalty |

**Example:**
- 1 contributor: 40/100 (single maintainer penalty)
- 10 contributors, 500 stars: 70/100
- 50 contributors, 5000 stars, high PR merge rate: 90/100

#### Popularity Score (0-100)

**What it measures:**
- Monthly download counts (from pypistats.org)
- Repository watchers
- Social proof of production usage

**Scoring (starts at 50, logarithmic normalization):**

| Factor | Max Points | Range |
|--------|-----------|--------|
| Downloads | +40 | 100→50M (log scale) |
| Watchers | +10 | 10→5,000 (log scale) |
| No download data | -5 | Penalty |

**Download tiers (approximate):**
- 100 downloads/month: 50/100 (neutral)
- 10,000 downloads/month: 64/100
- 1,000,000 downloads/month: 78/100
- 10,000,000 downloads/month: 85/100

**Why popularity matters:**
- High downloads = battle-tested in production
- Many watchers = community monitoring
- But popularity ≠ security (popular packages can have vulnerabilities)

### Risk Factors

DHM identifies specific risk factors displayed in reports:

**Security Risks:**
- "X OPEN critical vulnerability(ies)"
- "X OPEN high severity vulnerability(ies)"

**Maintenance Risks:**
- "Repository is archived"
- "Package is deprecated"
- "No release in X years"
- "No release in over a year"

**Community Risks:**
- "Single maintainer (bus factor risk)"
- "Many open issues with low resolution rate"

**Quality Risks:**
- "X yanked release(s)" (indicates problems in release process)

### Positive Factors

DHM also highlights positive indicators:

**Popularity:**
- "Highly popular (1M+ monthly downloads)"
- "Popular package (100K+ monthly downloads)"

**Maturity:**
- "Mature project with many releases"

**Activity:**
- "Recently updated"
- "Active contributor community"
- "Large contributor community"

**Quality:**
- "Highly starred repository"
- "Well-starred repository"
- "Excellent issue resolution rate"
- "Excellent PR merge rate"
- "Fast issue resolution"

### Confidence Levels

DHM reports confidence in its assessment based on data availability:

| Level | Criteria | Meaning |
|-------|----------|---------|
| **HIGH** | PyPI + GitHub + downloads + vulnerabilities | All data sources available |
| **MEDIUM** | PyPI + (GitHub OR downloads) | Some data sources unavailable |
| **LOW** | Missing PyPI or multiple sources | Limited data, score may be inaccurate |

**Low confidence can occur when:**
- GitHub API rate limited
- Package doesn't list repository URL
- pypistats.org unavailable
- Package is very new

---

## Configuration

### pyproject.toml Configuration

Add DHM configuration to your project's `pyproject.toml`:

```toml
[tool.dhm]
# Include transitive (indirect) dependencies in scans
include_transitive = true

# Default cache TTL in seconds (1 hour)
cache_ttl = 3600

[tool.dhm.thresholds]
# Minimum acceptable grade (C = 65+)
min_grade = "C"

# Maximum allowed open vulnerabilities
max_vulnerabilities = 0

# Maximum allowed abandoned packages
max_abandoned = 0
```

**Note**: Configuration file support is planned but not yet implemented in v0.1.0. These settings show the intended configuration schema.

### Custom Weights

For advanced users, you can customize scoring weights programmatically:

```python
from dhm.core.calculator import HealthCalculator
from dhm.reports.generator import ReportGenerator

# Create calculator with custom weights
custom_weights = {
    "security": 0.50,      # Increase security importance to 50%
    "maintenance": 0.25,   # Decrease maintenance to 25%
    "community": 0.15,     # Decrease community to 15%
    "popularity": 0.10,    # Decrease popularity to 10%
}

calculator = HealthCalculator(weights=custom_weights)

# Use with report generator
generator = ReportGenerator(calculator=calculator)
report = await generator.check_package("requests")
```

**When to customize weights:**
- **Security-critical applications**: Increase security weight to 50%+
- **Enterprise environments**: Increase maintenance and community weights
- **Experimental projects**: Decrease all weights, focus on functionality
- **Popular library preference**: Increase popularity weight

### Cache TTL Customization

Different data types have different default TTLs:

| Data Type | Default TTL | Rationale |
|-----------|-------------|-----------|
| GitHub repo data | 24 hours | Metrics change slowly |
| PyPI metadata | 1 hour | Releases are occasional |
| Download stats | 6 hours | Updated daily on pypistats |
| Vulnerabilities | 6 hours | Security-critical, stay current |

**Override programmatically:**

```python
from dhm.cache.sqlite import CacheLayer

# Create cache with custom default TTL
cache = CacheLayer(default_ttl=7200)  # 2 hours

# Or set per-item
cache.set("mykey", {"data": "value"}, ttl_seconds=3600)
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_TOKEN` | GitHub API token for higher rate limits | None |
| `DHM_CACHE_DIR` | Cache directory path | `~/.dhm` |

**Set cache directory:**

```bash
export DHM_CACHE_DIR="/tmp/dhm-cache"
dhm scan
```

---

## Cache Management

### Understanding the Cache

DHM caches API responses in a SQLite database (`~/.dhm/cache.db`) to:
- **Reduce API calls** (avoid rate limits)
- **Improve performance** (instant results for cached data)
- **Work offline** (use cached data when network unavailable)

**Cache structure:**

```
~/.dhm/
└── cache.db
    ├── pypi:requests → PyPI metadata
    ├── github:psf/requests → GitHub data
    ├── osv:requests → Vulnerability data
    └── pypistats:requests → Download stats
```

### Viewing Cache Statistics

```bash
dhm cache --stats
```

**Example output:**

```
Cache Statistics:
  Database: /home/user/.dhm/cache.db
  Size: 2.3 MB
  Total entries: 234
  Valid entries: 198
  Expired entries: 36

  Entries by type:
    github: 78 (24h TTL)
    pypi: 89 (1h TTL)
    pypistats: 21 (6h TTL)
    osv: 10 (6h TTL)
```

### Cache Maintenance

**Clear all cache:**

```bash
dhm cache --clear
```

Use when:
- Cache is very large (>100 MB)
- Suspect corrupt data
- Want completely fresh scan

**Remove expired entries only:**

```bash
dhm cache --cleanup
```

Use for routine maintenance without losing valid cache.

**Invalidate specific types:**

```bash
# Clear GitHub data (after rate limit reset)
dhm cache --invalidate 'github:%'

# Clear vulnerability data (after security advisory)
dhm cache --invalidate 'osv:%'

# Clear specific package
dhm cache --invalidate 'pypi:requests'
dhm cache --invalidate 'github:psf/requests'
```

### Programmatic Cache Access

```python
from dhm.cache.sqlite import CacheLayer

# Initialize cache
cache = CacheLayer()

# Manual cache operations
cache.set("mykey", {"data": "value"}, ttl_seconds=3600)
value = cache.get_value("mykey")

# Check cache stats
stats = cache.stats()
print(f"Total entries: {stats['total_entries']}")
print(f"Cache size: {stats['db_size_bytes'] / 1024:.1f} KB")

# Clear cache
count = cache.clear()
print(f"Removed {count} entries")
```

---

## CI/CD Integration

### GitHub Actions

**Basic health check:**

```yaml
name: Dependency Health Check

on:
  pull_request:
  push:
    branches: [main]
  schedule:
    - cron: '0 0 * * 1'  # Weekly on Monday

jobs:
  health-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install DHM
        run: pip install dependency-health-monitor

      - name: Scan dependencies
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          dhm scan --fail-on high -f json -o dhm-report.json

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: dependency-health-report
          path: dhm-report.json
```

**Advanced: Comment on PR with results:**

```yaml
      - name: Scan dependencies
        id: dhm-scan
        continue-on-error: true
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          dhm scan -f markdown > dhm-report.md

      - name: Comment on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v6
        with:
          script: |
            const fs = require('fs');
            const report = fs.readFileSync('dhm-report.md', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `## Dependency Health Report\n\n${report}`
            });
```

### GitLab CI

```yaml
dependency-health:
  image: python:3.11
  before_script:
    - pip install dependency-health-monitor
  script:
    - dhm scan --fail-on high -f json -o dhm-report.json
  artifacts:
    reports:
      json: dhm-report.json
    when: always
    expire_in: 30 days
  only:
    - merge_requests
    - main
```

### CircleCI

```yaml
version: 2.1

jobs:
  dependency-health:
    docker:
      - image: cimg/python:3.11
    steps:
      - checkout
      - run:
          name: Install DHM
          command: pip install dependency-health-monitor
      - run:
          name: Scan dependencies
          command: dhm scan --fail-on high -f json -o dhm-report.json
      - store_artifacts:
          path: dhm-report.json

workflows:
  version: 2
  build:
    jobs:
      - dependency-health
```

### Jenkins

```groovy
pipeline {
    agent any

    stages {
        stage('Dependency Health') {
            steps {
                sh 'pip install dependency-health-monitor'
                sh 'dhm scan --fail-on high -f json -o dhm-report.json'
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'dhm-report.json', fingerprint: true
        }
    }
}
```

### Pre-commit Hook

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash

echo "Running dependency health check..."

# Run DHM scan
dhm scan --fail-on critical -f table

if [ $? -ne 0 ]; then
    echo "❌ Commit blocked: Critical dependency issues found"
    echo "Run 'dhm scan' for details or use 'git commit --no-verify' to skip"
    exit 1
fi

echo "✓ Dependency health check passed"
```

Make executable:

```bash
chmod +x .git/hooks/pre-commit
```

---

## Troubleshooting

### Common Issues

#### Issue: "Rate limit exceeded"

**Symptom:**
```
Error: GitHub API rate limit exceeded (60/hour)
```

**Solution:**

1. Set GitHub token (increases limit to 5000/hour):
   ```bash
   export GITHUB_TOKEN="your_token_here"
   dhm scan
   ```

2. Or wait for rate limit reset:
   ```bash
   dhm cache --stats  # Check when rate limit resets
   ```

3. Or use cached data:
   ```bash
   dhm scan  # Uses cache by default
   ```

#### Issue: "Package not found"

**Symptom:**
```
Error: Package 'mypackage' not found on PyPI
```

**Solutions:**

1. Check spelling:
   ```bash
   # Correct
   dhm check scikit-learn

   # Wrong
   dhm check sklearn  # Not the PyPI name
   ```

2. Check package exists on PyPI: https://pypi.org/search/

3. For local packages, DHM only checks published PyPI packages

#### Issue: Slow scans

**Symptom:**
Scans take >5 minutes for small projects

**Solutions:**

1. Check cache is enabled:
   ```bash
   dhm scan  # Cache enabled by default
   ```

2. Use GitHub token (avoid rate limit delays):
   ```bash
   export GITHUB_TOKEN="your_token_here"
   dhm scan
   ```

3. Pre-populate cache:
   ```bash
   # Run once to cache data
   dhm scan

   # Subsequent scans are fast
   dhm scan
   ```

#### Issue: Missing GitHub data

**Symptom:**
```
Confidence: LOW
(Missing repository data)
```

**Causes & Solutions:**

1. **Package doesn't list repository URL**
   - Check PyPI page for package
   - No solution - DHM can't find repo without URL

2. **Rate limit exceeded**
   - Set `GITHUB_TOKEN` environment variable
   - Or wait for rate limit reset

3. **Private repository**
   - DHM only accesses public repositories
   - Private repos will show missing data

#### Issue: Incorrect vulnerability count

**Symptom:**
Shows vulnerabilities for wrong version

**Solution:**

Always specify version when checking:
```bash
# Check your specific version
dhm check requests -v 2.28.0

# Not just latest
dhm check requests  # Checks latest, may differ from your version
```

#### Issue: Cache not updating

**Symptom:**
Shows old data even after package update

**Solution:**

Clear cache for specific package:
```bash
# Clear all data for package
dhm cache --invalidate 'pypi:requests'
dhm cache --invalidate 'github:psf/requests'
dhm cache --invalidate 'osv:requests'

# Or clear all cache
dhm cache --clear

# Then re-scan
dhm check requests
```

### Debug Mode

For detailed error information, use Python's logging:

```python
import logging
import asyncio
from dhm import check

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

async def main():
    report = await check("requests")
    print(report)

asyncio.run(main())
```

### Getting Help

1. **Check documentation**: https://github.com/jeremylaratro/dhm
2. **Search issues**: https://github.com/jeremylaratro/dhm/issues
3. **Ask questions**: Open a GitHub issue with:
   - DHM version (`dhm --version`)
   - Python version (`python --version`)
   - Full error message
   - Steps to reproduce

---

## Appendix: Quick Reference

### CLI Commands Cheatsheet

```bash
# Check single package
dhm check <package>
dhm check <package> -v <version>

# Scan project
dhm scan
dhm scan /path/to/project
dhm scan -f json -o report.json
dhm scan --fail-on high

# Find alternatives
dhm alternatives <package>

# Manage cache
dhm cache --stats
dhm cache --clear
dhm cache --cleanup
dhm cache --invalidate 'pattern'
```

### Python API Cheatsheet

```python
# Async API
from dhm import check, scan, check_packages

report = await check("package")
reports = await scan("/path")
reports = await check_packages(["pkg1", "pkg2"])

# Sync API
from dhm import check_sync, scan_sync

report = check_sync("package")
reports = scan_sync("/path")

# Access report data
report.health.grade           # A, B, C, D, F
report.health.overall         # 0-100 score
report.health.security_score  # 0-100
report.health.vulnerabilities # List[Vulnerability]
report.health.risk_factors    # List[str]
```

### Health Grade Quick Reference

| Grade | Score | Use It? |
|-------|-------|---------|
| A | 85+ | ✅ Safe |
| B | 75-84 | ✅ Good |
| C | 65-74 | ⚠️ Caution |
| D | 55-64 | ⚠️ Investigate |
| F | <55 | ❌ Avoid |

---

**End of User Guide**

For more information, visit: https://github.com/jeremylaratro/dhm
