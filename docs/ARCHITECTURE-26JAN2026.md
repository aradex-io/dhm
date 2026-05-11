> **Status:** Superseded by `architecture.md`. Retained for historical context.

# Dependency Health Monitor - Architecture Document

**Document Date:** 26 January 2026
**Version:** 1.0
**Status:** Planning Phase

---

## 1. Executive Summary

The Dependency Health Monitor (DHM) is a Python library and CLI tool that provides comprehensive health assessments for project dependencies. It aggregates data from multiple sources (PyPI, GitHub, GitLab, security databases) to calculate composite health scores, identify vulnerabilities, detect unmaintained packages, and recommend safer alternatives.

### Core Value Proposition
- **Single source of truth** for dependency health
- **Proactive risk identification** before problems occur
- **Actionable recommendations** with specific alternatives
- **CI/CD integration** for automated dependency governance

---

## 2. System Overview

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interfaces                          │
├─────────────┬─────────────┬─────────────┬─────────────────────┤
│    CLI      │  Python API │   CI/CD     │   IDE Plugins       │
└──────┬──────┴──────┬──────┴──────┬──────┴──────────┬──────────┘
       │             │             │                  │
       └─────────────┴──────┬──────┴──────────────────┘
                            │
┌───────────────────────────┴───────────────────────────────────┐
│                      Core Engine                               │
├────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │  Dependency  │  │    Health    │  │    Alternatives      │ │
│  │   Resolver   │  │  Calculator  │  │    Recommender       │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ Vulnerability│  │    Report    │  │      Cache           │ │
│  │   Scanner    │  │   Generator  │  │      Layer           │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
└───────────────────────────┬───────────────────────────────────┘
                            │
┌───────────────────────────┴───────────────────────────────────┐
│                     Data Collectors                            │
├──────────────┬──────────────┬──────────────┬─────────────────┤
│    PyPI      │    GitHub    │   Security   │   Libraries.io  │
│   Client     │    Client    │   Databases  │     Client      │
└──────────────┴──────────────┴──────────────┴─────────────────┘
                            │
┌───────────────────────────┴───────────────────────────────────┐
│                    External Services                           │
├──────────────┬──────────────┬──────────────┬─────────────────┤
│  PyPI API    │  GitHub API  │  OSV/NVD     │  Libraries.io   │
│              │  GitLab API  │  Safety DB   │                 │
└──────────────┴──────────────┴──────────────┴─────────────────┘
```

### 2.2 Design Principles

1. **Offline-First**: Cache aggressively, work without network when possible
2. **Fail-Safe**: Graceful degradation when APIs are unavailable
3. **Extensible**: Plugin architecture for new data sources
4. **Fast**: Parallel fetching, smart caching, incremental updates
5. **Actionable**: Every warning includes a recommendation

---

## 3. Data Models

### 3.1 Core Types

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

class HealthGrade(Enum):
    """Letter grades for dependency health."""
    A = "A"  # Excellent (90-100)
    B = "B"  # Good (80-89)
    C = "C"  # Acceptable (70-79)
    D = "D"  # Concerning (60-69)
    F = "F"  # Critical (<60)

class RiskLevel(Enum):
    """Risk severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class MaintenanceStatus(Enum):
    """Package maintenance classification."""
    ACTIVE = "active"           # Regular updates, responsive maintainer
    STABLE = "stable"           # Mature, infrequent but intentional updates
    SLOW = "slow"               # Occasional updates, slow response
    MINIMAL = "minimal"         # Rare updates, unclear maintenance
    ABANDONED = "abandoned"     # No updates, unresponsive
    ARCHIVED = "archived"       # Explicitly marked as archived
    DEPRECATED = "deprecated"   # Officially deprecated

@dataclass
class PackageIdentifier:
    """Uniquely identifies a package."""
    name: str
    version: Optional[str] = None
    extras: tuple[str, ...] = ()

    def __str__(self) -> str:
        result = self.name
        if self.extras:
            result += f"[{','.join(self.extras)}]"
        if self.version:
            result += f"=={self.version}"
        return result

@dataclass
class Vulnerability:
    """Security vulnerability information."""
    id: str                          # CVE-2024-XXXX or GHSA-XXXX
    severity: RiskLevel
    title: str
    description: str
    affected_versions: str           # Version specifier
    fixed_version: Optional[str]     # Version that fixes it
    published: datetime
    references: list[str] = field(default_factory=list)
    cvss_score: Optional[float] = None

@dataclass
class PyPIMetadata:
    """Metadata from PyPI."""
    name: str
    version: str
    summary: str
    author: str
    author_email: Optional[str]
    license: Optional[str]
    python_requires: Optional[str]
    requires_dist: list[str]
    project_urls: dict[str, str]
    classifiers: list[str]
    downloads_last_month: int
    release_date: datetime
    first_release_date: datetime
    total_releases: int
    yanked_releases: int

@dataclass
class RepositoryMetadata:
    """Metadata from source repository (GitHub/GitLab)."""
    url: str
    stars: int
    forks: int
    open_issues: int
    open_pull_requests: int
    watchers: int
    contributors_count: int
    last_commit_date: datetime
    created_date: datetime
    is_archived: bool
    is_fork: bool
    license: Optional[str]
    topics: list[str]
    default_branch: str

    # Calculated metrics
    commit_frequency_30d: float      # Commits per day
    issue_close_rate_90d: float      # Percentage closed
    pr_merge_rate_90d: float         # Percentage merged
    avg_issue_close_time_days: float
    avg_pr_merge_time_days: float

@dataclass
class HealthScore:
    """Composite health score for a package."""
    overall: float                   # 0-100
    grade: HealthGrade

    # Component scores (0-100)
    security_score: float
    maintenance_score: float
    community_score: float
    popularity_score: float
    code_quality_score: float

    # Detailed breakdown
    maintenance_status: MaintenanceStatus
    vulnerabilities: list[Vulnerability]
    risk_factors: list[str]
    positive_factors: list[str]

    # Metadata
    calculated_at: datetime
    data_freshness: dict[str, datetime]  # Source -> last updated

@dataclass
class DependencyReport:
    """Complete health report for a dependency."""
    package: PackageIdentifier
    health: HealthScore
    pypi: Optional[PyPIMetadata]
    repository: Optional[RepositoryMetadata]
    alternatives: list["AlternativePackage"]
    update_available: Optional[str]  # Latest version if different
    is_direct: bool                  # Direct vs transitive dependency
    dependents: list[str]            # What depends on this

@dataclass
class AlternativePackage:
    """A recommended alternative package."""
    package: PackageIdentifier
    health_score: float
    migration_effort: str            # "low", "medium", "high"
    rationale: str
    api_compatibility: float         # 0-1, how similar the API is
```

