"""
Dependency Resolver for parsing various dependency file formats.

This module implements parsers for requirements.txt, pyproject.toml,
and other common Python dependency file formats.
"""

import re
import sys
from abc import ABC, abstractmethod
from pathlib import Path

from dhm.core.exceptions import ParsingError, ValidationError
from dhm.core.models import PackageIdentifier
from dhm.core.validation import (
    MAX_INCLUDE_DEPTH,
    check_recursion_depth,
    validate_include_path,
)

# Handle tomli import for Python 3.10 vs 3.11+
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


class DependencySource(ABC):
    """Abstract base class for dependency file parsers."""

    @abstractmethod
    def parse(self, path: Path) -> list[PackageIdentifier]:
        """Extract dependencies from a file.

        Args:
            path: Path to the dependency file.

        Returns:
            List of PackageIdentifier objects.

        Raises:
            ParsingError: If the file cannot be parsed.
        """
        pass

    @abstractmethod
    def can_parse(self, path: Path) -> bool:
        """Check if this source can parse the given file.

        Args:
            path: Path to check.

        Returns:
            True if this parser can handle the file.
        """
        pass


class RequirementsTxtSource(DependencySource):
    """Parse requirements.txt files."""

    # Regex patterns for parsing requirement lines
    REQUIREMENT_PATTERN = re.compile(
        r"^(?P<name>[A-Za-z0-9][-A-Za-z0-9._]*)"
        r"(?:\[(?P<extras>[^\]]+)\])?"
        r"(?:\s*(?P<specifier>[<>=!~][^;#]*))?"
        r"(?:\s*;[^#]*)?"  # Environment markers
        r"(?:\s*#.*)?$",  # Comments
        re.IGNORECASE,
    )

    def can_parse(self, path: Path) -> bool:
        """Check if this is a requirements file."""
        name = path.name.lower()
        return (
            name == "requirements.txt"
            or (name.startswith("requirements") and name.endswith(".txt"))
        )

    def parse(
        self,
        path: Path,
        base_path: Path | None = None,
        _depth: int = 0,
    ) -> list[PackageIdentifier]:
        """Parse requirements.txt and return package identifiers.

        Args:
            path: Path to the requirements file.
            base_path: Root project directory for path traversal validation.
                       If None, uses the parent of the initial file.
            _depth: Current recursion depth (internal use).

        Returns:
            List of PackageIdentifier objects.

        Raises:
            ParsingError: If the file cannot be parsed.
            ValidationError: If include depth exceeded or path traversal detected.
        """
        # Check recursion depth to prevent infinite loops
        check_recursion_depth(_depth, MAX_INCLUDE_DEPTH)

        # Set base_path on first call
        if base_path is None:
            base_path = path.parent.resolve()

        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            raise ParsingError(str(path), f"Failed to read file: {e}")

        packages = []
        included_files: list[Path] = []

        for line_num, line in enumerate(content.splitlines(), 1):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Handle -r includes with path traversal protection
            if line.startswith("-r ") or line.startswith("--requirement "):
                include_path_str = line.split(maxsplit=1)[1].strip()
                try:
                    # Validate the include path stays within project boundary
                    validated_path = validate_include_path(
                        include_path_str, base_path, path
                    )
                    if validated_path.exists():
                        included_files.append(validated_path)
                except ValidationError:
                    # Log warning but continue parsing (don't fail on invalid includes)
                    pass
                continue

            # Handle -e (editable installs) - skip for now
            if line.startswith("-e ") or line.startswith("--editable "):
                continue

            # Handle other pip options - skip
            if line.startswith("-"):
                continue

            # Parse the requirement
            pkg = self._parse_requirement(line, path, line_num)
            if pkg:
                packages.append(pkg)

        # Process included files with incremented depth
        for include_file in included_files:
            try:
                packages.extend(
                    self.parse(include_file, base_path=base_path, _depth=_depth + 1)
                )
            except (ParsingError, ValidationError):
                # Skip failed includes but don't propagate errors
                pass

        return packages

    def _parse_requirement(
        self,
        line: str,
        path: Path,
        line_num: int,
    ) -> PackageIdentifier | None:
        """Parse a single requirement line."""
        # Handle URLs (skip them)
        if "://" in line or line.startswith("git+"):
            return None

        # Try to match the requirement pattern
        match = self.REQUIREMENT_PATTERN.match(line)
        if not match:
            # Try a more lenient parse
            parts = re.split(r"[<>=!~\[\];]", line)
            if parts and parts[0].strip():
                name = parts[0].strip()
                return PackageIdentifier(name=name)
            return None

        name = match.group("name")
        extras_str = match.group("extras")
        specifier = match.group("specifier")

        extras = ()
        if extras_str:
            extras = tuple(e.strip() for e in extras_str.split(","))

        version = None
        if specifier:
            # Extract exact version if specified with ==
            exact_match = re.search(r"==\s*([\d.]+)", specifier)
            if exact_match:
                version = exact_match.group(1)

        return PackageIdentifier(name=name, version=version, extras=extras)


