"""
Main CLI entry point for DHM.

Provides commands for scanning projects, checking individual packages,
finding alternatives, and managing the cache.
"""

import asyncio
import sys
import traceback
from pathlib import Path

import click
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from dhm import __version__
from dhm.cli.output import (
    err_console,
    print_alternatives_table,
    print_detailed_report,
    print_error,
    print_info,
    print_success,
    print_table,
)
from dhm.core.models import RiskLevel

# Exit codes
EXIT_OK = 0        # No issues found / successful run
EXIT_THRESHOLD = 1  # --fail-on threshold was breached
EXIT_ERROR = 2     # Tool/runtime error (network, parse, unexpected exception)


def run_async(coro):
    """Run an async coroutine in a new event loop."""
    return asyncio.run(coro)


@click.group()
@click.version_option(version=__version__, prog_name="dhm")
@click.option(
    "--github-token",
    envvar="GITHUB_TOKEN",
    help="GitHub API token for higher rate limits.",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Print full tracebacks on errors.",
)
@click.pass_context
def cli(ctx: click.Context, github_token: str | None, debug: bool) -> None:
    """Dependency Health Monitor - Know your dependencies.

    DHM analyzes your project dependencies and provides health scores
    based on security, maintenance, community, and popularity metrics.

    \b
    Exit codes:
      0  Clean — no threshold violations, no errors.
      1  Threshold breached — --fail-on condition was met.
      2  Tool error — network failure, parse error, or unexpected exception.
    """
    ctx.ensure_object(dict)
    ctx.obj["github_token"] = github_token
    ctx.obj["debug"] = debug


@cli.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option(
    "--format", "-f",
    type=click.Choice(["table", "json", "markdown"]),
    default="table",
    help="Output format.",
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    help="Write output to file.",
)
@click.option(
    "--fail-on",
    type=click.Choice(["critical", "high", "medium", "low"]),
    help="Exit non-zero if issues at this severity or above.",
)
@click.option(
    "--no-cache",
    is_flag=True,
    help="Disable caching.",
)
@click.pass_context
def scan(
    ctx: click.Context,
    path: str,
    format: str,
    output: str | None,
    fail_on: str | None,
    no_cache: bool,
) -> None:
    """Scan project dependencies for health issues.

    Analyzes all dependencies found in the project at PATH (default: current
    directory) and displays a health report.

    \b
    Exit codes:
      0  No issues found (or none at the requested severity).
      1  One or more open vulnerabilities at or above --fail-on severity.
      2  Tool error (network, parse, or unexpected exception).

    \b
    Examples:
        dhm scan                         # Scan current directory
        dhm scan /path/to/project        # Scan specific project
        dhm scan -f json -o report.json  # Output as JSON
        dhm scan --fail-on high          # Exit 1 if high+ severity open issues
    """
    from dhm.reports.generator import ReportGenerator

    github_token = ctx.obj.get("github_token")
    debug = ctx.obj.get("debug", False)
    project_path = Path(path)

    generator = ReportGenerator(
        github_token=github_token,
        use_cache=not no_cache,
    )

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=err_console,
        ) as progress:
            task = progress.add_task("Scanning dependencies...", total=None)
            reports, formatted = run_async(
                generator.generate(
                    project_path,
                    output_format=format,
                    output_path=Path(output) if output else None,
                )
            )
            progress.update(task, description="Scan complete.")

        if not reports:
            print_info("No dependencies found in project.")
            return

        # Output results
        if format == "table":
            print_table(reports)
        elif not output:
            # Only echo structured output to stdout when not writing to a file
            click.echo(formatted)

        if output:
            print_success(f"Report written to {output}")

        # Check fail threshold
        if fail_on:
            exit_code = _check_threshold(reports, fail_on)
            if exit_code:
                print_error(f"Found issues at or above {fail_on} severity.")
                sys.exit(EXIT_THRESHOLD)

    except Exception as e:
        print_error(f"Scan failed: {e}")
        if debug:
            err_console.print(traceback.format_exc())
        sys.exit(EXIT_ERROR)


@cli.command()
@click.argument("package")
@click.option(
    "--version", "-v",
    help="Specific version to check.",
)
@click.pass_context
def check(ctx: click.Context, package: str, version: str | None) -> None:
    """Check health of a specific package.

    Fetches comprehensive health information for PACKAGE including
    security vulnerabilities, maintenance status, and community metrics.

    \b
    Examples:
        dhm check requests          # Check latest version
        dhm check requests -v 2.28.0  # Check specific version
    """
    from dhm.reports.generator import ReportGenerator

    github_token = ctx.obj.get("github_token")
    debug = ctx.obj.get("debug", False)

    generator = ReportGenerator(github_token=github_token)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=err_console,
        ) as progress:
            task = progress.add_task(f"Checking {package}...", total=None)
            report = run_async(generator.check_package(package, version))
            progress.update(task, description="Done.")

        print_detailed_report(report)

    except Exception as e:
        print_error(f"Check failed: {e}")
        if debug:
            err_console.print(traceback.format_exc())
        sys.exit(EXIT_ERROR)


