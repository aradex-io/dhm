"""
High-level programmatic API for DHM.

This module provides simple, async-friendly functions for common operations.
For more control, use the underlying classes directly.

Example:
    import asyncio
    from dhm import check, scan

    async def main():
        # Check a single package
        report = await check("requests")
        print(f"{report.package.name}: {report.health.grade}")

        # Scan a project
        reports = await scan("/path/to/project")
        for r in reports:
            if r.health.has_open_vulnerabilities:
                print(f"WARNING: {r.package.name} has vulnerabilities")

    asyncio.run(main())
"""

from pathlib import Path

from dhm.core.models import DependencyReport, PackageIdentifier
from dhm.core.validation import validate_package_name
from dhm.reports.generator import ReportGenerator


async def check(
    package: str,
    version: str | None = None,
    *,
    github_token: str | None = None,
    use_cache: bool = True,
) -> DependencyReport:
    """Check the health of a single package.

    Args:
        package: Package name (e.g., "requests", "django").
        version: Optional specific version to check. If not provided,
            checks the latest version from PyPI.
        github_token: Optional GitHub API token for higher rate limits.
        use_cache: Whether to use cached data (default: True).

    Returns:
        DependencyReport containing health score, vulnerabilities,
        and metadata.

    Example:
        >>> import asyncio
        >>> from dhm import check
        >>> report = asyncio.run(check("flask"))
        >>> print(f"Grade: {report.health.grade}")
        Grade: B
        >>> print(f"Open vulns: {len(report.health.open_vulnerabilities)}")
        Open vulns: 0
    """
    validate_package_name(package)
    generator = ReportGenerator(
        github_token=github_token,
        use_cache=use_cache,
    )
    return await generator.check_package(package, version)


async def scan(
    path: str | None = None,
    *,
    github_token: str | None = None,
    use_cache: bool = True,
) -> list[DependencyReport]:
    """Scan a project's dependencies for health issues.

    Args:
        path: Path to project directory. Defaults to current directory.
            Supports pyproject.toml (PEP 621 and Poetry) and requirements*.txt.
        github_token: Optional GitHub API token for higher rate limits.
        use_cache: Whether to use cached data (default: True).

    Returns:
        List of DependencyReport objects, one per dependency found.

    Example:
        >>> import asyncio
        >>> from dhm import scan
        >>> reports = asyncio.run(scan("."))
        >>> unhealthy = [r for r in reports if r.health.is_concerning]
        >>> print(f"Found {len(unhealthy)} concerning dependencies")
    """
    generator = ReportGenerator(
        github_token=github_token,
        use_cache=use_cache,
    )

    project_path = Path(path) if path else Path.cwd()
    reports, _ = await generator.generate(project_path)
    return reports


async def check_packages(
    packages: list[str],
    *,
    github_token: str | None = None,
    use_cache: bool = True,
) -> list[DependencyReport]:
    """Check health of multiple packages.

    Args:
        packages: List of package names (optionally with versions like "requests==2.31.0").
        github_token: Optional GitHub API token for higher rate limits.
        use_cache: Whether to use cached data (default: True).

    Returns:
        List of DependencyReport objects.

    Example:
        >>> import asyncio
        >>> from dhm import check_packages
        >>> reports = asyncio.run(check_packages(["requests", "flask", "django"]))
        >>> for r in sorted(reports, key=lambda x: x.health.overall):
        ...     print(f"{r.package.name}: {r.health.grade}")
    """
    generator = ReportGenerator(
        github_token=github_token,
        use_cache=use_cache,
    )

    # Parse package specifiers (validate each name before use)
    identifiers = []
    for pkg in packages:
        if "==" in pkg:
            name, version = pkg.split("==", 1)
            validate_package_name(name.strip())
            identifiers.append(PackageIdentifier(name=name.strip(), version=version.strip()))
        else:
            validate_package_name(pkg.strip())
            identifiers.append(PackageIdentifier(name=pkg.strip()))

    return await generator.generate_reports(identifiers)


def check_sync(
    package: str,
    version: str | None = None,
    *,
    github_token: str | None = None,
    use_cache: bool = True,
) -> DependencyReport:
    """Synchronous wrapper for check().

    For use in non-async contexts. Creates a new event loop via asyncio.run().

    Raises:
        RuntimeError: If called from inside a running event loop; use the
            async variant (check()) instead.

    Example:
        >>> from dhm import check_sync
        >>> report = check_sync("requests")
        >>> print(report.health.grade)
    """
    import asyncio
    return asyncio.run(
        check(package, version, github_token=github_token, use_cache=use_cache)
    )


def scan_sync(
    path: str | None = None,
    *,
    github_token: str | None = None,
    use_cache: bool = True,
) -> list[DependencyReport]:
    """Synchronous wrapper for scan().

    For use in non-async contexts. Creates a new event loop via asyncio.run().

    Raises:
        RuntimeError: If called from inside a running event loop; use the
            async variant (scan()) instead.

    Example:
        >>> from dhm import scan_sync
        >>> reports = scan_sync(".")
        >>> print(f"Scanned {len(reports)} packages")
    """
    import asyncio
    return asyncio.run(
        scan(path, github_token=github_token, use_cache=use_cache)
    )
