"""
Health Calculator for computing composite health scores.

This module implements the weighted scoring algorithm that combines
security, maintenance, community, and popularity metrics into an
overall health score and letter grade.

Uses logarithmic normalization for smooth scoring curves (industry best practice).
"""

import math
from datetime import datetime, timezone

from dhm.core.models import (
    ConfidenceLevel,
    HealthGrade,
    HealthScore,
    MaintenanceStatus,
    PyPIMetadata,
    RepositoryMetadata,
    RiskLevel,
    Vulnerability,
)


def _log_normalize(value: float, min_val: float, max_val: float, max_score: float) -> float:
    """Normalize a value using logarithmic scaling.

    Provides smooth scoring curves instead of abrupt step functions.
    A package with 999,999 downloads scores almost the same as one with 1,000,001.

    Args:
        value: The raw value to normalize.
        min_val: Minimum expected value (scores 0).
        max_val: Maximum expected value (scores max_score).
        max_score: Maximum score to return.

    Returns:
        Normalized score between 0 and max_score.
    """
    if value <= min_val:
        return 0.0
    if value >= max_val:
        return max_score

    # Use log scale for smooth progression
    log_min = math.log10(max(min_val, 1))
    log_max = math.log10(max_val)
    log_val = math.log10(max(value, 1))

    # Linear interpolation in log space
    ratio = (log_val - log_min) / (log_max - log_min)
    return ratio * max_score


def _linear_normalize(value: float, min_val: float, max_val: float, max_score: float) -> float:
    """Normalize a value using linear scaling.

    Args:
        value: The raw value to normalize.
        min_val: Minimum expected value (scores 0).
        max_val: Maximum expected value (scores max_score).
        max_score: Maximum score to return.

    Returns:
        Normalized score between 0 and max_score.
    """
    if value <= min_val:
        return 0.0
    if value >= max_val:
        return max_score

    ratio = (value - min_val) / (max_val - min_val)
    return ratio * max_score