---

## 4. Component Architecture

### 4.1 Dependency Resolver

Parses and resolves dependencies from various sources.

```python
from abc import ABC, abstractmethod
from pathlib import Path

class DependencySource(ABC):
    """Base class for dependency sources."""

    @abstractmethod
    def parse(self, path: Path) -> list[PackageIdentifier]:
        """Extract dependencies from a file."""
        pass

    @abstractmethod
    def can_parse(self, path: Path) -> bool:
        """Check if this source can parse the file."""
        pass

class RequirementsTxtSource(DependencySource):
    """Parse requirements.txt files."""

    def can_parse(self, path: Path) -> bool:
        return path.name in (
            "requirements.txt",
            "requirements-dev.txt",
            "requirements-test.txt",
        ) or path.name.startswith("requirements")

    def parse(self, path: Path) -> list[PackageIdentifier]:
        # Handle: package==1.0.0, package>=1.0, package[extra], -r includes
        ...

class PyProjectTomlSource(DependencySource):
    """Parse pyproject.toml (PEP 621 and Poetry)."""

    def can_parse(self, path: Path) -> bool:
        return path.name == "pyproject.toml"

    def parse(self, path: Path) -> list[PackageIdentifier]:
        # Handle: [project.dependencies], [tool.poetry.dependencies]
        ...

class SetupPySource(DependencySource):
    """Parse setup.py files (legacy)."""
    ...

class PipfileLockSource(DependencySource):
    """Parse Pipfile.lock for exact versions."""
    ...

class PoetryLockSource(DependencySource):
    """Parse poetry.lock for exact versions."""
    ...

class DependencyResolver:
    """Orchestrates dependency resolution."""

    def __init__(self):
        self.sources: list[DependencySource] = [
            PyProjectTomlSource(),
            RequirementsTxtSource(),
            PoetryLockSource(),
            PipfileLockSource(),
            SetupPySource(),
        ]

    def resolve(self, project_path: Path) -> list[PackageIdentifier]:
        """Find and parse all dependency files in a project."""
        dependencies = []
        for file in self._find_dependency_files(project_path):
            for source in self.sources:
                if source.can_parse(file):
                    dependencies.extend(source.parse(file))
                    break
        return self._deduplicate(dependencies)

    def resolve_transitive(
        self,
        direct: list[PackageIdentifier],
    ) -> dict[str, list[str]]:
        """Build dependency tree including transitive deps."""
        # Use pip's resolver or build dependency graph
        ...
```

