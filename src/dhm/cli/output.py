"""
Rich terminal output helpers for CLI.

Provides functions for printing tables, reports, and formatted
output using the Rich library.
"""


from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from dhm.core.models import (
    AlternativePackage,
    DependencyReport,
    HealthGrade,
    HealthScore,
    MaintenanceStatus,
)

# Console instance for structured/report output (stdout)
console = Console()

# Console instance for status/diagnostic messages (stderr)
err_console = Console(stderr=True)


def get_grade_style(grade: HealthGrade) -> str:
    """Get Rich style string for a health grade."""
    styles = {
        HealthGrade.A: "bold green",
        HealthGrade.B: "green",
        HealthGrade.C: "yellow",
        HealthGrade.D: "red",
        HealthGrade.F: "bold red",
    }
    return styles.get(grade, "white")


def get_status_style(status: MaintenanceStatus) -> str:
    """Get Rich style string for a maintenance status."""
    if status.is_concerning:
        return "red"
    elif status == MaintenanceStatus.ACTIVE:
        return "green"
    elif status == MaintenanceStatus.STABLE:
        return "cyan"
    else:
        return "yellow"


def print_table(reports: list[DependencyReport]) -> None:
    """Print a summary table of dependency health reports.

    Args:
        reports: List of DependencyReport objects.
    """
    table = Table(
        title="Dependency Health Report",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )

    table.add_column("Package", style="cyan", no_wrap=True)
    table.add_column("Version", style="dim")
    table.add_column("Grade", justify="center")
    table.add_column("Security", justify="right")
    table.add_column("Maint.", justify="right")
    table.add_column("Status")
    table.add_column("Issues")

    # Sort by overall score (lowest first to highlight problems)
    sorted_reports = sorted(reports, key=lambda r: r.health.overall)

    for report in sorted_reports:
        pkg = report.package
        health = report.health

        # Grade with color
        grade_style = get_grade_style(health.grade)
        grade_text = Text(health.grade.value, style=grade_style)

        # Status with color
        status_style = get_status_style(health.maintenance_status)
        status_text = Text(health.maintenance_status.value, style=status_style)

        # Build issues string
        issues = []
        if health.vulnerabilities:
            open_vulns = health.open_vulnerabilities
            fixed_vulns = health.fixed_vulnerabilities

            if open_vulns:
                open_critical = sum(1 for v in open_vulns if v.severity.value == "critical")
                if open_critical:
                    issues.append(Text(f"{open_critical} CRIT OPEN", style="bold red"))
                else:
                    issues.append(Text(f"{len(open_vulns)} open", style="red"))

            if fixed_vulns and not open_vulns:
                # Only show fixed count if no open vulns (good news)
                issues.append(Text(f"{len(fixed_vulns)} fixed", style="green"))

        if health.maintenance_status.is_concerning:
            if health.maintenance_status == MaintenanceStatus.ARCHIVED:
                issues.append(Text("archived", style="red"))
            elif health.maintenance_status == MaintenanceStatus.DEPRECATED:
                issues.append(Text("deprecated", style="red"))
            elif health.maintenance_status == MaintenanceStatus.ABANDONED:
                issues.append(Text("abandoned", style="yellow"))

        if report.update_available:
            issues.append(Text(f"update: {report.update_available}", style="cyan"))

        # Combine issues
        if issues:
            issues_text = Text()
            for i, issue in enumerate(issues):
                if i > 0:
                    issues_text.append(", ")
                issues_text.append_text(issue)
        else:
            issues_text = Text("OK", style="green")

        table.add_row(
            pkg.name,
            pkg.version or "-",
            grade_text,
            f"{health.security_score:.0f}",
            f"{health.maintenance_score:.0f}",
            status_text,
            issues_text,
        )

    console.print()
    console.print(table)

    # Print summary
    total = len(reports)
    healthy = sum(1 for r in reports if r.health.is_healthy)
    concerning = sum(1 for r in reports if r.health.is_concerning)
    with_vulns = sum(1 for r in reports if r.health.has_vulnerabilities)

    # Count packages with OPEN vulnerabilities
    with_open_vulns = sum(1 for r in reports if r.health.has_open_vulnerabilities)

    console.print()
    console.print(f"[bold]Summary:[/] {total} packages")
    console.print(f"  [green]Healthy (A/B):[/] {healthy}")
    console.print(f"  [red]Concerning (D/F):[/] {concerning}")
    console.print(f"  [red]With OPEN vulnerabilities:[/] {with_open_vulns}")
    if with_vulns > with_open_vulns:
        fixed_count = with_vulns - with_open_vulns
        console.print(f"  [dim]With fixed (historical) vulnerabilities:[/] {fixed_count}")