class HealthCalculator:
    """Calculate health scores from collected data.

    The calculator uses a weighted algorithm to combine multiple signals
    into a comprehensive health assessment. Weights can be customized
    to emphasize different aspects of package health.

    Uses logarithmic normalization for metrics that span many orders of
    magnitude (downloads, stars) for smoother scoring curves.
    """

    # Default scoring weights
    WEIGHTS = {
        "security": 0.35,
        "maintenance": 0.30,
        "community": 0.20,
        "popularity": 0.15,
    }

    # Vulnerability severity deductions
    VULN_DEDUCTIONS = {
        RiskLevel.CRITICAL: 40,
        RiskLevel.HIGH: 25,
        RiskLevel.MEDIUM: 10,
        RiskLevel.LOW: 5,
        RiskLevel.INFO: 1,
    }

    # License categories for scoring
    LICENSE_PERMISSIVE = {
        "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Unlicense", "0BSD"
    }
    LICENSE_COPYLEFT = {"GPL-2.0", "GPL-3.0", "LGPL-2.1", "LGPL-3.0", "AGPL-3.0", "MPL-2.0"}
    LICENSE_WEAK_COPYLEFT = {"LGPL-2.1", "LGPL-3.0", "MPL-2.0"}  # Less restrictive copyleft

    def __init__(
        self,
        weights: dict[str, float] | None = None,
    ):
        """Initialize the calculator with optional custom weights.

        Args:
            weights: Optional dict of weight overrides. Keys should be
                     'security', 'maintenance', 'community', 'popularity'.
        """
        self.weights = {**self.WEIGHTS}
        if weights:
            self.weights.update(weights)

        if any(v < 0 for v in self.weights.values()):
            raise ValueError("HealthCalculator weights must be non-negative")

        # Normalize weights to sum to 1.0
        total = sum(self.weights.values())
        if total <= 0:
            raise ValueError("HealthCalculator weights must sum to a positive value")
        self.weights = {k: v / total for k, v in self.weights.items()}

    def calculate(
        self,
        pypi: PyPIMetadata | None,
        repo: RepositoryMetadata | None,
        vulnerabilities: list[Vulnerability],
    ) -> HealthScore:
        """Calculate comprehensive health score.

        Args:
            pypi: Package metadata from PyPI (may be None).
            repo: Repository metadata from GitHub/GitLab (may be None).
            vulnerabilities: List of known vulnerabilities.

        Returns:
            HealthScore with overall score, grade, component scores, and confidence.
        """
        security = self._calculate_security_score(vulnerabilities)
        maintenance = self._calculate_maintenance_score(pypi, repo)
        community = self._calculate_community_score(repo)
        popularity = self._calculate_popularity_score(pypi, repo)
        code_quality = self._calculate_quality_score(repo)
        license_score = self._calculate_license_score(pypi, repo)

        # NOTE: code_quality_score and license_score are computed and exposed on
        # HealthScore for transparency, but are intentionally NOT weighted into
        # the overall grade in the current scoring rubric. See docs/SCORING_*.

        # Calculate weighted overall score
        overall = (
            security * self.weights["security"]
            + maintenance * self.weights["maintenance"]
            + community * self.weights["community"]
            + popularity * self.weights["popularity"]
        )

        # Determine confidence level based on data availability
        confidence = self._determine_confidence(pypi, repo)

        # Build data freshness dict
        data_freshness = {}
        if pypi:
            data_freshness["pypi"] = datetime.now(timezone.utc)
        if repo:
            data_freshness["repository"] = datetime.now(timezone.utc)

        return HealthScore(
            overall=overall,
            grade=self._score_to_grade(overall),
            security_score=security,
            maintenance_score=maintenance,
            community_score=community,
            popularity_score=popularity,
            code_quality_score=code_quality,
            license_score=license_score,
            maintenance_status=self._determine_maintenance_status(pypi, repo),
            vulnerabilities=vulnerabilities,
            risk_factors=self._identify_risks(pypi, repo, vulnerabilities),
            positive_factors=self._identify_positives(pypi, repo),
            confidence=confidence,
            calculated_at=datetime.now(timezone.utc),
            data_freshness=data_freshness,
        )

    def _calculate_security_score(
        self,
        vulnerabilities: list[Vulnerability],
    ) -> float:
        """Calculate score based on vulnerability count and severity.

        Perfect score (100) if no vulnerabilities. Scoring differentiates
        between OPEN vulnerabilities (heavy penalty) and FIXED ones (minor
        penalty - historical security issues that were resolved).

        A package with many fixed vulnerabilities may actually indicate
        responsive maintainers who address issues quickly.
        """
        if not vulnerabilities:
            return 100.0

        # Separate open vs fixed vulnerabilities
        open_vulns = [v for v in vulnerabilities if v.is_open]
        fixed_vulns = [v for v in vulnerabilities if v.is_fixed_in_installed_version]

        # Heavy penalty for OPEN vulnerabilities (affects current version)
        open_deduction = sum(
            self.VULN_DEDUCTIONS.get(v.severity, 5) for v in open_vulns
        )

        # Minor penalty for historical vulnerabilities (shows past issues existed)
        # But significantly reduced since they're fixed - only 10% of normal weight
        historical_deduction = sum(
            self.VULN_DEDUCTIONS.get(v.severity, 5) * 0.1 for v in fixed_vulns
        )

        total_deduction = open_deduction + historical_deduction

        return max(0.0, 100.0 - total_deduction)

    def _calculate_maintenance_score(
        self,
        pypi: PyPIMetadata | None,
        repo: RepositoryMetadata | None,
    ) -> float:
        """Calculate score based on maintenance activity.

        Considers release recency, release consistency, commit frequency,
        and issue responsiveness.
        """
        score = 50.0  # Base score

        now = datetime.now(timezone.utc)

        if pypi and pypi.release_date:
            # Make release_date timezone-aware if it isn't
            release_date = pypi.release_date
            if release_date.tzinfo is None:
                release_date = release_date.replace(tzinfo=timezone.utc)

            days_since_release = (now - release_date).days

            if days_since_release < 30:
                score += 20
            elif days_since_release < 90:
                score += 15
            elif days_since_release < 180:
                score += 10
            elif days_since_release < 365:
                score += 5
            elif days_since_release > 730:  # > 2 years
                score -= 10

            # Release consistency
            if pypi.total_releases > 10:
                score += 10
            elif pypi.total_releases > 5:
                score += 5

            # Check for deprecation
            if pypi.is_deprecated:
                score -= 20

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

            # Archived status is very bad
            if repo.is_archived:
                score -= 30

        return min(100.0, max(0.0, score))

    def _calculate_community_score(
        self,
        repo: RepositoryMetadata | None,
    ) -> float:
        """Calculate score based on community engagement.

        Uses logarithmic normalization for smooth scoring curves.
        A package with 999 stars scores almost the same as one with 1001.

        Scoring Philosophy:
        - Base score of 50 (neutral) when repo data exists
        - Logarithmic bonuses for positive signals
        - Without repo data, return neutral 50 (don't penalize missing data)
        """
        if not repo:
            return 50.0  # Neutral without data

        # Start at neutral base
        score = 50.0

        # Contributors: log scale from 1 to 200, max +20 points
        # 1 contributor = 0, 10 contributors = ~10, 100 contributors = ~17, 200+ = 20
        score += _log_normalize(repo.contributors_count, 1, 200, 20)

        # Single maintainer penalty
        if repo.contributors_count <= 1:
            score -= 10

        # Stars: log scale from 10 to 50000, max +20 points
        # 10 stars = 0, 100 stars = ~5, 1000 stars = ~11, 10000 stars = ~16
        score += _log_normalize(repo.stars, 10, 50000, 20)

        # Forks: log scale from 1 to 500, max +10 points
        score += _log_normalize(repo.forks, 1, 500, 10)

        # PR merge rate: linear scale (already 0-1), max +10 points
        score += _linear_normalize(repo.pr_merge_rate_90d, 0, 1, 10)

        # Penalty for archived repos (community is gone)
        if repo.is_archived:
            score -= 25

        return min(100.0, max(0.0, score))

    def _calculate_popularity_score(
        self,
        pypi: PyPIMetadata | None,
        repo: RepositoryMetadata | None,
    ) -> float:
        """Calculate score based on package popularity.

        Uses logarithmic normalization for smooth scoring across
        many orders of magnitude (100 to 100M downloads).

        Scoring Philosophy:
        - Base score of 50 (neutral) - don't penalize new/niche packages
        - Downloads are the primary signal (from pypistats.org)
        - Watchers provide secondary social proof
        - Stars NOT included (counted in Community)
        """
        # Start at neutral base
        score = 50.0

        if pypi:
            downloads = pypi.downloads_last_month

            if downloads == 0:
                # No download data - slight penalty
                score -= 5
            else:
                # Downloads: log scale from 100 to 50M, max +40 points
                # 100 downloads = 0, 10k = ~14, 1M = ~28, 10M = ~35
                score += _log_normalize(downloads, 100, 50_000_000, 40)

        if repo:
            # Watchers: log scale from 10 to 5000, max +10 points
            score += _log_normalize(repo.watchers, 10, 5000, 10)

        return min(100.0, max(0.0, score))

    def _calculate_quality_score(
        self,
        repo: RepositoryMetadata | None,
    ) -> float:
        """Calculate code quality score.

        NOTE: This score is calculated for informational/display purposes
        but is NOT included in the weighted overall score. The current
        signals largely duplicate Community score metrics.

        Future versions will incorporate stronger quality signals:
        - CI/CD status (GitHub Actions, Travis, etc.)
        - Test coverage percentage
        - Linting/type checking status
        - Documentation coverage

        Once these signals are available, this score will be added to
        the weighted average with appropriate weight rebalancing.
        """
        if not repo:
            return 50.0

        score = 50.0

        # Having multiple contributors suggests code review
        if repo.contributors_count > 5:
            score += 15
        elif repo.contributors_count > 2:
            score += 10

        # Good PR merge practices
        if repo.pr_merge_rate_90d > 0.6:
            score += 15
        elif repo.pr_merge_rate_90d > 0.3:
            score += 10

        # Quick issue resolution
        if repo.avg_issue_close_time_days < 7:
            score += 10
        elif repo.avg_issue_close_time_days < 30:
            score += 5

        # Not a fork (original work)
        if not repo.is_fork:
            score += 10

        return min(100.0, max(0.0, score))

    def _calculate_license_score(
        self,
        pypi: PyPIMetadata | None,
        repo: RepositoryMetadata | None,
    ) -> float:
        """Calculate license compatibility score.

        Evaluates the package license for legal risk and compatibility.

        Scoring Philosophy:
        - Permissive licenses (MIT, Apache, BSD): Full score
        - Weak copyleft (LGPL, MPL): Minor penalty (some restrictions)
        - Strong copyleft (GPL, AGPL): Larger penalty (viral licensing)
        - No license / Unknown: Significant penalty (legal uncertainty)
        """
        # Get license from repo (more reliable) or pypi
        license_id = None
        if repo and repo.license:
            license_id = repo.license
        elif pypi and pypi.license:
            # PyPI license field can be verbose, try to normalize
            license_id = pypi.license

        if not license_id:
            # No license information - risky for commercial use
            return 30.0

        # Tokenize on whitespace/punctuation (keeping hyphens/dots/plus so SPDX
        # ids like "Apache-2.0" stay intact) and match whole tokens against the
        # SPDX id sets. Whole-token matching avoids false positives from
        # substring containment (e.g. "ISC" inside "DISCLAIMER" in a verbose
        # license blob).
        import re

        tokens = {t.upper() for t in re.split(r"[\s,;:/()\[\]]+", license_id) if t}

        permissive = {lic.upper() for lic in self.LICENSE_PERMISSIVE} | {"BSD"}
        weak_copyleft = {lic.upper() for lic in self.LICENSE_WEAK_COPYLEFT}
        copyleft = {lic.upper() for lic in self.LICENSE_COPYLEFT}

        if tokens & permissive:
            return 100.0
        # Weak copyleft checked before strong so LGPL/MPL do not fall through to GPL.
        if tokens & weak_copyleft:
            return 75.0
        if tokens & copyleft:
            return 60.0

        # Unknown license - moderate uncertainty
        return 50.0

    def _determine_confidence(
        self,
        pypi: PyPIMetadata | None,
        repo: RepositoryMetadata | None,
    ) -> ConfidenceLevel:
        """Determine confidence level based on data availability.

        High confidence requires:
        - PyPI metadata available
        - GitHub/repo metadata available
        - Download stats available (non-zero)

        Medium confidence:
        - Missing GitHub data (rate limited) OR
        - Missing download stats

        Low confidence:
        - Missing PyPI data OR
        - Multiple data sources missing
        """
        has_pypi = pypi is not None
        has_repo = repo is not None
        has_downloads = pypi and pypi.downloads_last_month > 0

        if has_pypi and has_repo and has_downloads:
            return ConfidenceLevel.HIGH
        elif has_pypi and (has_repo or has_downloads):
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    def _determine_maintenance_status(
        self,
        pypi: PyPIMetadata | None,
        repo: RepositoryMetadata | None,
    ) -> MaintenanceStatus:
        """Classify maintenance status based on activity signals."""

        # Check for explicit archived status
        if repo and repo.is_archived:
            return MaintenanceStatus.ARCHIVED

        # Check for deprecation markers
        if pypi and pypi.is_deprecated:
            return MaintenanceStatus.DEPRECATED

        now = datetime.now(timezone.utc)
        days_since_release = float("inf")
        days_since_commit = float("inf")

        if pypi and pypi.release_date:
            release_date = pypi.release_date
            if release_date.tzinfo is None:
                release_date = release_date.replace(tzinfo=timezone.utc)
            days_since_release = (now - release_date).days

        if repo and repo.last_commit_date:
            commit_date = repo.last_commit_date
            if commit_date.tzinfo is None:
                commit_date = commit_date.replace(tzinfo=timezone.utc)
            days_since_commit = (now - commit_date).days

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
        """Convert numeric score to letter grade.

        Thresholds calibrated for the base-50 scoring system:
        - With all neutral data (50/50/50/50), overall = 50 → F (needs investigation)
        - With good signals, packages should reach B/A territory
        - Security issues can easily push packages down to D/F

        Grade distribution targets (approximate):
        - A: Top ~20% - Excellent, actively maintained, secure
        - B: Next ~25% - Good health, minor concerns
        - C: Middle ~25% - Acceptable, some caution advised
        - D: Next ~15% - Concerning, investigate before using
        - F: Bottom ~15% - Critical issues, avoid or replace
        """
        if score >= 85:
            return HealthGrade.A
        elif score >= 75:
            return HealthGrade.B
        elif score >= 65:
            return HealthGrade.C
        elif score >= 55:
            return HealthGrade.D
        else:
            return HealthGrade.F

    def _identify_risks(
        self,
        pypi: PyPIMetadata | None,
        repo: RepositoryMetadata | None,
        vulnerabilities: list[Vulnerability],
    ) -> list[str]:
        """Identify risk factors for a package."""
        risks = []

        # Security risks - only count OPEN vulnerabilities as risks
        open_vulns = [v for v in vulnerabilities if v.is_open]
        critical_vulns = [v for v in open_vulns if v.severity == RiskLevel.CRITICAL]
        high_vulns = [v for v in open_vulns if v.severity == RiskLevel.HIGH]

        if critical_vulns:
            risks.append(f"{len(critical_vulns)} OPEN critical vulnerability(ies)")
        if high_vulns:
            risks.append(f"{len(high_vulns)} OPEN high severity vulnerability(ies)")

        # Maintenance risks
        if repo and repo.is_archived:
            risks.append("Repository is archived")

        if pypi and pypi.is_deprecated:
            risks.append("Package is deprecated")

        now = datetime.now(timezone.utc)
        if pypi and pypi.release_date:
            release_date = pypi.release_date
            if release_date.tzinfo is None:
                release_date = release_date.replace(tzinfo=timezone.utc)
            days_since = (now - release_date).days
            if days_since > 730:
                risks.append(f"No release in {days_since // 365} years")
            elif days_since > 365:
                risks.append("No release in over a year")

        # Community risks
        if repo:
            if repo.contributors_count == 1:
                risks.append("Single maintainer (bus factor risk)")
            if repo.open_issues > 100 and repo.issue_close_rate_90d < 0.1:
                risks.append("Many open issues with low resolution rate")

        # Yanked releases indicate problems
        if pypi and pypi.yanked_releases > 0:
            risks.append(f"{pypi.yanked_releases} yanked release(s)")

        return risks

    def _identify_positives(
        self,
        pypi: PyPIMetadata | None,
        repo: RepositoryMetadata | None,
    ) -> list[str]:
        """Identify positive factors for a package."""
        positives = []

        if pypi:
            # Popularity
            if pypi.downloads_last_month > 1_000_000:
                positives.append("Highly popular (1M+ monthly downloads)")
            elif pypi.downloads_last_month > 100_000:
                positives.append("Popular package (100K+ monthly downloads)")

            # Maturity
            if pypi.total_releases > 20:
                positives.append("Mature project with many releases")

            # Recent activity
            now = datetime.now(timezone.utc)
            if pypi.release_date:
                release_date = pypi.release_date
                if release_date.tzinfo is None:
                    release_date = release_date.replace(tzinfo=timezone.utc)
                if (now - release_date).days < 30:
                    positives.append("Recently updated")

        if repo:
            # Community
            if repo.contributors_count > 50:
                positives.append("Large contributor community")
            elif repo.contributors_count > 10:
                positives.append("Active contributor community")

            if repo.stars > 5000:
                positives.append("Highly starred repository")
            elif repo.stars > 1000:
                positives.append("Well-starred repository")

            # Responsiveness
            if repo.issue_close_rate_90d > 0.8:
                positives.append("Excellent issue resolution rate")
            if repo.pr_merge_rate_90d > 0.8:
                positives.append("Excellent PR merge rate")

            # Quick response times
            if repo.avg_issue_close_time_days < 7:
                positives.append("Fast issue resolution")

        return positives