### 4.2 Data Collectors

#### PyPI Client

```python
import aiohttp
from datetime import datetime

class PyPIClient:
    """Async client for PyPI JSON API."""

    BASE_URL = "https://pypi.org/pypi"

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    async def get_package_info(self, name: str) -> PyPIMetadata:
        """Fetch package metadata from PyPI."""
        url = f"{self.BASE_URL}/{name}/json"
        async with self.session.get(url) as resp:
            if resp.status == 404:
                raise PackageNotFoundError(name)
            data = await resp.json()
            return self._parse_response(data)

    async def get_release_history(
        self,
        name: str,
    ) -> list[dict]:
        """Get all releases with dates."""
        url = f"{self.BASE_URL}/{name}/json"
        async with self.session.get(url) as resp:
            data = await resp.json()
            releases = []
            for version, files in data["releases"].items():
                if files:  # Skip yanked/empty releases
                    releases.append({
                        "version": version,
                        "upload_time": files[0]["upload_time"],
                        "yanked": files[0].get("yanked", False),
                    })
            return sorted(releases, key=lambda r: r["upload_time"])

    def _parse_response(self, data: dict) -> PyPIMetadata:
        info = data["info"]
        releases = data["releases"]

        # Calculate download stats from recent releases
        downloads = self._estimate_downloads(releases)

        return PyPIMetadata(
            name=info["name"],
            version=info["version"],
            summary=info.get("summary", ""),
            author=info.get("author", ""),
            author_email=info.get("author_email"),
            license=info.get("license"),
            python_requires=info.get("requires_python"),
            requires_dist=info.get("requires_dist") or [],
            project_urls=info.get("project_urls") or {},
            classifiers=info.get("classifiers") or [],
            downloads_last_month=downloads,
            release_date=self._parse_release_date(releases, info["version"]),
            first_release_date=self._find_first_release(releases),
            total_releases=len(releases),
            yanked_releases=self._count_yanked(releases),
        )
```

#### GitHub Client

```python
class GitHubClient:
    """Async client for GitHub API."""

    BASE_URL = "https://api.github.com"

    def __init__(
        self,
        session: aiohttp.ClientSession,
        token: Optional[str] = None,
    ):
        self.session = session
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            self.headers["Authorization"] = f"token {token}"

    async def get_repository(
        self,
        owner: str,
        repo: str,
    ) -> RepositoryMetadata:
        """Fetch repository metadata."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}"
        async with self.session.get(url, headers=self.headers) as resp:
            if resp.status == 404:
                raise RepositoryNotFoundError(f"{owner}/{repo}")
            data = await resp.json()

            # Fetch additional metrics in parallel
            commits, issues, prs, contributors = await asyncio.gather(
                self._get_recent_commits(owner, repo),
                self._get_issue_stats(owner, repo),
                self._get_pr_stats(owner, repo),
                self._get_contributor_count(owner, repo),
            )

            return self._build_metadata(data, commits, issues, prs, contributors)

    async def _get_recent_commits(
        self,
        owner: str,
        repo: str,
        days: int = 30,
    ) -> list[dict]:
        """Get commits from last N days."""
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/commits"
        params = {"since": since, "per_page": 100}

        commits = []
        async with self.session.get(
            url,
            headers=self.headers,
            params=params,
        ) as resp:
            if resp.status == 200:
                commits = await resp.json()
        return commits

    async def _get_issue_stats(
        self,
        owner: str,
        repo: str,
    ) -> dict:
        """Calculate issue resolution statistics."""
        # Fetch closed issues from last 90 days
        # Calculate average close time, close rate
        ...

    def extract_repo_from_url(self, url: str) -> tuple[str, str]:
        """Extract owner/repo from GitHub URL."""
        # Handle: github.com/owner/repo, git@github.com:owner/repo.git
        patterns = [
            r"github\.com/([^/]+)/([^/]+?)(?:\.git)?$",
            r"github\.com:([^/]+)/([^/]+?)(?:\.git)?$",
        ]
        for pattern in patterns:
            if match := re.search(pattern, url):
                return match.groups()
        raise ValueError(f"Cannot parse GitHub URL: {url}")
```

#### Vulnerability Scanner