def print_detailed_report(report: DependencyReport) -> None:
    """Print a detailed health report for a single package.

    Args:
        report: DependencyReport to display.
    """
    pkg = report.package
    health = report.health

    # Title
    grade_style = get_grade_style(health.grade)
    title = f"[bold]{pkg.name}[/]"
    if pkg.version:
        title += f" [dim]v{pkg.version}[/]"

    console.print()
    console.print(Panel(title, subtitle=f"Grade: [{grade_style}]{health.grade.value}[/]"))

    # Health scores with confidence indicator
    confidence_style = {
        "high": "green",
        "medium": "yellow",
        "low": "red",
    }.get(health.confidence.value, "white")

    console.print("\n[bold cyan]Health Scores[/]")
    conf = health.confidence.value
    console.print(
        f"  Overall: [{grade_style}]{health.overall:.1f}[/] / 100 "
        f"[{confidence_style}]({conf} confidence)[/]"
    )
    console.print(f"  Security: {health.security_score:.0f}")
    console.print(f"  Maintenance: {health.maintenance_score:.0f}")
    console.print(f"  Community: {health.community_score:.0f}")
    console.print(f"  Popularity: {health.popularity_score:.0f}")
    console.print(f"  License: {health.license_score:.0f}")
    console.print(
        f"  Code Quality: {health.code_quality_score:.0f}/100"
        " [dim](informational — not weighted into grade)[/]"
    )

    # Maintenance status
    status_style = get_status_style(health.maintenance_status)
    status_val = health.maintenance_status.value
    console.print(f"\n[bold cyan]Maintenance Status:[/] [{status_style}]{status_val}[/]")

    # Vulnerabilities
    if health.vulnerabilities:
        open_vulns = health.open_vulnerabilities
        fixed_vulns = health.fixed_vulnerabilities

        if open_vulns:
            count = len(open_vulns)
            console.print(f"\n[bold red]OPEN Vulnerabilities ({count}) - Action Required[/]")
            for vuln in open_vulns:
                severity_color = {
                    "critical": "bold red",
                    "high": "red",
                    "medium": "yellow",
                    "low": "cyan",
                }.get(vuln.severity.value, "white")

                console.print(f"  [{severity_color}]{vuln.id}[/] - {vuln.title}")
                if vuln.fixed_version:
                    console.print(f"    [green]Fix available:[/] Upgrade to {vuln.fixed_version}")

        if fixed_vulns:
            count = len(fixed_vulns)
            console.print(
                f"\n[dim]Fixed Vulnerabilities ({count}) - Historical, already patched[/]"
            )
            for vuln in fixed_vulns[:5]:  # Show max 5 historical
                console.print(f"  [dim]{vuln.id} - {vuln.title} (fixed in {vuln.fixed_version})[/]")
            if len(fixed_vulns) > 5:
                console.print(f"  [dim]... and {len(fixed_vulns) - 5} more[/]")

    # Risk factors
    if health.risk_factors:
        console.print("\n[bold yellow]Risk Factors[/]")
        for risk in health.risk_factors:
            console.print(f"  [yellow]![/] {risk}")

    # Positive factors
    if health.positive_factors:
        console.print("\n[bold green]Positive Factors[/]")
        for positive in health.positive_factors:
            console.print(f"  [green]+[/] {positive}")

    # PyPI metadata
    if report.pypi:
        pypi = report.pypi
        console.print("\n[bold cyan]PyPI Information[/]")
        console.print(f"  Author: {pypi.author or 'Unknown'}")
        console.print(f"  License: {pypi.license or 'Unknown'}")
        console.print(f"  Total releases: {pypi.total_releases}")
        if pypi.release_date:
            console.print(f"  Last release: {pypi.release_date.strftime('%Y-%m-%d')}")
        if pypi.python_requires:
            console.print(f"  Python requires: {pypi.python_requires}")

    # Repository metadata
    if report.repository:
        repo = report.repository
        console.print("\n[bold cyan]Repository Information[/]")
        console.print(f"  URL: {repo.url}")
        console.print(f"  Stars: {repo.stars:,}")
        console.print(f"  Forks: {repo.forks:,}")
        console.print(f"  Contributors: {repo.contributors_count}")
        console.print(f"  Open issues: {repo.open_issues}")
        if repo.last_commit_date:
            console.print(f"  Last commit: {repo.last_commit_date.strftime('%Y-%m-%d')}")

    # Update available
    if report.update_available:
        console.print(f"\n[bold cyan]Update Available:[/] {report.update_available}")

    # Alternatives
    if report.alternatives:
        console.print("\n[bold cyan]Suggested Alternatives[/]")
        for alt in report.alternatives[:3]:
            name = alt.package.name
            score = alt.health_score
            effort = alt.migration_effort
            console.print(f"  {name} (score: {score:.0f}, effort: {effort})")

    console.print()


def print_alternatives_table(
    package: str,
    current_health: HealthScore,
    alternatives: list[AlternativePackage],
) -> None:
    """Print a table of alternative packages.

    Args:
        package: Original package name.
        current_health: Health score of the original package.
        alternatives: List of alternative packages.
    """
    table = Table(
        title=f"Alternatives to {package}",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )

    table.add_column("Package", style="cyan")
    table.add_column("Health Score", justify="right")
    table.add_column("vs Current", justify="right")
    table.add_column("Migration Effort")
    table.add_column("Rationale")

    for alt in alternatives:
        diff = alt.health_score - current_health.overall
        diff_style = "green" if diff > 0 else "red"
        diff_text = f"+{diff:.0f}" if diff > 0 else f"{diff:.0f}"

        effort_style = {
            "low": "green",
            "medium": "yellow",
            "high": "red",
        }.get(alt.migration_effort, "white")

        table.add_row(
            alt.package.name,
            f"{alt.health_score:.0f}",
            Text(diff_text, style=diff_style),
            Text(alt.migration_effort, style=effort_style),
            alt.rationale[:50] + "..." if len(alt.rationale) > 50 else alt.rationale,
        )

    console.print()
    console.print(f"[bold]Current package:[/] {package}")
    score = current_health.overall
    grade = current_health.grade.value
    console.print(f"[bold]Current score:[/] {score:.0f} ({grade})")
    console.print()
    console.print(table)


def print_error(message: str) -> None:
    """Print an error message to stderr."""
    err_console.print(f"[bold red]Error:[/] {message}")


def print_success(message: str) -> None:
    """Print a success message to stderr."""
    err_console.print(f"[bold green]Success:[/] {message}")


def print_warning(message: str) -> None:
    """Print a warning message to stderr."""
    err_console.print(f"[bold yellow]Warning:[/] {message}")


def print_info(message: str) -> None:
    """Print an info message to stderr."""
    err_console.print(f"[cyan]Info:[/] {message}")