class PyProjectTomlSource(DependencySource):
    """Parse pyproject.toml files (PEP 621 and Poetry)."""

    def can_parse(self, path: Path) -> bool:
        """Check if this is a pyproject.toml file."""
        return path.name == "pyproject.toml"

    def parse(self, path: Path) -> list[PackageIdentifier]:
        """Parse pyproject.toml and return package identifiers."""
        try:
            content = path.read_bytes()
            data = tomllib.loads(content.decode("utf-8"))
        except OSError as e:
            raise ParsingError(str(path), f"Failed to read file: {e}")
        except tomllib.TOMLDecodeError as e:
            raise ParsingError(str(path), f"Invalid TOML: {e}")

        packages = []

        # PEP 621 format: [project.dependencies]
        if "project" in data:
            project = data["project"]

            # Main dependencies
            if "dependencies" in project:
                for dep in project["dependencies"]:
                    pkg = self._parse_pep508(dep)
                    if pkg:
                        packages.append(pkg)

            # Optional dependencies
            if "optional-dependencies" in project:
                for group, deps in project["optional-dependencies"].items():
                    for dep in deps:
                        pkg = self._parse_pep508(dep)
                        if pkg:
                            packages.append(pkg)

        # Poetry format: [tool.poetry.dependencies]
        if "tool" in data and "poetry" in data["tool"]:
            poetry = data["tool"]["poetry"]

            # Main dependencies
            if "dependencies" in poetry:
                for name, spec in poetry["dependencies"].items():
                    if name.lower() == "python":
                        continue
                    pkg = self._parse_poetry_dep(name, spec)
                    if pkg:
                        packages.append(pkg)

            # Dev dependencies
            if "dev-dependencies" in poetry:
                for name, spec in poetry["dev-dependencies"].items():
                    pkg = self._parse_poetry_dep(name, spec)
                    if pkg:
                        packages.append(pkg)

            # Group dependencies (Poetry 1.2+)
            if "group" in poetry:
                for group_name, group_data in poetry["group"].items():
                    if "dependencies" in group_data:
                        for name, spec in group_data["dependencies"].items():
                            pkg = self._parse_poetry_dep(name, spec)
                            if pkg:
                                packages.append(pkg)

        return packages

    def _parse_pep508(self, dep: str) -> PackageIdentifier | None:
        """Parse a PEP 508 dependency string."""
        # PEP 508 format: name[extras](<version specifier>)(; markers)
        pattern = re.compile(
            r"""
            ^
            (?P<name>[A-Za-z0-9][-A-Za-z0-9._]*)
            (?:\[(?P<extras>[^\]]+)\])?
            (?:\s*(?P<specifier>[<>=!~][^;]*))?
            (?:\s*;.*)?
            $
            """,
            re.VERBOSE,
        )

        match = pattern.match(dep.strip())
        if not match:
            return None

        name = match.group("name")
        extras_str = match.group("extras")
        specifier = match.group("specifier")

        extras = ()
        if extras_str:
            extras = tuple(e.strip() for e in extras_str.split(","))

        version = None
        if specifier:
            # Extract exact version if specified with ==
            exact_match = re.search(r"==\s*([\d.]+)", specifier)
            if exact_match:
                version = exact_match.group(1)

        return PackageIdentifier(name=name, version=version, extras=extras)

    def _parse_poetry_dep(
        self,
        name: str,
        spec: str | dict,
    ) -> PackageIdentifier | None:
        """Parse a Poetry dependency specification."""
        version = None
        extras = ()

        if isinstance(spec, str):
            # Simple version string: "^1.0.0" or ">=1.0,<2.0"
            # Extract version number if it looks like an exact version
            exact_match = re.search(r"^(\d+\.\d+(?:\.\d+)?)", spec)
            if exact_match:
                version = exact_match.group(1)
        elif isinstance(spec, dict):
            # Complex spec: {version = "^1.0", extras = ["dev"]}
            if "version" in spec:
                exact_match = re.search(r"^(\d+\.\d+(?:\.\d+)?)", spec["version"])
                if exact_match:
                    version = exact_match.group(1)
            if "extras" in spec:
                extras = tuple(spec["extras"])

            # Skip git/path/url dependencies
            if any(k in spec for k in ("git", "path", "url")):
                return None

        return PackageIdentifier(name=name, version=version, extras=extras)