```python
class VulnerabilityScanner:
    """Aggregate vulnerability data from multiple sources."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        osv_enabled: bool = True,
        safety_db_enabled: bool = True,
    ):
        self.session = session
        self.sources = []
        if osv_enabled:
            self.sources.append(OSVClient(session))
        if safety_db_enabled:
            self.sources.append(SafetyDBClient(session))

    async def scan_package(
        self,
        package: PackageIdentifier,
    ) -> list[Vulnerability]:
        """Check all sources for vulnerabilities."""
        tasks = [
            source.check(package.name, package.version)
            for source in self.sources
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge and deduplicate by CVE/GHSA ID
        vulnerabilities = {}
        for result in results:
            if isinstance(result, Exception):
                continue
            for vuln in result:
                if vuln.id not in vulnerabilities:
                    vulnerabilities[vuln.id] = vuln

        return sorted(
            vulnerabilities.values(),
            key=lambda v: v.severity.value,
        )

class OSVClient:
    """Client for Open Source Vulnerabilities database."""

    BASE_URL = "https://api.osv.dev/v1"

    async def check(
        self,
        package: str,
        version: Optional[str],
    ) -> list[Vulnerability]:
        """Query OSV for vulnerabilities."""
        payload = {
            "package": {"name": package, "ecosystem": "PyPI"},
        }
        if version:
            payload["version"] = version

        url = f"{self.BASE_URL}/query"
        async with self.session.post(url, json=payload) as resp:
            data = await resp.json()
            return [
                self._parse_vuln(v)
                for v in data.get("vulns", [])
            ]
```

### 4.3 Health Calculator

The heart of the system - calculates composite health scores.

```python
class HealthCalculator:
    """Calculate health scores from collected data."""

    # Scoring weights
    WEIGHTS = {
        "security": 0.35,
        "maintenance": 0.30,
        "community": 0.20,
        "popularity": 0.15,
    }

    def calculate(
        self,
        pypi: Optional[PyPIMetadata],
        repo: Optional[RepositoryMetadata],
        vulnerabilities: list[Vulnerability],
    ) -> HealthScore:
        """Calculate comprehensive health score."""

        security = self._calculate_security_score(vulnerabilities)
        maintenance = self._calculate_maintenance_score(pypi, repo)
        community = self._calculate_community_score(repo)
        popularity = self._calculate_popularity_score(pypi, repo)

        # Weighted overall score
        overall = (
            security * self.WEIGHTS["security"]
            + maintenance * self.WEIGHTS["maintenance"]
            + community * self.WEIGHTS["community"]
            + popularity * self.WEIGHTS["popularity"]
        )

        return HealthScore(
            overall=overall,
            grade=self._score_to_grade(overall),
            security_score=security,
            maintenance_score=maintenance,
            community_score=community,
            popularity_score=popularity,
            code_quality_score=self._calculate_quality_score(repo),
            maintenance_status=self._determine_maintenance_status(pypi, repo),
            vulnerabilities=vulnerabilities,
            risk_factors=self._identify_risks(pypi, repo, vulnerabilities),
            positive_factors=self._identify_positives(pypi, repo),
            calculated_at=datetime.utcnow(),
            data_freshness={},
        )

    def _calculate_security_score(
        self,
        vulnerabilities: list[Vulnerability],
    ) -> float:
        """Score based on vulnerability count and severity."""
        if not vulnerabilities:
            return 100.0

        # Deduct points per vulnerability by severity
        deductions = {
            RiskLevel.CRITICAL: 40,
            RiskLevel.HIGH: 25,
            RiskLevel.MEDIUM: 10,
            RiskLevel.LOW: 5,
            RiskLevel.INFO: 1,
        }

        total_deduction = sum(
            deductions.get(v.severity, 5)
            for v in vulnerabilities
        )

        return max(0, 100 - total_deduction)

    def _calculate_maintenance_score(
        self,
        pypi: Optional[PyPIMetadata],
        repo: Optional[RepositoryMetadata],
    ) -> float:
        """Score based on maintenance activity."""
        score = 50.0  # Base score

        if pypi:
            # Recency of last release
            days_since_release = (
                datetime.utcnow() - pypi.release_date
            ).days
            if days_since_release < 30:
                score += 20
            elif days_since_release < 90:
                score += 15
            elif days_since_release < 180:
                score += 10
            elif days_since_release < 365:
                score += 5
            else:
                score -= 10

            # Release consistency
            if pypi.total_releases > 10:
                score += 10
            elif pypi.total_releases > 5:
                score += 5

        if repo:
            # Commit frequency
            if repo.commit_frequency_30d > 1:
                score += 15
            elif repo.commit_frequency_30d > 0.1:
                score += 10
            elif repo.commit_frequency_30d > 0:
                score += 5

            # Issue responsiveness
            if repo.issue_close_rate_90d > 0.8:
                score += 10
            elif repo.issue_close_rate_90d > 0.5:
                score += 5

            # Not archived
            if repo.is_archived:
                score -= 30

        return min(100, max(0, score))

    def _calculate_community_score(
        self,
        repo: Optional[RepositoryMetadata],
    ) -> float:
        """Score based on community engagement."""
        if not repo:
            return 50.0  # Neutral without data

        score = 0.0

        # Contributors (logarithmic scale)
        if repo.contributors_count > 100:
            score += 30
        elif repo.contributors_count > 20:
            score += 25
        elif repo.contributors_count > 5:
            score += 20
        elif repo.contributors_count > 1:
            score += 10

        # Stars (logarithmic scale)
        if repo.stars > 10000:
            score += 30
        elif repo.stars > 1000:
            score += 25
        elif repo.stars > 100:
            score += 15
        elif repo.stars > 10:
            score += 5

        # Forks indicate reusability
        if repo.forks > 100:
            score += 20
        elif repo.forks > 10:
            score += 10

        # PR merge rate shows collaboration
        if repo.pr_merge_rate_90d > 0.7:
            score += 20
        elif repo.pr_merge_rate_90d > 0.4:
            score += 10

        return min(100, score)

    def _determine_maintenance_status(
        self,
        pypi: Optional[PyPIMetadata],
        repo: Optional[RepositoryMetadata],
    ) -> MaintenanceStatus:
        """Classify maintenance status."""

        if repo and repo.is_archived:
            return MaintenanceStatus.ARCHIVED

        # Check for deprecation markers
        if pypi and self._is_deprecated(pypi):
            return MaintenanceStatus.DEPRECATED

        days_since_release = float("inf")
        if pypi:
            days_since_release = (
                datetime.utcnow() - pypi.release_date
            ).days

        days_since_commit = float("inf")
        if repo:
            days_since_commit = (
                datetime.utcnow() - repo.last_commit_date
            ).days

        min_days = min(days_since_release, days_since_commit)

        if min_days < 90:
            return MaintenanceStatus.ACTIVE
        elif min_days < 365:
            return MaintenanceStatus.STABLE
        elif min_days < 730:  # 2 years
            return MaintenanceStatus.SLOW
        elif min_days < 1095:  # 3 years
            return MaintenanceStatus.MINIMAL
        else:
            return MaintenanceStatus.ABANDONED

    def _score_to_grade(self, score: float) -> HealthGrade:
        """Convert numeric score to letter grade."""
        if score >= 90:
            return HealthGrade.A
        elif score >= 80:
            return HealthGrade.B
        elif score >= 70:
            return HealthGrade.C
        elif score >= 60:
            return HealthGrade.D
        else:
            return HealthGrade.F
```

