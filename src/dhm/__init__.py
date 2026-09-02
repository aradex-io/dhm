"""
Dependency Health Monitor (DHM)

A comprehensive health assessment tool for Python project dependencies.
Aggregates data from PyPI, GitHub, and security databases to calculate
composite health scores, identify vulnerabilities, and recommend alternatives.

Quick Start:
    >>> import asyncio
    >>> from dhm import check
    >>> report = asyncio.run(check("requests"))
    >>> print(f"{report.package.name}: {report.health.grade}")
    requests: B

    # Or use synchronous API:
    >>> from dhm import check_sync
    >>> report = check_sync("flask")
    >>> if report.health.has_open_vulnerabilities:
    ...     print("Update needed!")
"""

__version__ = "0.4.1"

# High-level API (recommended for most users)
from dhm.api import (
    check,
    check_packages,
    check_sync,
    scan,
    scan_installed,
    scan_sync,
)

# Core components (for advanced usage)
from dhm.core.calculator import HealthCalculator

# Exceptions
from dhm.core.exceptions import (
    CacheError,
    DHMError,
    NetworkError,
    PackageNotFoundError,
    ParsingError,
    RateLimitError,
    RepositoryNotFoundError,
    ValidationError,
)

# Data models
from dhm.core.models import (
    AlternativePackage,
    ConfidenceLevel,
    DependencyReport,
    HealthGrade,
    HealthScore,
    MaintenanceStatus,
    PackageIdentifier,
    PyPIMetadata,
    RepositoryMetadata,
    RiskLevel,
    Vulnerability,
)
from dhm.core.resolver import DependencyResolver

__all__ = [
    # Version
    "__version__",
    # High-level API
    "check",
    "check_sync",
    "check_packages",
    "scan",
    "scan_sync",
    "scan_installed",
    # Models
    "AlternativePackage",
    "ConfidenceLevel",
    "DependencyReport",
    "HealthGrade",
    "HealthScore",
    "MaintenanceStatus",
    "PackageIdentifier",
    "PyPIMetadata",
    "RepositoryMetadata",
    "RiskLevel",
    "Vulnerability",
    # Core
    "HealthCalculator",
    "DependencyResolver",
    # Exceptions
    "DHMError",
    "PackageNotFoundError",
    "RepositoryNotFoundError",
    "RateLimitError",
    "CacheError",
    "ParsingError",
    "ValidationError",
    "NetworkError",
]
