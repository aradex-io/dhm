"""
Core data models for the Dependency Health Monitor.

This module defines the data structures used throughout DHM for representing
packages, health scores, vulnerabilities, and other metadata.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class HealthGrade(Enum):
    """Letter grades for dependency health.

    Thresholds defined in HealthCalculator._score_to_grade.
    """

    A = "A"  # Excellent (≥85)
    B = "B"  # Good (≥75)
    C = "C"  # Acceptable (≥65)
    D = "D"  # Concerning (≥55)
    F = "F"  # Critical (<55)

    def __str__(self) -> str:
        return self.value


class ConfidenceLevel(Enum):
    """Confidence level in the calculated score based on data availability."""

    HIGH = "high"       # All data sources available (PyPI + GitHub + pypistats + vulns)
    MEDIUM = "medium"   # Some data sources unavailable (e.g., GitHub rate limited)
    LOW = "low"         # Missing critical data sources

    def __str__(self) -> str:
        return self.value


class RiskLevel(Enum):
    """Risk severity levels for vulnerabilities and issues."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    def __str__(self) -> str:
        return self.value

    @property
    def sort_order(self) -> int:
        """Return sort order (lower = more severe)."""
        order = {
            RiskLevel.CRITICAL: 0,
            RiskLevel.HIGH: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.LOW: 3,
            RiskLevel.INFO: 4,
        }
        return order[self]


class MaintenanceStatus(Enum):
    """Package maintenance classification."""

    ACTIVE = "active"  # Regular updates, responsive maintainer
    STABLE = "stable"  # Mature, infrequent but intentional updates
    SLOW = "slow"  # Occasional updates, slow response
    MINIMAL = "minimal"  # Rare updates, unclear maintenance
    ABANDONED = "abandoned"  # No updates, unresponsive
    ARCHIVED = "archived"  # Explicitly marked as archived
    DEPRECATED = "deprecated"  # Officially deprecated

    def __str__(self) -> str:
        return self.value

    @property
    def is_concerning(self) -> bool:
        """Return True if this status is concerning."""
        return self in (
            MaintenanceStatus.ABANDONED,
            MaintenanceStatus.ARCHIVED,
            MaintenanceStatus.DEPRECATED,
        )


@dataclass
class PackageIdentifier:
    """Uniquely identifies a package with optional version and extras."""

    name: str
    version: str | None = None
    extras: tuple[str, ...] = ()
    # Whether this package is a direct (declared) dependency vs a transitive one.
    # Not part of identity (see __hash__/__eq__ below).
    is_direct: bool = True

    def __str__(self) -> str:
        result = self.name
        if self.extras:
            result += f"[{','.join(self.extras)}]"
        if self.version:
            result += f"=={self.version}"
        return result

    def __hash__(self) -> int:
        return hash((self.name.lower(), self.version, self.extras))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PackageIdentifier):
            return False
        return (
            self.name.lower() == other.name.lower()
            and self.version == other.version
            and self.extras == other.extras
        )

    @property
    def normalized_name(self) -> str:
        """Return normalized package name (lowercase, underscores to hyphens)."""
        return self.name.lower().replace("_", "-")