### 4.4 Alternatives Recommender

```python
class AlternativesRecommender:
    """Find and rank alternative packages."""

    def __init__(
        self,
        pypi_client: PyPIClient,
        github_client: GitHubClient,
        health_calculator: HealthCalculator,
    ):
        self.pypi = pypi_client
        self.github = github_client
        self.calculator = health_calculator

        # Known alternatives database
        self.known_alternatives = {
            "requests": ["httpx", "aiohttp", "urllib3"],
            "flask": ["fastapi", "starlette", "litestar"],
            "django": ["fastapi", "flask", "starlette"],
            "pillow": ["opencv-python", "scikit-image"],
            "pyyaml": ["ruamel.yaml", "strictyaml"],
            "python-dateutil": ["pendulum", "arrow", "dateparser"],
            "beautifulsoup4": ["selectolax", "lxml", "parsel"],
            "nose": ["pytest"],
            "mock": ["unittest.mock"],  # stdlib
        }

    async def find_alternatives(
        self,
        package: PackageIdentifier,
        current_health: HealthScore,
    ) -> list[AlternativePackage]:
        """Find healthier alternatives for a package."""

        alternatives = []

        # Check known alternatives first
        if package.name in self.known_alternatives:
            for alt_name in self.known_alternatives[package.name]:
                alt = await self._evaluate_alternative(
                    alt_name,
                    package,
                    current_health,
                )
                if alt and alt.health_score > current_health.overall:
                    alternatives.append(alt)

        # Search for similar packages by keywords
        similar = await self._search_similar(package.name)
        for similar_name in similar[:5]:
            if similar_name == package.name:
                continue
            alt = await self._evaluate_alternative(
                similar_name,
                package,
                current_health,
            )
            if alt and alt.health_score > current_health.overall + 10:
                alternatives.append(alt)

        # Sort by health score descending
        return sorted(
            alternatives,
            key=lambda a: a.health_score,
            reverse=True,
        )[:5]

    async def _evaluate_alternative(
        self,
        name: str,
        original: PackageIdentifier,
        original_health: HealthScore,
    ) -> Optional[AlternativePackage]:
        """Evaluate a potential alternative."""
        try:
            pypi = await self.pypi.get_package_info(name)
            repo_url = pypi.project_urls.get("Repository") or \
                       pypi.project_urls.get("Source")

            repo = None
            if repo_url and "github.com" in repo_url:
                owner, repo_name = self.github.extract_repo_from_url(repo_url)
                repo = await self.github.get_repository(owner, repo_name)

            health = self.calculator.calculate(pypi, repo, [])

            return AlternativePackage(
                package=PackageIdentifier(name, pypi.version),
                health_score=health.overall,
                migration_effort=self._estimate_migration_effort(
                    original.name,
                    name,
                ),
                rationale=self._generate_rationale(health, original_health),
                api_compatibility=self._estimate_api_compatibility(
                    original.name,
                    name,
                ),
            )
        except Exception:
            return None

    def _estimate_migration_effort(
        self,
        from_pkg: str,
        to_pkg: str,
    ) -> str:
        """Estimate effort to migrate between packages."""
        # Simple heuristic based on known migrations
        easy_migrations = {
            ("requests", "httpx"),
            ("flask", "fastapi"),
            ("nose", "pytest"),
        }

        if (from_pkg, to_pkg) in easy_migrations:
            return "low"
        elif from_pkg.split("-")[0] == to_pkg.split("-")[0]:
            return "low"  # Same family
        else:
            return "medium"
```

