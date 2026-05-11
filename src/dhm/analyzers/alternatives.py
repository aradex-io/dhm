"""
Alternative package recommender.

Finds and ranks alternative packages that could replace a dependency
with better health scores or different characteristics.
"""

from typing import TYPE_CHECKING

from dhm.core.models import (
    AlternativePackage,
    HealthScore,
    PackageIdentifier,
)

if TYPE_CHECKING:
    from dhm.reports.generator import ReportGenerator


class AlternativesRecommender:
    """Find and rank alternative packages.

    Uses a database of known alternatives and searches for similar
    packages to provide recommendations for replacing dependencies.
    """

    # Known alternatives database
    # Maps package name to list of potential alternatives
    KNOWN_ALTERNATIVES: dict[str, list[str]] = {
        # HTTP clients
        "requests": ["httpx", "aiohttp", "urllib3", "httpcore"],
        "urllib3": ["httpx", "aiohttp", "requests"],
        "aiohttp": ["httpx", "requests", "httpcore"],

        # Web frameworks
        "flask": ["fastapi", "starlette", "litestar", "quart"],
        "django": ["fastapi", "flask", "starlette"],
        "bottle": ["flask", "fastapi", "starlette"],
        "tornado": ["fastapi", "aiohttp", "starlette"],
        "pyramid": ["flask", "fastapi", "django"],

        # Async frameworks
        "starlette": ["fastapi", "litestar", "quart"],
        "fastapi": ["starlette", "litestar", "flask"],

        # Image processing
        "pillow": ["opencv-python", "scikit-image", "imageio"],
        "opencv-python": ["pillow", "scikit-image", "imageio"],

        # YAML parsing
        "pyyaml": ["ruamel.yaml", "strictyaml", "oyaml"],
        "ruamel.yaml": ["pyyaml", "strictyaml"],

        # Date/time handling
        "python-dateutil": ["pendulum", "arrow", "dateparser", "maya"],
        "arrow": ["pendulum", "python-dateutil", "dateparser"],
        "pendulum": ["arrow", "python-dateutil", "dateparser"],

        # HTML parsing
        "beautifulsoup4": ["selectolax", "lxml", "parsel", "html5lib"],
        "lxml": ["beautifulsoup4", "selectolax", "parsel"],
        "html5lib": ["beautifulsoup4", "lxml", "html5-parser"],

        # Testing
        "nose": ["pytest", "unittest"],
        "nose2": ["pytest", "unittest"],
        "mock": ["pytest-mock", "unittest.mock"],

        # JSON
        "simplejson": ["orjson", "ujson", "rapidjson"],
        "ujson": ["orjson", "simplejson", "rapidjson"],
        "orjson": ["ujson", "simplejson", "rapidjson"],

        # CLI
        "argparse": ["click", "typer", "fire"],
        "click": ["typer", "fire", "argparse"],
        "fire": ["click", "typer", "argparse"],

        # Configuration
        "configparser": ["toml", "pydantic-settings", "dynaconf"],
        "python-dotenv": ["pydantic-settings", "environs", "dynaconf"],

        # Database
        "sqlalchemy": ["peewee", "tortoise-orm", "databases"],
        "peewee": ["sqlalchemy", "tortoise-orm", "pony"],

        # Validation
        "marshmallow": ["pydantic", "attrs", "cerberus"],
        "cerberus": ["pydantic", "marshmallow", "voluptuous"],

        # Logging
        "logging": ["loguru", "structlog"],

        # HTTP servers
        "gunicorn": ["uvicorn", "hypercorn", "daphne"],
        "uwsgi": ["gunicorn", "uvicorn", "hypercorn"],

        # Task queues
        "celery": ["rq", "huey", "dramatiq", "arq"],
        "rq": ["celery", "huey", "dramatiq"],

        # Cryptography
        "pycrypto": ["pycryptodome", "cryptography"],
        "pycryptodome": ["cryptography", "pynacl"],

        # Serialization
        "msgpack": ["msgpack-python", "cbor2", "protobuf"],
    }

    # Migration effort estimates
    MIGRATION_EFFORTS: dict[tuple[str, str], str] = {
        # Easy migrations (similar API)
        ("requests", "httpx"): "low",
        ("flask", "quart"): "low",
        ("pyyaml", "ruamel.yaml"): "low",
        ("nose", "pytest"): "low",
        ("simplejson", "orjson"): "low",
        ("gunicorn", "uvicorn"): "low",

        # Medium migrations
        ("flask", "fastapi"): "medium",
        ("django", "fastapi"): "high",
        ("requests", "aiohttp"): "medium",
        ("sqlalchemy", "peewee"): "medium",
        ("celery", "dramatiq"): "medium",

        # Harder migrations
        ("django", "flask"): "high",
        ("sqlalchemy", "tortoise-orm"): "high",
    }

    def __init__(self):
        """Initialize the alternatives recommender.

        Instance-level copies of the class-level dicts are made so that
        mutations via ``add_known_alternative`` are isolated per-instance
        and do not leak across instances or races between concurrent
        ``ReportGenerator`` workers (M-13).
        """
        self.known_alternatives: dict[str, list[str]] = {
            k: list(v) for k, v in self.KNOWN_ALTERNATIVES.items()
        }
        self.migration_efforts: dict[tuple[str, str], str] = dict(self.MIGRATION_EFFORTS)

    def find_alternatives(
        self,
        package: PackageIdentifier,
        current_health: HealthScore,
    ) -> list[AlternativePackage]:
        """Find alternatives for a package (sync version, returns known alternatives only).

        Args:
            package: The package to find alternatives for.
            current_health: Current health score of the package.

        Returns:
            List of AlternativePackage objects.
        """
        pkg_name = package.normalized_name
        alternatives = []

        # Get known alternatives
        known = self.known_alternatives.get(pkg_name, [])

        for alt_name in known:
            alt = AlternativePackage(
                package=PackageIdentifier(name=alt_name),
                health_score=0.0,  # Unknown without fetching
                migration_effort=self._estimate_migration_effort(pkg_name, alt_name),
                rationale=self._generate_rationale_simple(pkg_name, alt_name),
                api_compatibility=self._estimate_api_compatibility(pkg_name, alt_name),
            )
            alternatives.append(alt)

        return alternatives

    async def find_alternatives_async(
        self,
        package: PackageIdentifier,
        current_health: HealthScore,
        generator: "ReportGenerator",
    ) -> list[AlternativePackage]:
        """Find alternatives for a package with health scores (async version).

        Args:
            package: The package to find alternatives for.
            current_health: Current health score of the package.
            generator: ReportGenerator for fetching health data.

        Returns:
            List of AlternativePackage objects sorted by health score.
        """
        pkg_name = package.normalized_name
        alternatives = []

        # Get known alternatives
        known = self.known_alternatives.get(pkg_name, [])

        for alt_name in known:
            try:
                # Fetch health info for alternative
                report = await generator.check_package(alt_name)

                # Only include if healthier
                if report.health.overall > current_health.overall:
                    alt = AlternativePackage(
                        package=PackageIdentifier(
                            name=alt_name,
                            version=report.pypi.version if report.pypi else None,
                        ),
                        health_score=report.health.overall,
                        migration_effort=self._estimate_migration_effort(pkg_name, alt_name),
                        rationale=self._generate_rationale(
                            pkg_name,
                            alt_name,
                            report.health,
                            current_health,
                        ),
                        api_compatibility=self._estimate_api_compatibility(pkg_name, alt_name),
                    )
                    alternatives.append(alt)
            except Exception:
                # Skip alternatives we can't fetch
                pass

        # Sort by health score descending
        alternatives.sort(key=lambda a: a.health_score, reverse=True)

        return alternatives[:5]  # Return top 5

    def _estimate_migration_effort(
        self,
        from_pkg: str,
        to_pkg: str,
    ) -> str:
        """Estimate effort to migrate between packages.

        Args:
            from_pkg: Original package name.
            to_pkg: Target package name.

        Returns:
            Effort level: "low", "medium", or "high".
        """
        # Check known migration efforts
        effort = self.migration_efforts.get((from_pkg, to_pkg))
        if effort:
            return effort

        # Check reverse direction
        effort = self.migration_efforts.get((to_pkg, from_pkg))
        if effort:
            return effort

        # Heuristics for unknown migrations
        # Same prefix often means similar API
        from_prefix = from_pkg.split("-")[0].split("_")[0]
        to_prefix = to_pkg.split("-")[0].split("_")[0]

        if from_prefix == to_prefix:
            return "low"

        # Default to medium
        return "medium"

    def _estimate_api_compatibility(
        self,
        from_pkg: str,
        to_pkg: str,
    ) -> float:
        """Estimate API compatibility between packages.

        Args:
            from_pkg: Original package name.
            to_pkg: Target package name.

        Returns:
            Compatibility score from 0.0 to 1.0.
        """
        effort = self._estimate_migration_effort(from_pkg, to_pkg)

        # Map effort to compatibility
        compatibility_map = {
            "low": 0.8,
            "medium": 0.5,
            "high": 0.2,
        }

        return compatibility_map.get(effort, 0.5)

    def _generate_rationale_simple(
        self,
        from_pkg: str,
        to_pkg: str,
    ) -> str:
        """Generate a simple rationale without health data.

        Args:
            from_pkg: Original package name.
            to_pkg: Target package name.

        Returns:
            Rationale string.
        """
        # Package-specific rationales
        rationales = {
            ("requests", "httpx"): "Modern async-first HTTP client with sync support",
            ("flask", "fastapi"): "Modern async framework with automatic API docs",
            ("pyyaml", "ruamel.yaml"): "Better YAML 1.2 support, preserves comments",
            ("nose", "pytest"): "More actively maintained, better plugin ecosystem",
            ("simplejson", "orjson"): "Much faster JSON serialization",
            ("gunicorn", "uvicorn"): "ASGI support, better for async frameworks",
            ("celery", "dramatiq"): "Simpler API, better defaults",
            ("beautifulsoup4", "selectolax"): "Much faster HTML parsing",
            ("python-dateutil", "pendulum"): "Cleaner API, timezone handling",
        }

        key = (from_pkg, to_pkg)
        if key in rationales:
            return rationales[key]

        return f"Alternative to {from_pkg}"

    def _generate_rationale(
        self,
        from_pkg: str,
        to_pkg: str,
        alt_health: HealthScore,
        current_health: HealthScore,
    ) -> str:
        """Generate a rationale for recommending an alternative.

        Args:
            from_pkg: Original package name.
            to_pkg: Target package name.
            alt_health: Health score of the alternative.
            current_health: Health score of the current package.

        Returns:
            Rationale string explaining why the alternative is recommended.
        """
        parts = []

        # Score improvement
        score_diff = alt_health.overall - current_health.overall
        if score_diff > 20:
            parts.append(f"Significantly healthier (+{score_diff:.0f} points)")
        elif score_diff > 10:
            parts.append(f"Healthier (+{score_diff:.0f} points)")

        # Security improvement
        if (alt_health.security_score > current_health.security_score
                and current_health.has_vulnerabilities):
            parts.append("No known vulnerabilities")

        # Maintenance improvement
        if (alt_health.maintenance_score - current_health.maintenance_score > 15):
            parts.append("Better maintained")

        # Community improvement
        if (alt_health.community_score - current_health.community_score > 15):
            parts.append("Larger community")

        # Add package-specific info
        specific = self._generate_rationale_simple(from_pkg, to_pkg)
        if specific != f"Alternative to {from_pkg}":
            parts.append(specific)

        if parts:
            return "; ".join(parts)
        else:
            return "Better overall health score"

    def get_known_alternatives(self, package_name: str) -> list[str]:
        """Get list of known alternatives for a package.

        Args:
            package_name: Package name to look up.

        Returns:
            List of alternative package names.
        """
        normalized = package_name.lower().replace("_", "-")
        return self.known_alternatives.get(normalized, [])

    def add_known_alternative(
        self,
        package_name: str,
        alternative: str,
        effort: str = "medium",
    ) -> None:
        """Add a known alternative to the database.

        Args:
            package_name: Package name.
            alternative: Alternative package name.
            effort: Migration effort ("low", "medium", "high").
        """
        normalized = package_name.lower().replace("_", "-")

        if normalized not in self.known_alternatives:
            self.known_alternatives[normalized] = []

        if alternative not in self.known_alternatives[normalized]:
            self.known_alternatives[normalized].append(alternative)

        self.migration_efforts[(normalized, alternative)] = effort
