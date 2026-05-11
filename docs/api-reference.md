# API Reference

Complete reference documentation for the Dependency Health Monitor (DHM) Python package.

## Table of Contents

1. [Public API Functions](#public-api-functions)
2. [Core Models](#core-models)
3. [Exceptions](#exceptions)
4. [Health Calculator](#health-calculator)
5. [Dependency Resolver](#dependency-resolver)
6. [Report Generator](#report-generator)

---

## Public API Functions

The high-level API provides simple, async-friendly functions for common operations. These are the recommended entry points for most users.

### `check()`

Check the health of a single package.

```python
async def check(
    package: str,
    version: str | None = None,
    *,
    github_token: str | None = None,
    use_cache: bool = True,
) -> DependencyReport
```

**Parameters:**
- `package` (str): Package name (e.g., `"requests"`, `"django"`).
- `version` (str | None): Optional specific version to check. If not provided, checks the latest version from PyPI.
- `github_token` (str | None): Optional GitHub API token for higher rate limits and access to private repositories.
- `use_cache` (bool): Whether to use cached data. Default: `True`.

**Returns:**
- `DependencyReport`: Complete health report containing health score, vulnerabilities, and metadata.

**Example:**

```python
import asyncio
from dhm import check

async def main():
    # Check latest version
    report = await check("flask")
    print(f"Grade: {report.health.grade}")
    print(f"Open vulnerabilities: {len(report.health.open_vulnerabilities)}")

    # Check specific version
    report = await check("requests", version="2.25.0")
    if report.health.has_open_vulnerabilities:
        print("WARNING: This version has known vulnerabilities!")

asyncio.run(main())
```

---

### `check_sync()`

Synchronous wrapper for `check()`.

```python
def check_sync(
    package: str,
    version: str | None = None,
    *,
    github_token: str | None = None,
    use_cache: bool = True,
) -> DependencyReport
```

For use in non-async contexts. Creates and manages its own event loop.

**Parameters:** Same as `check()`.

**Returns:** `DependencyReport`

**Example:**

```python
from dhm import check_sync

# Simple synchronous usage
report = check_sync("requests")
print(f"{report.package.name}: {report.health.grade}")

if report.health.is_concerning:
    print("This package needs attention!")
    for risk in report.health.risk_factors:
        print(f"  - {risk}")
```

---

### `scan()`

Scan a project's dependencies for health issues.

```python
async def scan(
    path: str | None = None,
    *,
    github_token: str | None = None,
    use_cache: bool = True,
) -> list[DependencyReport]
```

**Parameters:**
- `path` (str | None): Path to project directory. Defaults to current directory. Automatically detects and parses `pyproject.toml`, `requirements.txt`, `setup.py`, etc.
- `github_token` (str | None): Optional GitHub API token.
- `use_cache` (bool): Whether to use cached data. Default: `True`.

**Returns:**
- `list[DependencyReport]`: List of reports, one per dependency found.

**Example:**

```python
import asyncio
from dhm import scan

async def main():
    # Scan current directory
    reports = await scan(".")

    # Filter concerning dependencies
    unhealthy = [r for r in reports if r.health.is_concerning]
    print(f"Found {len(unhealthy)} concerning dependencies")

    # Show packages with vulnerabilities
    vulnerable = [r for r in reports if r.health.has_open_vulnerabilities]
    for report in vulnerable:
        print(f"\n{report.package.name} has vulnerabilities:")
        for vuln in report.health.open_vulnerabilities:
            print(f"  - {vuln.id} ({vuln.severity}): {vuln.title}")

asyncio.run(main())
```

---

### `scan_sync()`

Synchronous wrapper for `scan()`.

```python
def scan_sync(
    path: str | None = None,
    *,
    github_token: str | None = None,
    use_cache: bool = True,
) -> list[DependencyReport]
```

**Parameters:** Same as `scan()`.

**Returns:** `list[DependencyReport]`

**Example:**

```python
from dhm import scan_sync

# Scan a project synchronously
reports = scan_sync("/path/to/project")
print(f"Scanned {len(reports)} packages")

# Generate a summary
grades = {}
for report in reports:
    grade = report.health.grade.value
    grades[grade] = grades.get(grade, 0) + 1

print("\nGrade Distribution:")
for grade in ["A", "B", "C", "D", "F"]:
    count = grades.get(grade, 0)
    print(f"  {grade}: {count}")
```

---

### `check_packages()`

Check health of multiple packages concurrently.

```python
async def check_packages(
    packages: list[str],
    *,
    github_token: str | None = None,
    use_cache: bool = True,
) -> list[DependencyReport]
```

**Parameters:**
- `packages` (list[str]): List of package names. Optionally include versions using `==` syntax (e.g., `"requests==2.31.0"`).
- `github_token` (str | None): Optional GitHub API token.
- `use_cache` (bool): Whether to use cached data. Default: `True`.

**Returns:**
- `list[DependencyReport]`: List of reports, one per package.

**Example:**

```python
import asyncio
from dhm import check_packages

async def main():
    packages = [
        "requests",
        "flask==2.0.0",
        "django",
        "numpy>=1.20.0"
    ]

    reports = await check_packages(packages)

    # Sort by health score
    sorted_reports = sorted(reports, key=lambda r: r.health.overall, reverse=True)

    print("Packages ranked by health:")
    for report in sorted_reports:
        print(f"{report.package.name}: {report.health.grade} ({report.health.overall:.1f})")

asyncio.run(main())
```

---

## Core Models

All data models are defined as dataclasses and are importable from `dhm.core.models`.

### `PackageIdentifier`

Uniquely identifies a package with optional version and extras.

```python
@dataclass
class PackageIdentifier:
    name: str
    version: str | None = None
    extras: tuple[str, ...] = ()
```

**Attributes:**
- `name` (str): Package name (e.g., `"requests"`).
- `version` (str | None): Optional version string (e.g., `"2.31.0"`).
- `extras` (tuple[str, ...]): Optional extras (e.g., `("security", "socks")`).

**Properties:**
- `normalized_name` (str): Lowercase name with underscores converted to hyphens.

**Methods:**
- `__str__()` → str: Returns formatted string like `"requests[security]==2.31.0"`.
- `__hash__()` → int: Makes the object hashable for use in sets/dicts.
- `__eq__(other)` → bool: Case-insensitive name comparison.

**Example:**

```python
from dhm import PackageIdentifier

# Basic package
pkg = PackageIdentifier(name="requests")
print(pkg)  # "requests"

# With version
pkg = PackageIdentifier(name="django", version="4.2.0")
print(pkg)  # "django==4.2.0"

# With extras
pkg = PackageIdentifier(
    name="httpx",
    version="0.24.0",
    extras=("http2", "brotli")
)
print(pkg)  # "httpx[http2,brotli]==0.24.0"
print(pkg.normalized_name)  # "httpx"
```

---

### `HealthGrade`

Letter grades for dependency health (Enum).

```python
class HealthGrade(Enum):
    A = "A"  # Excellent (85-100)
    B = "B"  # Good (75-84)
    C = "C"  # Acceptable (65-74)
    D = "D"  # Concerning (55-64)
    F = "F"  # Critical (<55)
```

**Example:**

```python
from dhm import HealthGrade

grade = HealthGrade.A
print(grade)  # "A"
print(grade.value)  # "A"
```

---

### `ConfidenceLevel`

Confidence level in the calculated score based on data availability (Enum).

```python
class ConfidenceLevel(Enum):
    HIGH = "high"     # All data sources available (PyPI + GitHub + pypistats + vulns)
    MEDIUM = "medium" # Some data sources unavailable (e.g., GitHub rate limited)
    LOW = "low"       # Missing critical data sources
```

---

### `RiskLevel`

Risk severity levels for vulnerabilities and issues (Enum).

```python
class RiskLevel(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
```

**Properties:**
- `sort_order` (int): Numeric sort order where lower = more severe (CRITICAL=0, INFO=4).

**Example:**

```python
from dhm import RiskLevel

severity = RiskLevel.CRITICAL
print(severity.sort_order)  # 0

# Sort vulnerabilities by severity
vulnerabilities.sort(key=lambda v: v.severity.sort_order)
```

---

### `MaintenanceStatus`

Package maintenance classification (Enum).

```python
class MaintenanceStatus(Enum):
    ACTIVE = "active"         # Regular updates, responsive maintainer
    STABLE = "stable"         # Mature, infrequent but intentional updates
    SLOW = "slow"             # Occasional updates, slow response
    MINIMAL = "minimal"       # Rare updates, unclear maintenance
    ABANDONED = "abandoned"   # No updates, unresponsive
    ARCHIVED = "archived"     # Explicitly marked as archived
    DEPRECATED = "deprecated" # Officially deprecated
```

**Properties:**
- `is_concerning` (bool): Returns `True` if status is ABANDONED, ARCHIVED, or DEPRECATED.

**Example:**

```python
from dhm import MaintenanceStatus

status = MaintenanceStatus.ABANDONED
if status.is_concerning:
    print("WARNING: This package is no longer maintained!")
```

---

### `Vulnerability`

Security vulnerability information.

```python
@dataclass
class Vulnerability:
    id: str  # CVE-2024-XXXX or GHSA-XXXX
    severity: RiskLevel
    title: str
    description: str
    affected_versions: str  # Version specifier
    fixed_version: str | None = None
    published: datetime | None = None
    references: list[str] = field(default_factory=list)
    cvss_score: float | None = None
    is_fixed_in_installed_version: bool = False
```

**Attributes:**
- `id` (str): Vulnerability identifier (e.g., `"CVE-2024-12345"`, `"GHSA-xxxx-xxxx-xxxx"`).
- `severity` (RiskLevel): Severity level (CRITICAL, HIGH, MEDIUM, LOW, INFO).
- `title` (str): Brief vulnerability title.
- `description` (str): Detailed description.
- `affected_versions` (str): Version range affected (e.g., `"<2.31.0"`).
- `fixed_version` (str | None): Version that fixes the vulnerability (if available).
- `published` (datetime | None): Publication date.
- `references` (list[str]): List of reference URLs.
- `cvss_score` (float | None): CVSS score (0-10 scale).
- `is_fixed_in_installed_version` (bool): `True` if the installed version is patched.

**Properties:**
- `has_fix` (bool): Returns `True` if `fixed_version` is available.
- `is_open` (bool): Returns `True` if vulnerability affects the installed version.

**Methods:**
- `to_dict()` → dict: Convert to dictionary for caching/serialization.
- `from_dict(data: dict)` → Vulnerability: Construct from dictionary (classmethod).

**Example:**

```python
# Vulnerability objects are typically returned in reports
for vuln in report.health.vulnerabilities:
    print(f"{vuln.id} - {vuln.title}")
    print(f"  Severity: {vuln.severity}")
    print(f"  Affected: {vuln.affected_versions}")

    if vuln.has_fix:
        print(f"  Fix available: {vuln.fixed_version}")

    if vuln.is_open:
        print("  STATUS: OPEN - Affects your version!")
    else:
        print("  STATUS: Fixed in your version")
```

---

### `PyPIMetadata`

Metadata retrieved from PyPI.

```python
@dataclass
class PyPIMetadata:
    name: str
    version: str
    summary: str
    author: str
    author_email: str | None = None
    license: str | None = None
    python_requires: str | None = None
    requires_dist: list[str] = field(default_factory=list)
    project_urls: dict[str, str] = field(default_factory=dict)
    classifiers: list[str] = field(default_factory=list)
    downloads_last_month: int = 0
    release_date: datetime | None = None
    first_release_date: datetime | None = None
    total_releases: int = 0
    yanked_releases: int = 0
```

**Properties:**
- `home_page` (str | None): Project home page URL.
- `repository_url` (str | None): Source repository URL (GitHub, GitLab, etc.).
- `is_deprecated` (bool): `True` if package appears deprecated based on classifiers.

**Methods:**
- `to_dict()` → dict: Convert to dictionary for caching.
- `from_dict(data: dict)` → PyPIMetadata: Construct from dictionary (classmethod).

**Example:**

```python
pypi = report.pypi
if pypi:
    print(f"Package: {pypi.name} v{pypi.version}")
    print(f"Summary: {pypi.summary}")
    print(f"License: {pypi.license}")
    print(f"Downloads: {pypi.downloads_last_month:,}")
    print(f"Repository: {pypi.repository_url}")

    if pypi.is_deprecated:
        print("WARNING: This package is deprecated!")
```

---

### `RepositoryMetadata`

Metadata from source repository (GitHub/GitLab).

```python
@dataclass
class RepositoryMetadata:
    url: str
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    open_pull_requests: int = 0
    watchers: int = 0
    contributors_count: int = 0
    last_commit_date: datetime | None = None
    created_date: datetime | None = None
    is_archived: bool = False
    is_fork: bool = False
    license: str | None = None
    topics: list[str] = field(default_factory=list)
    default_branch: str = "main"

    # Calculated metrics
    commit_frequency_30d: float = 0.0  # Commits per day
    issue_close_rate_90d: float = 0.0  # Percentage closed
    pr_merge_rate_90d: float = 0.0     # Percentage merged
    avg_issue_close_time_days: float = 0.0
    avg_pr_merge_time_days: float = 0.0
```

**Properties:**
- `github_owner_repo` (tuple[str, str] | None): Extracts `(owner, repo)` from GitHub URL.

**Methods:**
- `to_dict()` → dict: Convert to dictionary for caching.
- `from_dict(data: dict)` → RepositoryMetadata: Construct from dictionary (classmethod).

**Example:**

```python
repo = report.repository
if repo:
    print(f"Repository: {repo.url}")
    print(f"Stars: {repo.stars:,}")
    print(f"Contributors: {repo.contributors_count}")
    print(f"Commit frequency: {repo.commit_frequency_30d:.2f} commits/day")
    print(f"Issue close rate: {repo.issue_close_rate_90d:.1%}")

    if repo.is_archived:
        print("WARNING: Repository is archived!")

    if repo.last_commit_date:
        days_ago = (datetime.now() - repo.last_commit_date).days
        print(f"Last commit: {days_ago} days ago")
```

---

### `HealthScore`

Composite health score for a package.

```python
@dataclass
class HealthScore:
    overall: float  # 0-100
    grade: HealthGrade

    # Component scores (0-100)
    security_score: float = 100.0
    maintenance_score: float = 50.0
    community_score: float = 50.0
    popularity_score: float = 50.0
    code_quality_score: float = 50.0
    license_score: float = 50.0

    # Detailed breakdown
    maintenance_status: MaintenanceStatus = MaintenanceStatus.STABLE
    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    risk_factors: list[str] = field(default_factory=list)
    positive_factors: list[str] = field(default_factory=list)

    # Confidence in the score
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH

    # Metadata
    calculated_at: datetime | None = None
    data_freshness: dict[str, datetime] = field(default_factory=dict)
```

**Properties:**
- `is_healthy` (bool): Returns `True` if grade is A or B.
- `is_concerning` (bool): Returns `True` if grade is D or F.
- `has_vulnerabilities` (bool): Returns `True` if any vulnerabilities exist.
- `has_open_vulnerabilities` (bool): Returns `True` if unpatched vulnerabilities exist.
- `open_vulnerabilities` (list[Vulnerability]): List of vulnerabilities affecting installed version.
- `fixed_vulnerabilities` (list[Vulnerability]): List of vulnerabilities fixed in installed version.
- `critical_vulnerabilities` (list[Vulnerability]): List of open CRITICAL severity vulnerabilities.

**Example:**

```python
health = report.health

# Overall assessment
print(f"Grade: {health.grade} ({health.overall:.1f}/100)")
print(f"Confidence: {health.confidence}")

# Component scores
print(f"\nComponent Scores:")
print(f"  Security: {health.security_score:.1f}")
print(f"  Maintenance: {health.maintenance_score:.1f}")
print(f"  Community: {health.community_score:.1f}")
print(f"  Popularity: {health.popularity_score:.1f}")

# Status checks
if health.is_healthy:
    print("\n✓ Package is healthy")
elif health.is_concerning:
    print("\n✗ Package needs attention!")

# Vulnerabilities
if health.has_open_vulnerabilities:
    print(f"\nOpen Vulnerabilities: {len(health.open_vulnerabilities)}")
    for vuln in health.critical_vulnerabilities:
        print(f"  CRITICAL: {vuln.id} - {vuln.title}")

# Risk factors
if health.risk_factors:
    print("\nRisk Factors:")
    for risk in health.risk_factors:
        print(f"  - {risk}")

# Positive factors
if health.positive_factors:
    print("\nPositive Factors:")
    for factor in health.positive_factors:
        print(f"  + {factor}")
```

---

### `AlternativePackage`

A recommended alternative package.

```python
@dataclass
class AlternativePackage:
    package: PackageIdentifier
    health_score: float
    migration_effort: str  # "low", "medium", "high"
    rationale: str
    api_compatibility: float = 0.0  # 0-1, how similar the API is
```

**Example:**

```python
for alt in report.alternatives:
    print(f"\nAlternative: {alt.package.name}")
    print(f"  Health Score: {alt.health_score:.0f}")
    print(f"  Migration Effort: {alt.migration_effort}")
    print(f"  Rationale: {alt.rationale}")
    print(f"  API Compatibility: {alt.api_compatibility:.0%}")
```

---

### `DependencyReport`

Complete health report for a dependency.

```python
@dataclass
class DependencyReport:
    package: PackageIdentifier
    health: HealthScore
    pypi: PyPIMetadata | None = None
    repository: RepositoryMetadata | None = None
    alternatives: list[AlternativePackage] = field(default_factory=list)
    update_available: str | None = None  # Latest version if different
    is_direct: bool = True  # Direct vs transitive dependency
    dependents: list[str] = field(default_factory=list)  # What depends on this
```

**Properties:**
- `needs_attention` (bool): Returns `True` if the dependency has concerning health, vulnerabilities, or maintenance status.

**Methods:**
- `to_dict()` → dict: Convert to dictionary for JSON serialization.

**Example:**

```python
report = await check("requests")

print(f"Package: {report.package}")
print(f"Health: {report.health}")

if report.update_available:
    print(f"Update available: {report.update_available}")

if report.needs_attention:
    print("\n⚠️ This dependency needs attention!")

    if report.health.has_open_vulnerabilities:
        print(f"  - {len(report.health.open_vulnerabilities)} open vulnerabilities")

    if report.health.maintenance_status.is_concerning:
        print(f"  - Maintenance status: {report.health.maintenance_status}")

# Access metadata
if report.pypi:
    print(f"\nPyPI: {report.pypi.name} v{report.pypi.version}")

if report.repository:
    print(f"Repository: {report.repository.url}")
    print(f"Stars: {report.repository.stars}")

# Convert to dict for JSON export
data = report.to_dict()
import json
print(json.dumps(data, indent=2))
```

---

## Exceptions

All exceptions inherit from `DHMError` and are importable from `dhm.core.exceptions`.

### `DHMError`

Base exception for all DHM errors.

```python
class DHMError(Exception):
    def __init__(self, message: str, details: str | None = None)
```

**Attributes:**
- `message` (str): Error message.
- `details` (str | None): Optional additional details.

**Example:**

```python
from dhm import DHMError

try:
    report = await check("nonexistent-package")
except DHMError as e:
    print(f"Error: {e.message}")
    if e.details:
        print(f"Details: {e.details}")
```

---

### `PackageNotFoundError`

Raised when a package cannot be found on PyPI.

```python
class PackageNotFoundError(DHMError):
    def __init__(self, package_name: str)
```

**Attributes:**
- `package_name` (str): Name of the package that was not found.

**Example:**

```python
from dhm import PackageNotFoundError

try:
    report = await check("this-package-does-not-exist")
except PackageNotFoundError as e:
    print(f"Package '{e.package_name}' not found on PyPI")
```

---

### `RepositoryNotFoundError`

Raised when a repository cannot be found on GitHub/GitLab.

```python
class RepositoryNotFoundError(DHMError):
    def __init__(self, repo_identifier: str)
```

**Attributes:**
- `repo_identifier` (str): Repository identifier (e.g., `"owner/repo"`).

---

### `RateLimitError`

Raised when an API rate limit is exceeded.

```python
class RateLimitError(DHMError):
    def __init__(
        self,
        service: str,
        reset_time: int | None = None,
    )
```

**Attributes:**
- `service` (str): Name of the service that rate limited (e.g., `"GitHub"`, `"PyPI"`).
- `reset_time` (int | None): Seconds until rate limit resets.

**Example:**

```python
from dhm import RateLimitError

try:
    reports = await scan(".")
except RateLimitError as e:
    print(f"Rate limit exceeded for {e.service}")
    if e.reset_time:
        print(f"Resets in {e.reset_time} seconds")
        print("Consider using a GitHub token to increase limits:")
        print('  await scan(".", github_token="your_token")')
```

---

### `CacheError`

Raised when a cache operation fails.

```python
class CacheError(DHMError):
    def __init__(self, operation: str, details: str | None = None)
```

**Attributes:**
- `operation` (str): The cache operation that failed (e.g., `"read"`, `"write"`).

---

### `ParsingError`

Raised when a dependency file cannot be parsed.

```python
class ParsingError(DHMError):
    def __init__(self, file_path: str, details: str | None = None)
```

**Attributes:**
- `file_path` (str): Path to the file that failed to parse.

**Example:**

```python
from dhm import ParsingError

try:
    reports = await scan("/path/with/invalid/requirements.txt")
except ParsingError as e:
    print(f"Failed to parse: {e.file_path}")
    print(f"Reason: {e.details}")
```

---

### `ValidationError`

Raised when data validation fails.

```python
class ValidationError(DHMError):
    def __init__(self, field: str, value: str, reason: str)
```

**Attributes:**
- `field` (str): Field name that failed validation.
- `value` (str): Invalid value.
- `reason` (str): Reason for validation failure.

---

### `NetworkError`

Raised when a network request fails.

```python
class NetworkError(DHMError):
    def __init__(
        self,
        url: str,
        status_code: int | None = None,
        details: str | None = None
    )
```

**Attributes:**
- `url` (str): URL that failed.
- `status_code` (int | None): HTTP status code (if available).

---

## Health Calculator

The `HealthCalculator` class calculates composite health scores from collected data.

```python
from dhm import HealthCalculator
```

### Constructor

```python
def __init__(
    self,
    weights: dict[str, float] | None = None,
)
```

**Parameters:**
- `weights` (dict[str, float] | None): Optional weight overrides. Keys: `'security'`, `'maintenance'`, `'community'`, `'popularity'`. Weights are automatically normalized to sum to 1.0.

**Default Weights:**
```python
{
    "security": 0.35,      # 35%
    "maintenance": 0.30,   # 30%
    "community": 0.20,     # 20%
    "popularity": 0.15,    # 15%
}
```

---

### `calculate()`

Calculate comprehensive health score.

```python
def calculate(
    self,
    pypi: PyPIMetadata | None,
    repo: RepositoryMetadata | None,
    vulnerabilities: list[Vulnerability],
) -> HealthScore
```

**Parameters:**
- `pypi` (PyPIMetadata | None): Package metadata from PyPI (may be `None`).
- `repo` (RepositoryMetadata | None): Repository metadata from GitHub/GitLab (may be `None`).
- `vulnerabilities` (list[Vulnerability]): List of known vulnerabilities.

**Returns:**
- `HealthScore`: Complete health assessment with overall score, grade, component scores, and confidence level.

**Scoring Methodology:**

The calculator uses a **weighted algorithm** combining multiple signals:

1. **Security Score (35% weight)**: Based on vulnerability count and severity.
   - Perfect score (100) if no vulnerabilities
   - Heavy penalties for open vulnerabilities
   - Minor penalties for historical fixed vulnerabilities
   - Deductions by severity:
     - CRITICAL: -40 points
     - HIGH: -25 points
     - MEDIUM: -10 points
     - LOW: -5 points
     - INFO: -1 point

2. **Maintenance Score (30% weight)**: Based on release recency and activity.
   - Recent releases (< 30 days): +20 points
   - Release consistency: +5-10 points
   - Commit frequency: +5-15 points
   - Issue responsiveness: +5-10 points
   - Archived/deprecated: -20-30 points

3. **Community Score (20% weight)**: Based on community engagement.
   - Uses logarithmic normalization for smooth curves
   - Contributors: up to +20 points (1→200 contributors)
   - Stars: up to +20 points (10→50,000 stars)
   - Forks: up to +10 points
   - PR merge rate: up to +10 points
   - Single maintainer penalty: -10 points

4. **Popularity Score (15% weight)**: Based on package adoption.
   - Downloads: up to +40 points (100→50M monthly downloads)
   - Watchers: up to +10 points
   - Uses logarithmic scaling

**Grade Thresholds:**
- **A (Excellent)**: 85-100
- **B (Good)**: 75-84
- **C (Acceptable)**: 65-74
- **D (Concerning)**: 55-64
- **F (Critical)**: 0-54

---

### Example: Custom Weights

```python
from dhm import HealthCalculator
from dhm.core.models import PyPIMetadata, RepositoryMetadata

# Emphasize security over popularity
calculator = HealthCalculator(weights={
    "security": 0.50,      # 50%
    "maintenance": 0.30,   # 30%
    "community": 0.15,     # 15%
    "popularity": 0.05,    # 5%
})

# Calculate health
health = calculator.calculate(pypi, repo, vulnerabilities)
print(f"Security-focused score: {health.grade}")
```

---

### Component Score Details

#### Security Score

```python
def _calculate_security_score(
    self,
    vulnerabilities: list[Vulnerability],
) -> float
```

- Perfect 100 if no vulnerabilities
- Differentiates between open (heavy penalty) and fixed (minor penalty) vulnerabilities
- Fixed vulnerabilities show responsive maintainers

#### Maintenance Score

```python
def _calculate_maintenance_score(
    self,
    pypi: PyPIMetadata | None,
    repo: RepositoryMetadata | None,
) -> float
```

- Base score: 50
- Recent releases: +5-20 points based on recency
- Release consistency: +5-10 points for mature projects
- Commit frequency: +5-15 points
- Issue close rate: +5-10 points
- Deprecated/archived: -20-30 points

#### Community Score

```python
def _calculate_community_score(
    self,
    repo: RepositoryMetadata | None,
) -> float
```

- Base score: 50 (neutral without data)
- Logarithmic normalization for smooth curves
- Contributors, stars, forks, PR merge rate
- Single maintainer penalty (bus factor risk)

#### Popularity Score

```python
def _calculate_popularity_score(
    self,
    pypi: PyPIMetadata | None,
    repo: RepositoryMetadata | None,
) -> float
```

- Base score: 50 (neutral - don't penalize niche packages)
- Downloads are primary signal (from pypistats.org)
- Logarithmic scaling: 100 downloads → 50M downloads
- Watchers provide secondary signal

#### License Score

```python
def _calculate_license_score(
    self,
    pypi: PyPIMetadata | None,
    repo: RepositoryMetadata | None,
) -> float
```

- Permissive licenses (MIT, Apache, BSD): 100 points
- Weak copyleft (LGPL, MPL): 75 points
- Strong copyleft (GPL, AGPL): 60 points
- No license/unknown: 30-50 points

---

### Confidence Levels

```python
def _determine_confidence(
    self,
    pypi: PyPIMetadata | None,
    repo: RepositoryMetadata | None,
) -> ConfidenceLevel
```

**HIGH Confidence:**
- PyPI metadata available
- GitHub/repo metadata available
- Download stats available (non-zero)

**MEDIUM Confidence:**
- Missing GitHub data (e.g., rate limited) OR
- Missing download stats

**LOW Confidence:**
- Missing PyPI data OR
- Multiple data sources missing

---

## Dependency Resolver

The `DependencyResolver` class parses various dependency file formats.

```python
from dhm import DependencyResolver
```

### Constructor

```python
def __init__(self)
```

Initializes with default parsers for:
- `pyproject.toml` (PEP 621 and Poetry formats)
- `requirements.txt` (and variants like `requirements-dev.txt`)

---

### `resolve()`

Find and parse all dependency files in a project.

```python
def resolve(self, project_path: Path) -> list[PackageIdentifier]
```

**Parameters:**
- `project_path` (Path): Path to project root or a specific dependency file.

**Returns:**
- `list[PackageIdentifier]`: Deduplicated list of packages.

**Supported Files:**
- `pyproject.toml` (PEP 621 `[project.dependencies]` and Poetry `[tool.poetry.dependencies]`)
- `requirements.txt`
- `requirements-dev.txt`, `requirements-test.txt`, `requirements-prod.txt`
- Any file matching `requirements*.txt`

**Example:**

```python
from pathlib import Path
from dhm import DependencyResolver

resolver = DependencyResolver()

# Resolve from project directory
packages = resolver.resolve(Path("/path/to/project"))
print(f"Found {len(packages)} dependencies")

for pkg in packages:
    print(f"  - {pkg}")
```

---

### `resolve_file()`

Parse a specific dependency file.

```python
def resolve_file(self, file_path: Path) -> list[PackageIdentifier]
```

**Parameters:**
- `file_path` (Path): Path to the dependency file.

**Returns:**
- `list[PackageIdentifier]`: List of packages.

**Raises:**
- `ParsingError`: If no suitable parser is found or parsing fails.

**Example:**

```python
from pathlib import Path
from dhm import DependencyResolver
from dhm.core.exceptions import ParsingError

resolver = DependencyResolver()

try:
    packages = resolver.resolve_file(Path("requirements.txt"))
    for pkg in packages:
        print(pkg)
except ParsingError as e:
    print(f"Failed to parse: {e}")
```

---

### `add_source()`

Add a custom dependency source parser.

```python
def add_source(self, source: DependencySource) -> None
```

**Parameters:**
- `source` (DependencySource): A custom parser implementing the `DependencySource` interface.

**Example: Custom Parser**

```python
from pathlib import Path
from dhm import DependencyResolver
from dhm.core.resolver import DependencySource
from dhm.core.models import PackageIdentifier

class PipfileLockSource(DependencySource):
    """Parse Pipfile.lock"""

    def can_parse(self, path: Path) -> bool:
        return path.name == "Pipfile.lock"

    def parse(self, path: Path) -> list[PackageIdentifier]:
        import json
        data = json.loads(path.read_text())
        packages = []

        for name, info in data.get("default", {}).items():
            version = info.get("version", "").lstrip("==")
            packages.append(PackageIdentifier(name=name, version=version))

        return packages

# Add custom parser
resolver = DependencyResolver()
resolver.add_source(PipfileLockSource())

# Now can parse Pipfile.lock
packages = resolver.resolve(Path("/path/to/project"))
```

---

### Parsing Details

#### `requirements.txt` Format

Supports:
- Simple package names: `requests`
- Version specifiers: `requests>=2.28.0`, `django==4.2.0`
- Extras: `requests[security,socks]`
- Environment markers: `pytest; python_version >= "3.8"`
- Comments: `# This is a comment`
- Include directives: `-r requirements-dev.txt`
- Editable installs are skipped: `-e .`
- URLs and VCS links are skipped

**Example:**

```text
# Core dependencies
requests>=2.28.0
django==4.2.0
flask[async]>=2.3.0

# Include dev dependencies
-r requirements-dev.txt

# Platform-specific
pywin32>=305; sys_platform == "win32"
```

#### `pyproject.toml` Format

**PEP 621 format:**

```toml
[project]
dependencies = [
    "requests>=2.28.0",
    "django==4.2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "black>=23.0.0",
]
```

**Poetry format:**

```toml
[tool.poetry.dependencies]
python = "^3.10"
requests = "^2.28.0"
django = {version = "^4.2", extras = ["psycopg2"]}

[tool.poetry.group.dev.dependencies]
pytest = "^7.0.0"
```

---

## Report Generator

The `ReportGenerator` class orchestrates the entire health report generation process.

```python
from dhm.reports.generator import ReportGenerator
```

### Constructor

```python
def __init__(
    self,
    github_token: str | None = None,
    cache_ttl: int = 3600,
    use_cache: bool = True,
)
```

**Parameters:**
- `github_token` (str | None): Optional GitHub API token for higher rate limits.
- `cache_ttl` (int): Cache time-to-live in seconds. Default: 3600 (1 hour).
- `use_cache` (bool): Whether to enable caching. Default: `True`.

---

### `generate()`

Generate a health report for a project.

```python
async def generate(
    self,
    project_path: Path,
    output_format: str = "table",
    output_path: Path | None = None,
) -> tuple[list[DependencyReport], str]
```

**Parameters:**
- `project_path` (Path): Path to project root or dependency file.
- `output_format` (str): Output format: `"json"`, `"markdown"`, or `"table"`. Default: `"table"`.
- `output_path` (Path | None): Optional path to write output file.

**Returns:**
- `tuple[list[DependencyReport], str]`: List of reports and formatted output string.

**Example:**

```python
from pathlib import Path
from dhm.reports.generator import ReportGenerator

async def main():
    generator = ReportGenerator(github_token="ghp_...")

    # Generate markdown report
    reports, markdown = await generator.generate(
        project_path=Path("."),
        output_format="markdown",
        output_path=Path("health-report.md")
    )

    print(f"Generated report for {len(reports)} dependencies")
    print(markdown)
```

---

### `generate_reports()`

Generate health reports for a list of packages.

```python
async def generate_reports(
    self,
    packages: list[PackageIdentifier],
) -> list[DependencyReport]
```

**Parameters:**
- `packages` (list[PackageIdentifier]): List of packages to analyze.

**Returns:**
- `list[DependencyReport]`: List of health reports.

**Example:**

```python
from dhm.reports.generator import ReportGenerator
from dhm.core.models import PackageIdentifier

async def main():
    generator = ReportGenerator()

    packages = [
        PackageIdentifier(name="requests"),
        PackageIdentifier(name="flask", version="2.0.0"),
        PackageIdentifier(name="django"),
    ]

    reports = await generator.generate_reports(packages)

    for report in reports:
        print(f"{report.package.name}: {report.health.grade}")
```

---

### `check_package()`

Check health of a single package.

```python
async def check_package(
    self,
    name: str,
    version: str | None = None,
) -> DependencyReport
```

**Parameters:**
- `name` (str): Package name.
- `version` (str | None): Optional specific version.

**Returns:**
- `DependencyReport`: Health report for the package.

**Example:**

```python
from dhm.reports.generator import ReportGenerator

async def main():
    generator = ReportGenerator()
    report = await generator.check_package("requests", version="2.31.0")

    print(f"Package: {report.package}")
    print(f"Health: {report.health.grade}")
```

---

### `format_reports()`

Format reports using the specified formatter.

```python
def format_reports(
    self,
    reports: list[DependencyReport],
    format_name: str = "table",
) -> str
```

**Parameters:**
- `reports` (list[DependencyReport]): List of reports to format.
- `format_name` (str): Formatter name: `"json"`, `"markdown"`, or `"table"`.

**Returns:**
- `str`: Formatted output string.

**Raises:**
- `ValueError`: If `format_name` is not recognized.

**Example:**

```python
# JSON format
json_output = generator.format_reports(reports, "json")
print(json_output)

# Markdown format
markdown_output = generator.format_reports(reports, "markdown")
with open("report.md", "w") as f:
    f.write(markdown_output)

# Table format (CLI-friendly)
table_output = generator.format_reports(reports, "table")
print(table_output)
```

---

### `add_formatter()`

Add a custom formatter.

```python
def add_formatter(self, name: str, formatter: Formatter) -> None
```

**Parameters:**
- `name` (str): Name for the formatter.
- `formatter` (Formatter): Formatter instance implementing the `Formatter` interface.

**Example: Custom HTML Formatter**

```python
from dhm.reports.formatters import Formatter
from dhm.core.models import DependencyReport

class HTMLFormatter(Formatter):
    """Format reports as HTML"""

    def format(self, reports: list[DependencyReport]) -> str:
        html = ["<html><body>"]
        html.append("<h1>Dependency Health Report</h1>")

        for report in reports:
            grade_color = {
                "A": "green", "B": "blue",
                "C": "yellow", "D": "orange", "F": "red"
            }[report.health.grade.value]

            html.append(f'<div style="border: 2px solid {grade_color};">')
            html.append(f'<h2>{report.package.name}</h2>')
            html.append(f'<p>Grade: {report.health.grade}</p>')
            html.append('</div>')

        html.append("</body></html>")
        return "\n".join(html)

# Add custom formatter
generator = ReportGenerator()
generator.add_formatter("html", HTMLFormatter())

# Use it
html_output = generator.format_reports(reports, "html")
```

---

## Complete Usage Example

Here's a comprehensive example demonstrating the full API:

```python
import asyncio
from pathlib import Path
from dhm import (
    check,
    scan,
    check_packages,
    HealthGrade,
    RiskLevel,
    MaintenanceStatus,
)

async def main():
    # Example 1: Check a single package
    print("=" * 60)
    print("Example 1: Check single package")
    print("=" * 60)

    report = await check("requests", version="2.31.0")

    print(f"\nPackage: {report.package}")
    print(f"Health Grade: {report.health.grade} ({report.health.overall:.1f}/100)")
    print(f"Confidence: {report.health.confidence}")

    # Component scores
    print(f"\nComponent Scores:")
    print(f"  Security:    {report.health.security_score:.1f}")
    print(f"  Maintenance: {report.health.maintenance_score:.1f}")
    print(f"  Community:   {report.health.community_score:.1f}")
    print(f"  Popularity:  {report.health.popularity_score:.1f}")

    # Vulnerabilities
    if report.health.has_open_vulnerabilities:
        print(f"\n⚠️  Open Vulnerabilities: {len(report.health.open_vulnerabilities)}")
        for vuln in report.health.open_vulnerabilities:
            print(f"  - {vuln.id} ({vuln.severity}): {vuln.title}")
            if vuln.fixed_version:
                print(f"    Fix available: {vuln.fixed_version}")
    else:
        print("\n✓ No open vulnerabilities")

    # Metadata
    if report.pypi:
        print(f"\nPyPI Info:")
        print(f"  Version: {report.pypi.version}")
        print(f"  Downloads: {report.pypi.downloads_last_month:,}/month")
        print(f"  License: {report.pypi.license}")

    if report.repository:
        print(f"\nRepository Info:")
        print(f"  URL: {report.repository.url}")
        print(f"  Stars: {report.repository.stars:,}")
        print(f"  Contributors: {report.repository.contributors_count}")

    # Example 2: Scan project dependencies
    print("\n" + "=" * 60)
    print("Example 2: Scan project dependencies")
    print("=" * 60)

    reports = await scan(".")

    print(f"\nScanned {len(reports)} dependencies")

    # Summary by grade
    grade_counts = {}
    for r in reports:
        grade = r.health.grade.value
        grade_counts[grade] = grade_counts.get(grade, 0) + 1

    print("\nGrade Distribution:")
    for grade in ["A", "B", "C", "D", "F"]:
        count = grade_counts.get(grade, 0)
        if count > 0:
            print(f"  {grade}: {count}")

    # Find concerning packages
    concerning = [r for r in reports if r.health.is_concerning]
    if concerning:
        print(f"\n⚠️  {len(concerning)} concerning dependencies:")
        for r in concerning:
            print(f"  - {r.package.name}: {r.health.grade}")
            for risk in r.health.risk_factors[:3]:  # Show first 3 risks
                print(f"    • {risk}")

    # Find packages with vulnerabilities
    vulnerable = [r for r in reports if r.health.has_open_vulnerabilities]
    if vulnerable:
        print(f"\n🔴 {len(vulnerable)} packages with open vulnerabilities:")
        for r in vulnerable:
            critical = len([v for v in r.health.vulnerabilities
                          if v.severity == RiskLevel.CRITICAL and v.is_open])
            high = len([v for v in r.health.vulnerabilities
                       if v.severity == RiskLevel.HIGH and v.is_open])
            print(f"  - {r.package.name}: {critical} critical, {high} high")

    # Example 3: Check multiple packages
    print("\n" + "=" * 60)
    print("Example 3: Check multiple packages")
    print("=" * 60)

    packages = ["flask", "django", "fastapi", "requests"]
    reports = await check_packages(packages)

    # Sort by health score
    reports.sort(key=lambda r: r.health.overall, reverse=True)

    print("\nPackages ranked by health:")
    for r in reports:
        health = r.health
        status = "✓" if health.is_healthy else ("⚠️" if health.grade == HealthGrade.C else "✗")
        print(f"  {status} {r.package.name:20} {health.grade} ({health.overall:.0f})")

    # Example 4: Advanced filtering
    print("\n" + "=" * 60)
    print("Example 4: Advanced filtering")
    print("=" * 60)

    reports = await scan(".")

    # Find abandoned packages
    abandoned = [r for r in reports
                 if r.health.maintenance_status == MaintenanceStatus.ABANDONED]
    if abandoned:
        print(f"\n🔴 {len(abandoned)} abandoned packages:")
        for r in abandoned:
            print(f"  - {r.package.name}")

    # Find packages without updates
    stale = [r for r in reports if r.update_available]
    if stale:
        print(f"\n📦 {len(stale)} packages with updates available:")
        for r in stale:
            print(f"  - {r.package.name}: {r.package.version} → {r.update_available}")

    # Find highly-maintained packages
    healthy = [r for r in reports if r.health.grade in (HealthGrade.A, HealthGrade.B)]
    print(f"\n✓ {len(healthy)} healthy packages (grades A-B)")

    # Example 5: Export to JSON
    print("\n" + "=" * 60)
    print("Example 5: Export to JSON")
    print("=" * 60)

    from dhm.reports.generator import ReportGenerator

    generator = ReportGenerator()
    reports, json_output = await generator.generate(
        project_path=Path("."),
        output_format="json",
        output_path=Path("health-report.json")
    )

    print(f"Exported report to health-report.json")
    print(f"Report size: {len(json_output)} bytes")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Rate Limits and Caching

### Rate Limits

DHM makes requests to multiple external APIs:

- **PyPI API**: No rate limits for public packages
- **pypistats.org**: Rate limited to ~100 requests/minute
- **GitHub API**:
  - Unauthenticated: 60 requests/hour
  - Authenticated: 5,000 requests/hour (use `github_token`)
- **OSV.dev (vulnerabilities)**: No official rate limits

**Best Practices:**

1. **Use GitHub Token**: Always provide a GitHub token for production use:

```python
import os
from dhm import scan

reports = await scan(".", github_token=os.getenv("GITHUB_TOKEN"))
```

2. **Enable Caching**: Cache is enabled by default and significantly reduces API calls:

```python
from dhm import check

# Uses cache (default)
report = await check("requests", use_cache=True)

# Disable for fresh data
report = await check("requests", use_cache=False)
```

3. **Adjust Cache TTL**: Customize cache expiration:

```python
from dhm.reports.generator import ReportGenerator

# Cache for 2 hours
generator = ReportGenerator(cache_ttl=7200)
```

---

### Cache Behavior

DHM uses SQLite-based caching (stored in `~/.dhm/cache.db`).

**Cached Data:**
- PyPI metadata (package info, releases)
- GitHub repository metadata
- Download statistics (pypistats)
- Vulnerability scan results (OSV.dev)

**Cache Keys:**
- Format: `{source}:{package}:{version}:{timestamp}`
- Example: `pypi:requests:2.31.0:1234567890`

**Cache Management:**

```python
from dhm.cache.sqlite import CacheLayer

# Manual cache management
cache = CacheLayer(default_ttl=3600)

# Clear specific entry
cache.delete("pypi:requests:2.31.0")

# Clear all expired entries
# (Automatically done on initialization)

# Disable cache entirely
generator = ReportGenerator(use_cache=False)
```

---

## Advanced Topics

### Custom Weight Configuration

Adjust scoring weights to match your priorities:

```python
from dhm import HealthCalculator

# Security-first organization
security_focused = HealthCalculator(weights={
    "security": 0.60,      # 60% - Top priority
    "maintenance": 0.25,   # 25% - Important
    "community": 0.10,     # 10% - Less important
    "popularity": 0.05,    # 5% - Least important
})

# Community-driven projects
community_focused = HealthCalculator(weights={
    "security": 0.30,
    "maintenance": 0.20,
    "community": 0.35,     # 35% - Value community
    "popularity": 0.15,
})

# Use custom calculator
from dhm.reports.generator import ReportGenerator

generator = ReportGenerator()
generator.calculator = security_focused
```

---

### Batch Processing

Process large numbers of packages efficiently:

```python
import asyncio
from dhm import check_packages

async def batch_check(package_list: list[str], batch_size: int = 50):
    """Check packages in batches to avoid overwhelming APIs"""
    results = []

    for i in range(0, len(package_list), batch_size):
        batch = package_list[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}...")

        reports = await check_packages(batch)
        results.extend(reports)

        # Rate limit courtesy pause
        if i + batch_size < len(package_list):
            await asyncio.sleep(2)

    return results

# Process 200 packages
packages = ["requests", "flask", "django", ...]  # 200 packages
reports = await batch_check(packages)
```

---

### Monitoring and Alerts

Set up automated dependency monitoring:

```python
import asyncio
from dhm import scan, HealthGrade

async def monitor_dependencies(project_path: str, alert_threshold: HealthGrade = HealthGrade.C):
    """Monitor dependencies and alert on issues"""
    reports = await scan(project_path)

    alerts = []
    for report in reports:
        # Alert on poor health
        if report.health.grade.value > alert_threshold.value:
            alerts.append(f"Low health: {report.package.name} = {report.health.grade}")

        # Alert on critical vulnerabilities
        if report.health.critical_vulnerabilities:
            alerts.append(
                f"CRITICAL vulnerability in {report.package.name}: "
                f"{len(report.health.critical_vulnerabilities)} found"
            )

        # Alert on maintenance issues
        if report.health.maintenance_status.is_concerning:
            alerts.append(
                f"Maintenance issue: {report.package.name} is "
                f"{report.health.maintenance_status.value}"
            )

    if alerts:
        # Send alerts (email, Slack, etc.)
        for alert in alerts:
            print(f"🚨 ALERT: {alert}")
        return False
    else:
        print("✓ All dependencies healthy")
        return True

# Run as part of CI/CD
healthy = await monitor_dependencies(".")
exit(0 if healthy else 1)
```

---

### Integration with CI/CD

Example GitHub Actions workflow:

```yaml
name: Dependency Health Check

on:
  schedule:
    - cron: '0 0 * * 1'  # Weekly on Monday
  pull_request:
    paths:
      - 'requirements.txt'
      - 'pyproject.toml'

jobs:
  health-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install DHM
        run: pip install dependency-health-monitor

      - name: Run health check
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          dhm scan . --format markdown --output report.md

      - name: Upload report
        uses: actions/upload-artifact@v3
        with:
          name: health-report
          path: report.md

      - name: Check for critical issues
        run: |
          dhm scan . --format json --output report.json
          # Parse JSON and fail if critical vulnerabilities found
          python -c "
          import json, sys
          with open('report.json') as f:
              data = json.load(f)
          critical = sum(1 for r in data['reports']
                        if r['health']['grade'] == 'F')
          if critical > 0:
              print(f'Found {critical} critical dependencies!')
              sys.exit(1)
          "
```

---

## FAQ

### How accurate are the health scores?

Health scores combine objective metrics (vulnerabilities, downloads, commit frequency) with heuristic classifications (maintenance status). Scores are most accurate when all data sources are available (HIGH confidence). Always review the detailed breakdown and risk factors.

### What if a package has no GitHub repository?

DHM will calculate a score based on PyPI data alone. The confidence level will be MEDIUM or LOW. Community and code quality scores will default to neutral (50).

### How often should I run health checks?

- **Development**: Weekly scans during development
- **CI/CD**: On every PR that modifies dependencies
- **Production**: Weekly or monthly scheduled scans
- **Security-critical**: Daily scans with vulnerability focus

### Can I use DHM offline?

No, DHM requires internet access to fetch data from PyPI, GitHub, and vulnerability databases. However, cached data can be used for subsequent runs.

### How do I handle rate limits?

1. Use a GitHub token (`github_token="..."`)
2. Enable caching (default)
3. Process packages in batches with delays
4. Run checks during off-peak hours

### What Python versions are supported?

DHM supports Python 3.10+.

---

## Additional Resources

- **GitHub Repository**: https://github.com/jeremylaratro/dhm
- **PyPI Package**: https://pypi.org/project/dhm/
- **Issue Tracker**: https://github.com/jeremylaratro/dhm/issues
- **Contributing Guide**: See CONTRIBUTING.md in the repository

---

**Document Version**: 0.1.0
**Last Updated**: 2026-01-29
**DHM Version**: 0.1.0