### 4.5 Report Generator

```python
class ReportGenerator:
    """Generate health reports in various formats."""

    def __init__(self):
        self.formatters = {
            "json": JSONFormatter(),
            "markdown": MarkdownFormatter(),
            "html": HTMLFormatter(),
            "sarif": SARIFFormatter(),  # For GitHub Security
            "junit": JUnitFormatter(),   # For CI/CD
        }

    def generate(
        self,
        reports: list[DependencyReport],
        format: str = "markdown",
        output: Optional[Path] = None,
    ) -> str:
        """Generate formatted report."""
        formatter = self.formatters.get(format)
        if not formatter:
            raise ValueError(f"Unknown format: {format}")

        content = formatter.format(reports)

        if output:
            output.write_text(content)

        return content

class MarkdownFormatter:
    """Generate Markdown reports."""

    def format(self, reports: list[DependencyReport]) -> str:
        lines = ["# Dependency Health Report", ""]

        # Summary
        total = len(reports)
        healthy = sum(1 for r in reports if r.health.grade in (HealthGrade.A, HealthGrade.B))
        concerning = sum(1 for r in reports if r.health.grade in (HealthGrade.D, HealthGrade.F))

        lines.extend([
            "## Summary",
            "",
            f"- **Total Dependencies:** {total}",
            f"- **Healthy (A/B):** {healthy}",
            f"- **Concerning (D/F):** {concerning}",
            "",
        ])

        # Critical issues first
        critical = [r for r in reports if r.health.vulnerabilities]
        if critical:
            lines.extend(["## 🚨 Security Vulnerabilities", ""])
            for report in critical:
                lines.append(f"### {report.package}")
                for vuln in report.health.vulnerabilities:
                    lines.append(
                        f"- **{vuln.id}** ({vuln.severity.value}): {vuln.title}"
                    )
                    if vuln.fixed_version:
                        lines.append(f"  - Fixed in: {vuln.fixed_version}")
                lines.append("")

        # Unmaintained packages
        unmaintained = [
            r for r in reports
            if r.health.maintenance_status in (
                MaintenanceStatus.ABANDONED,
                MaintenanceStatus.ARCHIVED,
                MaintenanceStatus.DEPRECATED,
            )
        ]
        if unmaintained:
            lines.extend(["## ⚠️ Unmaintained Packages", ""])
            for report in unmaintained:
                lines.append(
                    f"- **{report.package}** - {report.health.maintenance_status.value}"
                )
                if report.alternatives:
                    alt = report.alternatives[0]
                    lines.append(
                        f"  - Consider: {alt.package} (score: {alt.health_score:.0f})"
                    )
            lines.append("")

        # Full breakdown
        lines.extend(["## All Dependencies", ""])
        lines.append("| Package | Grade | Security | Maintenance | Status |")
        lines.append("|---------|-------|----------|-------------|--------|")

        for report in sorted(reports, key=lambda r: r.health.overall):
            lines.append(
                f"| {report.package} | {report.health.grade.value} | "
                f"{report.health.security_score:.0f} | "
                f"{report.health.maintenance_score:.0f} | "
                f"{report.health.maintenance_status.value} |"
            )

        return "\n".join(lines)
```