class DependencyResolver:
    """Orchestrates dependency resolution from various sources."""

    def __init__(self):
        """Initialize the resolver with default source parsers."""
        self.sources: list[DependencySource] = [
            PyProjectTomlSource(),
            RequirementsTxtSource(),
        ]

    def add_source(self, source: DependencySource) -> None:
        """Add a custom dependency source parser.

        Args:
            source: A DependencySource implementation.
        """
        self.sources.insert(0, source)  # Custom sources take priority

    def resolve(self, project_path: Path) -> list[PackageIdentifier]:
        """Find and parse all dependency files in a project.

        Args:
            project_path: Path to project root or a specific dependency file.

        Returns:
            Deduplicated list of PackageIdentifier objects.
        """
        dependencies = []

        if project_path.is_file():
            # Single file provided
            for source in self.sources:
                if source.can_parse(project_path):
                    dependencies.extend(source.parse(project_path))
                    break
        else:
            # Directory provided - search for dependency files
            for file in self._find_dependency_files(project_path):
                for source in self.sources:
                    if source.can_parse(file):
                        try:
                            dependencies.extend(source.parse(file))
                        except ParsingError:
                            # Continue with other files if one fails
                            pass
                        break

        return self._deduplicate(dependencies)

    def resolve_file(self, file_path: Path) -> list[PackageIdentifier]:
        """Parse a specific dependency file.

        Args:
            file_path: Path to the dependency file.

        Returns:
            List of PackageIdentifier objects.

        Raises:
            ParsingError: If no suitable parser is found or parsing fails.
        """
        for source in self.sources:
            if source.can_parse(file_path):
                return source.parse(file_path)

        raise ParsingError(
            str(file_path),
            "No suitable parser found for this file type.",
        )

    def _find_dependency_files(self, project_path: Path) -> list[Path]:
        """Find all dependency files in a project directory.

        Args:
            project_path: Path to project root.

        Returns:
            List of paths to dependency files.
        """
        dependency_files = []

        # Priority order for dependency files
        priority_files = [
            "pyproject.toml",
            "requirements.txt",
            "requirements-dev.txt",
            "requirements-test.txt",
            "requirements-prod.txt",
        ]

        # Check priority files first
        for filename in priority_files:
            file_path = project_path / filename
            if file_path.exists():
                dependency_files.append(file_path)

        # Look for other requirements files
        for path in project_path.glob("requirements*.txt"):
            if path not in dependency_files:
                dependency_files.append(path)

        return dependency_files

    def _deduplicate(
        self,
        packages: list[PackageIdentifier],
    ) -> list[PackageIdentifier]:
        """Remove duplicate packages, keeping the most specific version.

        Args:
            packages: List of packages that may contain duplicates.

        Returns:
            Deduplicated list.
        """
        seen: dict[str, PackageIdentifier] = {}

        for pkg in packages:
            key = pkg.normalized_name

            if key not in seen:
                seen[key] = pkg
            else:
                existing = seen[key]
                # Prefer the one with a version specified
                if pkg.version and not existing.version:
                    seen[key] = pkg
                # Merge extras
                if pkg.extras or existing.extras:
                    merged_extras = tuple(set(existing.extras) | set(pkg.extras))
                    seen[key] = PackageIdentifier(
                        name=existing.name,
                        version=existing.version or pkg.version,
                        extras=merged_extras,
                    )

        return list(seen.values())