@dataclass
class Vulnerability:
    """Security vulnerability information."""

    id: str  # CVE-2024-XXXX or GHSA-XXXX
    severity: RiskLevel
    title: str
    description: str
    affected_versions: str  # Version specifier
    fixed_version: str | None = None  # Version that fixes it
    published: datetime | None = None
    references: list[str] = field(default_factory=list)
    cvss_score: float | None = None
    is_fixed_in_installed_version: bool = False  # True if current version is patched

    def __str__(self) -> str:
        status = " [FIXED]" if self.is_fixed_in_installed_version else ""
        return f"{self.id} ({self.severity}){status}: {self.title}"

    @property
    def has_fix(self) -> bool:
        """Return True if a fixed version is available."""
        return self.fixed_version is not None

    @property
    def is_open(self) -> bool:
        """Return True if this vulnerability affects the installed version."""
        return not self.is_fixed_in_installed_version

    def to_dict(self) -> dict:
        """Convert to dictionary for caching."""
        return {
            "id": self.id,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "affected_versions": self.affected_versions,
            "fixed_version": self.fixed_version,
            "published": self.published.isoformat() if self.published else None,
            "references": self.references,
            "cvss_score": self.cvss_score,
            # Note: is_fixed_in_installed_version is NOT cached - it's computed at runtime
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Vulnerability":
        """Create from dictionary (cache retrieval)."""
        published = None
        if data.get("published"):
            try:
                published = datetime.fromisoformat(data["published"])
            except (ValueError, TypeError):
                pass

        return cls(
            id=data.get("id", ""),
            severity=RiskLevel(data.get("severity", "medium")),
            title=data.get("title", ""),
            description=data.get("description", ""),
            affected_versions=data.get("affected_versions", "*"),
            fixed_version=data.get("fixed_version"),
            published=published,
            references=data.get("references", []),
            cvss_score=data.get("cvss_score"),
            # is_fixed_in_installed_version is computed at runtime, not cached
            is_fixed_in_installed_version=False,
        )


@dataclass
class PyPIMetadata:
    """Metadata retrieved from PyPI."""

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

    @property
    def home_page(self) -> str | None:
        """Return the project home page URL."""
        return self.project_urls.get("Homepage") or self.project_urls.get("Home")

    @property
    def repository_url(self) -> str | None:
        """Return the source repository URL."""
        for key in ("Repository", "Source", "Source Code", "Code"):
            if url := self.project_urls.get(key):
                return url
        return None

    @property
    def is_deprecated(self) -> bool:
        """Check if package appears deprecated based on classifiers."""
        deprecated_classifiers = [
            "Development Status :: 7 - Inactive",
        ]
        return any(c in self.classifiers for c in deprecated_classifiers)

    def to_dict(self) -> dict:
        """Convert to dictionary for caching."""
        return {
            "name": self.name,
            "version": self.version,
            "summary": self.summary,
            "author": self.author,
            "author_email": self.author_email,
            "license": self.license,
            "python_requires": self.python_requires,
            "requires_dist": self.requires_dist,
            "project_urls": self.project_urls,
            "classifiers": self.classifiers,
            "downloads_last_month": self.downloads_last_month,
            "release_date": self.release_date.isoformat() if self.release_date else None,
            "first_release_date": (
                self.first_release_date.isoformat() if self.first_release_date else None
            ),
            "total_releases": self.total_releases,
            "yanked_releases": self.yanked_releases,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PyPIMetadata":
        """Create from dictionary (cache retrieval)."""
        release_date = None
        if data.get("release_date"):
            try:
                release_date = datetime.fromisoformat(data["release_date"])
            except (ValueError, TypeError):
                pass

        first_release = None
        if data.get("first_release_date"):
            try:
                first_release = datetime.fromisoformat(data["first_release_date"])
            except (ValueError, TypeError):
                pass

        return cls(
            name=data.get("name", ""),
            version=data.get("version", ""),
            summary=data.get("summary", ""),
            author=data.get("author", ""),
            author_email=data.get("author_email"),
            license=data.get("license"),
            python_requires=data.get("python_requires"),
            requires_dist=data.get("requires_dist", []),
            project_urls=data.get("project_urls", {}),
            classifiers=data.get("classifiers", []),
            downloads_last_month=data.get("downloads_last_month", 0),
            release_date=release_date,
            first_release_date=first_release,
            total_releases=data.get("total_releases", 0),
            yanked_releases=data.get("yanked_releases", 0),
        )


@dataclass
class RepositoryMetadata:
    """Metadata from source repository (GitHub/GitLab)."""

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
    pr_merge_rate_90d: float = 0.0  # Percentage merged
    avg_issue_close_time_days: float = 0.0
    avg_pr_merge_time_days: float = 0.0

    @property
    def github_owner_repo(self) -> tuple[str, str] | None:
        """Extract owner/repo from GitHub URL."""
        import re

        patterns = [
            r"github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
            r"github\.com:([^/]+)/([^/]+?)(?:\.git)?$",
        ]
        for pattern in patterns:
            if match := re.search(pattern, self.url):
                return match.groups()
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary for caching."""
        return {
            "url": self.url,
            "stars": self.stars,
            "forks": self.forks,
            "open_issues": self.open_issues,
            "open_pull_requests": self.open_pull_requests,
            "watchers": self.watchers,
            "contributors_count": self.contributors_count,
            "last_commit_date": (
                self.last_commit_date.isoformat() if self.last_commit_date else None
            ),
            "created_date": self.created_date.isoformat() if self.created_date else None,
            "is_archived": self.is_archived,
            "is_fork": self.is_fork,
            "license": self.license,
            "topics": self.topics,
            "default_branch": self.default_branch,
            "commit_frequency_30d": self.commit_frequency_30d,
            "issue_close_rate_90d": self.issue_close_rate_90d,
            "pr_merge_rate_90d": self.pr_merge_rate_90d,
            "avg_issue_close_time_days": self.avg_issue_close_time_days,
            "avg_pr_merge_time_days": self.avg_pr_merge_time_days,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RepositoryMetadata":
        """Create from dictionary (cache retrieval)."""
        last_commit = None
        if data.get("last_commit_date"):
            try:
                last_commit = datetime.fromisoformat(data["last_commit_date"])
            except (ValueError, TypeError):
                pass

        created = None
        if data.get("created_date"):
            try:
                created = datetime.fromisoformat(data["created_date"])
            except (ValueError, TypeError):
                pass

        return cls(
            url=data.get("url", ""),
            stars=data.get("stars", 0),
            forks=data.get("forks", 0),
            open_issues=data.get("open_issues", 0),
            open_pull_requests=data.get("open_pull_requests", 0),
            watchers=data.get("watchers", 0),
            contributors_count=data.get("contributors_count", 0),
            last_commit_date=last_commit,
            created_date=created,
            is_archived=data.get("is_archived", False),
            is_fork=data.get("is_fork", False),
            license=data.get("license"),
            topics=data.get("topics", []),
            default_branch=data.get("default_branch", "main"),
            commit_frequency_30d=data.get("commit_frequency_30d", 0.0),
            issue_close_rate_90d=data.get("issue_close_rate_90d", 0.0),
            pr_merge_rate_90d=data.get("pr_merge_rate_90d", 0.0),
            avg_issue_close_time_days=data.get("avg_issue_close_time_days", 0.0),
            avg_pr_merge_time_days=data.get("avg_pr_merge_time_days", 0.0),
        )


@dataclass
class HealthScore:
    """Composite health score for a package.

    NOTE: code_quality_score and license_score are computed and exposed here
    for transparency, but are intentionally NOT weighted into the overall grade
    in the current scoring rubric. See docs/SCORING_* and
    HealthCalculator._score_to_grade for details.
    """

    overall: float  # 0-100
    grade: HealthGrade

    # Component scores (0-100)
    security_score: float = 100.0
    maintenance_score: float = 50.0
    community_score: float = 50.0
    popularity_score: float = 50.0
    code_quality_score: float = 50.0
    license_score: float = 50.0  # New: license compatibility scoring

    # Detailed breakdown
    maintenance_status: MaintenanceStatus = MaintenanceStatus.STABLE
    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    risk_factors: list[str] = field(default_factory=list)
    positive_factors: list[str] = field(default_factory=list)

    # Confidence in the score (based on data availability)
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH

    # Metadata
    calculated_at: datetime | None = None
    data_freshness: dict[str, datetime] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.grade.value} ({self.overall:.1f})"

    @property
    def is_healthy(self) -> bool:
        """Return True if grade is A or B."""
        return self.grade in (HealthGrade.A, HealthGrade.B)

    @property
    def is_concerning(self) -> bool:
        """Return True if grade is D or F."""
        return self.grade in (HealthGrade.D, HealthGrade.F)

    @property
    def has_vulnerabilities(self) -> bool:
        """Return True if there are any known vulnerabilities."""
        return len(self.vulnerabilities) > 0

    @property
    def open_vulnerabilities(self) -> list[Vulnerability]:
        """Return list of vulnerabilities affecting the installed version."""
        return [v for v in self.vulnerabilities if v.is_open]

    @property
    def fixed_vulnerabilities(self) -> list[Vulnerability]:
        """Return list of vulnerabilities that have been fixed in installed version."""
        return [v for v in self.vulnerabilities if v.is_fixed_in_installed_version]

    @property
    def has_open_vulnerabilities(self) -> bool:
        """Return True if there are unpatched vulnerabilities."""
        return len(self.open_vulnerabilities) > 0

    @property
    def critical_vulnerabilities(self) -> list[Vulnerability]:
        """Return list of critical severity vulnerabilities (open only)."""
        return [v for v in self.vulnerabilities if v.severity == RiskLevel.CRITICAL and v.is_open]


@dataclass
class AlternativePackage:
    """A recommended alternative package."""

    package: PackageIdentifier
    health_score: float
    migration_effort: str  # "low", "medium", "high"
    rationale: str
    api_compatibility: float = 0.0  # 0-1, how similar the API is

    def __str__(self) -> str:
        name = self.package.name
        score = self.health_score
        effort = self.migration_effort
        return f"{name} (score: {score:.0f}, effort: {effort})"


@dataclass
class DependencyReport:
    """Complete health report for a dependency."""

    package: PackageIdentifier
    health: HealthScore
    pypi: PyPIMetadata | None = None
    repository: RepositoryMetadata | None = None
    alternatives: list[AlternativePackage] = field(default_factory=list)
    update_available: str | None = None  # Latest version if different
    is_direct: bool = True  # Direct vs transitive dependency
    dependents: list[str] = field(default_factory=list)  # What depends on this

    def __str__(self) -> str:
        return f"{self.package}: {self.health}"

    @property
    def needs_attention(self) -> bool:
        """Return True if this dependency needs attention."""
        return (
            self.health.is_concerning
            or self.health.has_open_vulnerabilities
            or self.health.maintenance_status.is_concerning
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "package": {
                "name": self.package.name,
                "version": self.package.version,
                "extras": list(self.package.extras),
            },
            "health": {
                "overall": self.health.overall,
                "grade": self.health.grade.value,
                "security_score": self.health.security_score,
                "maintenance_score": self.health.maintenance_score,
                "community_score": self.health.community_score,
                "popularity_score": self.health.popularity_score,
                "maintenance_status": self.health.maintenance_status.value,
                "vulnerabilities": [
                    {
                        "id": v.id,
                        "severity": v.severity.value,
                        "title": v.title,
                        "fixed_version": v.fixed_version,
                        "is_open": not v.is_fixed_in_installed_version,
                    }
                    for v in self.health.vulnerabilities
                ],
                "open_vulnerabilities_count": len(self.health.open_vulnerabilities),
                "risk_factors": self.health.risk_factors,
                "positive_factors": self.health.positive_factors,
            },
            "update_available": self.update_available,
            "is_direct": self.is_direct,
            "alternatives": [
                {
                    "name": alt.package.name,
                    "health_score": alt.health_score,
                    "migration_effort": alt.migration_effort,
                    "rationale": alt.rationale,
                }
                for alt in self.alternatives
            ],
        }