### 4.6 Cache Layer

```python
import sqlite3
from contextlib import contextmanager

class CacheLayer:
    """SQLite-based cache for API responses."""

    def __init__(self, db_path: Path = Path.home() / ".dhm" / "cache.db"):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize cache database schema."""
        with self._connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    etag TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_expires
                ON cache(expires_at);
            """)

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def get(self, key: str) -> Optional[tuple[str, Optional[str]]]:
        """Get cached value and ETag if not expired."""
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT value, etag FROM cache
                WHERE key = ? AND expires_at > datetime('now')
                """,
                (key,),
            ).fetchone()
            return row if row else None

    def set(
        self,
        key: str,
        value: str,
        ttl_seconds: int = 3600,
        etag: Optional[str] = None,
    ):
        """Store value in cache with TTL."""
        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache (key, value, etag, expires_at)
                VALUES (?, ?, ?, datetime('now', ? || ' seconds'))
                """,
                (key, value, etag, str(ttl_seconds)),
            )

    def invalidate(self, pattern: str):
        """Invalidate cache entries matching pattern."""
        with self._connection() as conn:
            conn.execute(
                "DELETE FROM cache WHERE key LIKE ?",
                (pattern,),
            )

    def cleanup(self):
        """Remove expired entries."""
        with self._connection() as conn:
            conn.execute(
                "DELETE FROM cache WHERE expires_at < datetime('now')"
            )
```

---

## 5. CLI Interface

```python
import click
from rich.console import Console
from rich.table import Table

console = Console()

@click.group()
@click.version_option()
def cli():
    """Dependency Health Monitor - Know your dependencies."""
    pass

@cli.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--format", "-f", type=click.Choice(["table", "json", "markdown"]), default="table")
@click.option("--output", "-o", type=click.Path(), help="Output file")
@click.option("--fail-on", type=click.Choice(["critical", "high", "medium", "low"]),
              help="Exit non-zero if issues at this level or above")
@click.option("--include-transitive/--direct-only", default=True)
def scan(path, format, output, fail_on, include_transitive):
    """Scan project dependencies for health issues."""
    from dhm import DependencyHealthMonitor

    monitor = DependencyHealthMonitor()

    with console.status("Scanning dependencies..."):
        reports = monitor.scan(
            Path(path),
            include_transitive=include_transitive,
        )

    if format == "table":
        _print_table(reports)
    elif format == "json":
        _print_json(reports)
    elif format == "markdown":
        _print_markdown(reports)

    if fail_on:
        exit_code = _check_threshold(reports, fail_on)
        raise SystemExit(exit_code)

@cli.command()
@click.argument("package")
@click.option("--version", "-v", help="Specific version to check")
def check(package, version):
    """Check health of a specific package."""
    from dhm import DependencyHealthMonitor

    monitor = DependencyHealthMonitor()

    with console.status(f"Checking {package}..."):
        report = monitor.check_package(package, version)

    _print_detailed_report(report)

@cli.command()
@click.argument("package")
def alternatives(package):
    """Find healthier alternatives for a package."""
    from dhm import DependencyHealthMonitor

    monitor = DependencyHealthMonitor()

    with console.status(f"Finding alternatives for {package}..."):
        alts = monitor.find_alternatives(package)

    if not alts:
        console.print(f"No better alternatives found for {package}")
        return

    table = Table(title=f"Alternatives to {package}")
    table.add_column("Package")
    table.add_column("Health Score")
    table.add_column("Migration Effort")
    table.add_column("Rationale")

    for alt in alts:
        table.add_row(
            str(alt.package),
            f"{alt.health_score:.0f}",
            alt.migration_effort,
            alt.rationale,
        )

    console.print(table)

@cli.command()
@click.option("--clear", is_flag=True, help="Clear all cached data")
@click.option("--stats", is_flag=True, help="Show cache statistics")
def cache(clear, stats):
    """Manage the local cache."""
    from dhm.cache import CacheLayer

    cache = CacheLayer()

    if clear:
        cache.invalidate("%")
        console.print("Cache cleared")
    elif stats:
        # Show cache stats
        pass

def _print_table(reports: list):
    """Print results as a rich table."""
    table = Table(title="Dependency Health Report")

    table.add_column("Package", style="cyan")
    table.add_column("Version")
    table.add_column("Grade", justify="center")
    table.add_column("Security", justify="right")
    table.add_column("Maintenance", justify="right")
    table.add_column("Status")
    table.add_column("Issues")

    for report in sorted(reports, key=lambda r: r.health.overall):
        grade_style = {
            HealthGrade.A: "green",
            HealthGrade.B: "green",
            HealthGrade.C: "yellow",
            HealthGrade.D: "red",
            HealthGrade.F: "red bold",
        }.get(report.health.grade, "white")

        issues = []
        if report.health.vulnerabilities:
            issues.append(f"🚨 {len(report.health.vulnerabilities)} vulns")
        if report.health.maintenance_status == MaintenanceStatus.ABANDONED:
            issues.append("⚠️ abandoned")

        table.add_row(
            report.package.name,
            report.package.version or "?",
            f"[{grade_style}]{report.health.grade.value}[/]",
            f"{report.health.security_score:.0f}",
            f"{report.health.maintenance_score:.0f}",
            report.health.maintenance_status.value,
            " ".join(issues) or "✓",
        )

    console.print(table)

if __name__ == "__main__":
    cli()
```

