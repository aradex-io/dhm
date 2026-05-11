"""
Report generator for orchestrating health report creation.

Provides the main ReportGenerator class that coordinates data collection
and formatting to produce complete dependency health reports.
"""

import asyncio
import logging
from pathlib import Path

import aiohttp

from dhm.cache.sqlite import CacheLayer
from dhm.collectors.github import GitHubClient
from dhm.collectors.pypi import PyPIClient
from dhm.collectors.vulnerability import VulnerabilityScanner
from dhm.core.calculator import HealthCalculator
from dhm.core.exceptions import NetworkError, PackageNotFoundError, RateLimitError
from dhm.core.models import (
    ConfidenceLevel,
    DependencyReport,
    PackageIdentifier,
)
from dhm.core.resolver import DependencyResolver
from dhm.reports.formatters import (
    Formatter,
    JSONFormatter,
    MarkdownFormatter,
    TableFormatter,
)

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate health reports for project dependencies.

    Orchestrates the entire process of resolving dependencies,
    fetching metadata, scanning for vulnerabilities, calculating
    health scores, and formatting output.
    """

    def __init__(
        self,
        github_token: str | None = None,
        cache_ttl: int = 3600,
        use_cache: bool = True,
        max_concurrency: int = 10,
    ):
        """Initialize the report generator.

        Args:
            github_token: Optional GitHub API token for higher rate limits.
            cache_ttl: Cache time-to-live in seconds.
            use_cache: Whether to use caching.
            max_concurrency: Maximum number of packages analyzed concurrently.
        """
        self.github_token = github_token
        self.cache_ttl = cache_ttl
        self.use_cache = use_cache
        self.max_concurrency = max_concurrency

        self.resolver = DependencyResolver()
        self.calculator = HealthCalculator()

        if use_cache:
            self.cache = CacheLayer(default_ttl=cache_ttl)
        else:
            self.cache = None

        # Formatters
        self.formatters: dict[str, Formatter] = {
            "json": JSONFormatter(),
            "markdown": MarkdownFormatter(),
            "table": TableFormatter(),
        }

    async def generate(
        self,
        project_path: Path,
        output_format: str = "table",
        output_path: Path | None = None,
    ) -> tuple[list[DependencyReport], str]:
        """Generate a health report for a project.

        Args:
            project_path: Path to project root or dependency file.
            output_format: Output format ('json', 'markdown', 'table').
            output_path: Optional path to write output file.

        Returns:
            Tuple of (list of DependencyReport, formatted output string).
        """
        # Resolve dependencies
        packages = self.resolver.resolve(project_path)

        if not packages:
            return [], "No dependencies found."

        # Generate reports for all packages
        reports = await self.generate_reports(packages)

        # Format output
        formatted = self.format_reports(reports, output_format)

        # Write to file if requested
        if output_path:
            output_path.write_text(formatted)

        return reports, formatted

    async def generate_reports(
        self,
        packages: list[PackageIdentifier],
    ) -> list[DependencyReport]:
        """Generate health reports for a list of packages.

        Args:
            packages: List of packages to analyze.

        Returns:
            List of DependencyReport objects.
        """
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        ) as session:
            pypi_client = PyPIClient(session, cache=self.cache)
            github_client = GitHubClient(session, token=self.github_token, cache=self.cache)
            vuln_scanner = VulnerabilityScanner(session, cache=self.cache)

            # Bound concurrency to avoid overwhelming upstream APIs
            sem = asyncio.Semaphore(self.max_concurrency)

            async def run_with_sem(pkg: PackageIdentifier):
                async with sem:
                    return await self._generate_single_report(
                        pkg,
                        pypi_client,
                        github_client,
                        vuln_scanner,
                    )

            tasks = [run_with_sem(pkg) for pkg in packages]

            reports = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out exceptions and return valid reports
            valid_reports = []
            for pkg, report in zip(packages, reports):
                if isinstance(report, DependencyReport):
                    valid_reports.append(report)
                elif isinstance(report, Exception):
                    logger.warning(
                        "Package %r failed during report generation: %s: %s",
                        pkg.name,
                        type(report).__name__,
                        report,
                    )

            return valid_reports

    async def _generate_single_report(
        self,
        package: PackageIdentifier,
        pypi_client: PyPIClient,
        github_client: GitHubClient,
        vuln_scanner: VulnerabilityScanner,
    ) -> DependencyReport:
        """Generate a health report for a single package.

        Args:
            package: Package to analyze.
            pypi_client: PyPI client instance.
            github_client: GitHub client instance.
            vuln_scanner: Vulnerability scanner instance.

        Returns:
            DependencyReport for the package.
        """
        # Check cache first
        cache_key = CacheLayer.make_key("report", package.name, package.version or "latest")
        if self.cache:
            cached = self.cache.get_value(cache_key)
            if cached:
                # Reconstruct report from cached data
                # For simplicity, we skip this in MVP and always fetch fresh data
                pass

        # Track which data sources failed so we can lower confidence accordingly
        failed_sources: list[str] = []

        # Fetch PyPI metadata — PackageNotFoundError propagates immediately (H-14)
        pypi_metadata = None
        try:
            pypi_metadata = await pypi_client.get_package_info(
                package.name,
                package.version,
            )
            # Also fetch download stats from pypistats.org
            if pypi_metadata:
                try:
                    downloads = await pypi_client.get_download_stats(package.name)
                    # Update the metadata object with real download count
                    pypi_metadata.downloads_last_month = downloads
                except (NetworkError, RateLimitError) as exc:
                    logger.warning(
                        "Package %r: download stats unavailable: %s: %s",
                        package.name,
                        type(exc).__name__,
                        exc,
                    )
                    failed_sources.append(f"Download stats unavailable: {exc}")

                # IMPORTANT: Update package version from PyPI if not specified
                # This enables accurate open vs fixed vulnerability detection
                if not package.version and pypi_metadata.version:
                    package = PackageIdentifier(
                        name=package.name,
                        version=pypi_metadata.version,
                        extras=package.extras,
                    )
        except PackageNotFoundError:
            # Re-raise so gather captures it and the caller can report it properly
            raise
        except (NetworkError, RateLimitError) as exc:
            logger.warning(
                "Package %r: PyPI metadata unavailable: %s: %s",
                package.name,
                type(exc).__name__,
                exc,
            )
            failed_sources.append(f"PyPI data unavailable: {exc}")

        # Fetch repository metadata if available
        repo_metadata = None
        if pypi_metadata and pypi_metadata.repository_url:
            repo_url = pypi_metadata.repository_url
            if "github.com" in repo_url:
                try:
                    owner, repo = github_client.extract_repo_from_url(repo_url)
                    repo_metadata = await github_client.get_repository(owner, repo)
                except (NetworkError, RateLimitError) as exc:
                    logger.warning(
                        "Package %r: GitHub data unavailable: %s: %s",
                        package.name,
                        type(exc).__name__,
                        exc,
                    )
                    failed_sources.append(f"GitHub data unavailable: {exc}")

        # Scan for vulnerabilities
        vulnerabilities = []
        try:
            vulnerabilities = await vuln_scanner.scan_package(package)
        except (NetworkError, RateLimitError) as exc:
            logger.warning(
                "Package %r: vulnerability scan unavailable: %s: %s",
                package.name,
                type(exc).__name__,
                exc,
            )
            failed_sources.append(f"Vulnerability data unavailable: {exc}")

        # Calculate health score
        health = self.calculator.calculate(
            pypi_metadata,
            repo_metadata,
            vulnerabilities,
        )

        # Attach risk factors and lower confidence for each failed data source (M-20)
        if failed_sources:
            health.risk_factors.extend(failed_sources)
            # Drop confidence one level per failure, floor at LOW
            if len(failed_sources) >= 2:
                health.confidence = ConfidenceLevel.LOW
            elif health.confidence == ConfidenceLevel.HIGH:
                health.confidence = ConfidenceLevel.MEDIUM

        # Check for available updates
        update_available = None
        if pypi_metadata and package.version:
            if package.version != pypi_metadata.version:
                update_available = pypi_metadata.version

        # Build the report
        report = DependencyReport(
            package=package,
            health=health,
            pypi=pypi_metadata,
            repository=repo_metadata,
            update_available=update_available,
            is_direct=True,
        )

        # Cache the result
        if self.cache:
            try:
                self.cache.set(cache_key, report.to_dict(), self.cache_ttl)
            except Exception:
                pass

        return report

    async def check_package(
        self,
        name: str,
        version: str | None = None,
    ) -> DependencyReport:
        """Check health of a single package.

        Args:
            name: Package name.
            version: Optional specific version.

        Returns:
            DependencyReport for the package.
        """
        package = PackageIdentifier(name=name, version=version)

        # Run generate_reports, but intercept PackageNotFoundError so it propagates
        # to the caller rather than being silently swallowed (H-14).
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        ) as session:
            pypi_client = PyPIClient(session, cache=self.cache)
            github_client = GitHubClient(session, token=self.github_token, cache=self.cache)
            vuln_scanner = VulnerabilityScanner(session, cache=self.cache)

            # _generate_single_report re-raises PackageNotFoundError directly,
            # so we let it escape here too.
            report = await self._generate_single_report(
                package,
                pypi_client,
                github_client,
                vuln_scanner,
            )

        return report

    def format_reports(
        self,
        reports: list[DependencyReport],
        format_name: str = "table",
    ) -> str:
        """Format reports using the specified formatter.

        Args:
            reports: List of DependencyReport objects.
            format_name: Name of formatter to use.

        Returns:
            Formatted string output.

        Raises:
            ValueError: If format_name is not recognized.
        """
        formatter = self.formatters.get(format_name)
        if not formatter:
            raise ValueError(
                f"Unknown format: {format_name}. "
                f"Available formats: {list(self.formatters.keys())}"
            )

        return formatter.format(reports)

    def add_formatter(self, name: str, formatter: Formatter) -> None:
        """Add a custom formatter.

        Args:
            name: Name for the formatter.
            formatter: Formatter instance.
        """
        self.formatters[name] = formatter