@cli.command()
@click.argument("package")
@click.pass_context
def alternatives(ctx: click.Context, package: str) -> None:
    """Find healthier alternatives for a package.

    Searches for alternative packages that serve a similar purpose
    and may have better health scores.

    \b
    Examples:
        dhm alternatives requests   # Find alternatives to requests
    """
    from dhm.analyzers.alternatives import AlternativesRecommender
    from dhm.reports.generator import ReportGenerator

    github_token = ctx.obj.get("github_token")
    debug = ctx.obj.get("debug", False)

    generator = ReportGenerator(github_token=github_token)
    recommender = AlternativesRecommender()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=err_console,
        ) as progress:
            task = progress.add_task(f"Finding alternatives for {package}...", total=None)

            # First check the original package
            report = run_async(generator.check_package(package))
            progress.update(task, description=f"Finding alternatives for {package}...")

            # Find alternatives
            alts = run_async(
                recommender.find_alternatives_async(
                    report.package,
                    report.health,
                    generator,
                )
            )
            progress.update(task, description="Done.")

        if not alts:
            print_info(f"No better alternatives found for {package}.")
            score = report.health.overall
            grade = report.health.grade.value
            print_info(f"Current health score: {score:.0f} ({grade})")
            return

        print_alternatives_table(package, report.health, alts)

    except Exception as e:
        print_error(f"Search failed: {e}")
        if debug:
            err_console.print(traceback.format_exc())
        sys.exit(EXIT_ERROR)


@cli.command()
@click.option("--clear", is_flag=True, help="Clear all cached data.")
@click.option("--stats", is_flag=True, help="Show cache statistics.")
@click.option("--cleanup", is_flag=True, help="Remove expired entries.")
@click.option(
    "--invalidate", type=str, help="Invalidate entries matching pattern (e.g., 'github:%')"
)
@click.option(
    "--yes", "-y",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt (for scripted use).",
)
def cache(clear: bool, stats: bool, cleanup: bool, invalidate: str | None, yes: bool) -> None:
    """Manage the local cache.

    DHM caches API responses to improve performance and reduce
    rate limiting. Use this command to view or manage the cache.

    \b
    Cache TTLs:
      - GitHub data: 24 hours (repo metrics change slowly)
      - PyPI metadata: 1 hour (releases are occasional)
      - Download stats: 6 hours (updated daily on pypistats)
      - Vulnerabilities: 6 hours (security-critical, stay current)

    \b
    Examples:
        dhm cache --stats         # Show cache statistics
        dhm cache --clear         # Clear all cached data
        dhm cache --cleanup       # Remove only expired entries
        dhm cache --invalidate 'github:%'  # Clear only GitHub cache
    """
    from dhm.cache.sqlite import CacheLayer

    cache_layer = CacheLayer()

    if clear:
        if not yes:
            click.confirm(
                "Clear all cached data? This cannot be undone.",
                abort=True,
            )
        count = cache_layer.clear()
        print_success(f"Cache cleared. Removed {count} entries.")
    elif cleanup:
        count = cache_layer.cleanup()
        print_success(f"Cleanup complete. Removed {count} expired entries.")
    elif invalidate:
        count = cache_layer.invalidate(invalidate)
        print_success(f"Invalidated {count} entries matching '{invalidate}'.")
    elif stats:
        cache_stats = cache_layer.stats()
        click.echo("\nCache Statistics:")
        click.echo(f"  Database: {cache_stats['db_path']}")
        click.echo(f"  Size: {cache_stats['db_size_bytes'] / 1024:.1f} KB")
        click.echo(f"  Total entries: {cache_stats['total_entries']}")
        click.echo(f"  Valid entries: {cache_stats['valid_entries']}")
        click.echo(f"  Expired entries: {cache_stats['expired_entries']}")

        if cache_stats['entries_by_prefix']:
            click.echo("\n  Entries by type:")
            for prefix, count in cache_stats['entries_by_prefix'].items():
                ttl_info = {
                    "github": "24h TTL",
                    "pypi": "1h TTL",
                    "pypistats": "6h TTL",
                    "osv": "6h TTL",
                }.get(prefix, "")
                click.echo(f"    {prefix}: {count} {f'({ttl_info})' if ttl_info else ''}")

        click.echo("\n  To refresh all data, use: dhm cache --clear")
    else:
        # Show help if no option specified
        ctx = click.get_current_context()
        click.echo(ctx.get_help())


def _check_threshold(reports: list, fail_on: str) -> int:
    """Check if any reports have open vulnerabilities exceeding the threshold.

    Only open vulnerabilities (not already-patched historical ones) are
    considered, so projects pinned to a fixed version are not penalised.

    Args:
        reports: List of DependencyReport objects.
        fail_on: Minimum severity to fail on.

    Returns:
        EXIT_THRESHOLD if any open vulnerability meets the threshold, else EXIT_OK.
    """
    threshold_map = {
        "critical": RiskLevel.CRITICAL,
        "high": RiskLevel.HIGH,
        "medium": RiskLevel.MEDIUM,
        "low": RiskLevel.LOW,
    }

    threshold = threshold_map.get(fail_on)
    if not threshold:
        return EXIT_OK

    threshold_order = threshold.sort_order

    for report in reports:
        for vuln in report.health.open_vulnerabilities:
            if vuln.severity.sort_order <= threshold_order:
                return EXIT_THRESHOLD

    return EXIT_OK


if __name__ == "__main__":
    cli()