---

## 6. Project Structure

```
dependency-health-monitor/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── dhm/
│       ├── __init__.py
│       ├── __main__.py           # CLI entry point
│       ├── cli.py                # Click commands
│       ├── core/
│       │   ├── __init__.py
│       │   ├── models.py         # Data classes
│       │   ├── monitor.py        # Main orchestrator
│       │   ├── resolver.py       # Dependency resolution
│       │   └── calculator.py     # Health scoring
│       ├── collectors/
│       │   ├── __init__.py
│       │   ├── base.py           # Collector interface
│       │   ├── pypi.py           # PyPI client
│       │   ├── github.py         # GitHub client
│       │   ├── gitlab.py         # GitLab client
│       │   └── vulnerability.py  # Security DBs
│       ├── analyzers/
│       │   ├── __init__.py
│       │   ├── alternatives.py   # Alternative finder
│       │   └── trends.py         # Trend analysis
│       ├── reports/
│       │   ├── __init__.py
│       │   ├── generator.py      # Report orchestrator
│       │   └── formatters/
│       │       ├── __init__.py
│       │       ├── json.py
│       │       ├── markdown.py
│       │       ├── html.py
│       │       └── sarif.py
│       ├── cache/
│       │   ├── __init__.py
│       │   └── sqlite.py         # Cache implementation
│       └── plugins/
│           ├── __init__.py
│           └── base.py           # Plugin interface
├── tests/
│   ├── conftest.py
│   ├── test_resolver.py
│   ├── test_calculator.py
│   ├── test_collectors/
│   │   ├── test_pypi.py
│   │   └── test_github.py
│   └── fixtures/
│       ├── requirements.txt
│       └── pyproject.toml
└── docs/
    ├── index.md
    ├── quickstart.md
    ├── configuration.md
    └── api/
```

---

## 7. Configuration

```toml
# pyproject.toml
[tool.dhm]
# Default behavior
include_transitive = true
cache_ttl = 3600  # seconds

# Thresholds for CI/CD
[tool.dhm.thresholds]
min_grade = "C"
max_vulnerabilities = 0
max_abandoned = 0

# Ignored packages (known acceptable risks)
[tool.dhm.ignore]
packages = [
    "some-internal-package",
]
vulnerabilities = [
    "CVE-2024-XXXX",  # Accepted risk with justification
]

# API tokens (prefer environment variables)
[tool.dhm.tokens]
github = "${GITHUB_TOKEN}"
```

---

## 8. Security Considerations

### 8.1 API Token Handling
- Never log or display API tokens
- Support environment variables for all credentials
- Clear tokens from memory after use
- Validate token permissions before use

### 8.2 Data Privacy
- Cache only public data
- Allow disabling telemetry
- No tracking of user projects
- Clear documentation on data collection

### 8.3 Rate Limiting
- Respect API rate limits
- Exponential backoff on failures
- User notification when rate limited
- Cache to minimize API calls

---

## 9. Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Single package check | <2s | With warm cache |
| Full project scan (50 deps) | <30s | Parallel fetching |
| Cache lookup | <10ms | SQLite indexed |
| Format detection | <100ms | Per file |

---

## 10. Risk Assessment

### Technical Risks
| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| API rate limiting | High | Medium | Aggressive caching, token rotation |
| Data source unavailability | Medium | High | Graceful degradation, multiple sources |
| Scoring algorithm gaming | Low | Medium | Multiple signals, human review |

### Business Risks
| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Similar tool emerges | Medium | High | Rapid feature development, community |
| Low adoption | Medium | High | Strong documentation, integrations |

---

*This architecture document provides the technical foundation for the Dependency Health Monitor. Implementation should follow the phased approach outlined in the companion roadmap document.*
