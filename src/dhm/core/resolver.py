"""
Dependency Resolver for parsing various dependency file formats.

This module implements parsers for requirements.txt, pyproject.toml,
and other common Python dependency file formats.
"""

import json
import os
import re
import sys
from abc import ABC, abstractmethod
from pathlib import Path

from packaging.specifiers import InvalidSpecifier, SpecifierSet

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


def _extract_pinned_version(specifier: str) -> str | None:
    """Return the exact pinned version from a PEP 440 specifier, or None.

    Uses ``packaging`` so pre-releases (``1.0.0rc1``), post/dev releases, and
    epochs are preserved intact instead of being truncated by a ``[\\d.]`` regex.
    Only ``==``/``===`` pins yield a concrete version; ranges return None.
    """
    if not specifier:
        return None
    try:
        spec_set = SpecifierSet(specifier)
    except InvalidSpecifier:
        return None
    for spec in spec_set:
        if spec.operator in ("==", "==="):
            # Strip a trailing ".*" wildcard pin (e.g. "==1.2.*").
            return spec.version.rstrip(".*") or None
    return None


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

            # Strip a trailing line-continuation backslash (hashed requirements:
            # "pkg==1.0 \" followed by indented "--hash=..." lines).
            if line.endswith("\\"):
                line = line[:-1].strip()

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

        version = _extract_pinned_version(specifier) if specifier else None

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

        version = _extract_pinned_version(specifier) if specifier else None

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


class PoetryLockSource(DependencySource):
    """Parse poetry.lock files (full pinned resolution, incl. transitive)."""

    def can_parse(self, path: Path) -> bool:
        return path.name == "poetry.lock"

    def parse(self, path: Path) -> list[PackageIdentifier]:
        try:
            data = tomllib.loads(path.read_bytes().decode("utf-8"))
        except OSError as e:
            raise ParsingError(str(path), f"Failed to read file: {e}")
        except tomllib.TOMLDecodeError as e:
            raise ParsingError(str(path), f"Invalid TOML: {e}")

        packages = []
        for entry in data.get("package", []):
            name = entry.get("name")
            if not name:
                continue
            packages.append(PackageIdentifier(name=name, version=entry.get("version")))
        return packages


class UvLockSource(DependencySource):
    """Parse uv.lock files (full pinned resolution, incl. transitive)."""

    def can_parse(self, path: Path) -> bool:
        return path.name == "uv.lock"

    def parse(self, path: Path) -> list[PackageIdentifier]:
        try:
            data = tomllib.loads(path.read_bytes().decode("utf-8"))
        except OSError as e:
            raise ParsingError(str(path), f"Failed to read file: {e}")
        except tomllib.TOMLDecodeError as e:
            raise ParsingError(str(path), f"Invalid TOML: {e}")

        packages = []
        for entry in data.get("package", []):
            name = entry.get("name")
            if not name:
                continue
            packages.append(PackageIdentifier(name=name, version=entry.get("version")))
        return packages


class PipfileLockSource(DependencySource):
    """Parse Pipfile.lock files (full pinned resolution, incl. transitive)."""

    def can_parse(self, path: Path) -> bool:
        return path.name == "Pipfile.lock"

    def parse(self, path: Path) -> list[PackageIdentifier]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except OSError as e:
            raise ParsingError(str(path), f"Failed to read file: {e}")
        except json.JSONDecodeError as e:
            raise ParsingError(str(path), f"Invalid JSON: {e}")

        packages = []
        for section in ("default", "develop"):
            for name, info in (data.get(section) or {}).items():
                if not name:
                    continue
                version = None
                if isinstance(info, dict):
                    raw = info.get("version")
                    if isinstance(raw, str):
                        version = raw.lstrip("=") or None
                packages.append(PackageIdentifier(name=name, version=version))
        return packages


# Lockfile source classes, in priority order (most-authoritative first).
LOCKFILE_SOURCES: tuple[type[DependencySource], ...] = (
    PoetryLockSource,
    UvLockSource,
    PipfileLockSource,
)


class DependencyResolver:
    """Orchestrates dependency resolution from various sources."""

    # Manifest sources declare *direct* dependencies; lockfile sources contain
    # the full pinned resolution (direct + transitive).
    MANIFEST_FILENAMES = (
        "pyproject.toml",
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-test.txt",
        "requirements-prod.txt",
    )
    LOCKFILE_FILENAMES = ("poetry.lock", "uv.lock", "Pipfile.lock")

    # Directories that never contain a project's own manifests, or that would
    # blow up the search (vendored deps, VCS metadata, caches, virtualenvs).
    IGNORED_DIR_NAMES = frozenset(
        {
            ".git",
            ".hg",
            ".svn",
            "__pycache__",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            ".tox",
            ".nox",
            ".venv",
            "venv",
            "env",
            ".env",
            "node_modules",
            "site-packages",
            "dist",
            "build",
            ".eggs",
            "vendor",
        }
    )
    # How many directory levels below project_path to search for manifests.
    MAX_SCAN_DEPTH = 4

    def __init__(self):
        """Initialize the resolver with default source parsers."""
        self.manifest_sources: list[DependencySource] = [
            PyProjectTomlSource(),
            RequirementsTxtSource(),
        ]
        self.lockfile_sources: list[DependencySource] = [cls() for cls in LOCKFILE_SOURCES]
        # Unified list used by resolve_file / can_parse lookups.
        self.sources: list[DependencySource] = self.manifest_sources + self.lockfile_sources

    def add_source(self, source: DependencySource) -> None:
        """Add a custom dependency source parser.

        Args:
            source: A DependencySource implementation.
        """
        self.manifest_sources.insert(0, source)  # Custom sources take priority
        self.sources.insert(0, source)

    def resolve(
        self,
        project_path: Path,
        include_transitive: bool = False,
    ) -> list[PackageIdentifier]:
        """Find and parse dependencies for a project.

        Args:
            project_path: Path to a project root or a specific dependency file.
            include_transitive: If True, include transitive dependencies. When a
                lockfile is present its full pinned set is used; otherwise the
                installed-environment requirement graph is walked from the direct
                dependencies.

        Returns:
            Deduplicated list of PackageIdentifier objects with ``is_direct`` set.
        """
        if project_path.is_file():
            return self._resolve_single_file(project_path, include_transitive)

        direct_pkgs: list[PackageIdentifier] = []
        for file in self._find_manifest_files(project_path):
            for source in self.manifest_sources:
                if source.can_parse(file):
                    try:
                        direct_pkgs.extend(source.parse(file))
                    except ParsingError:
                        pass
                    break

        locked_pkgs: list[PackageIdentifier] = []
        for file in self._find_lockfiles(project_path):
            for source in self.lockfile_sources:
                if source.can_parse(file):
                    try:
                        locked_pkgs.extend(source.parse(file))
                    except ParsingError:
                        pass
                    break

        return self._combine(direct_pkgs, locked_pkgs, include_transitive)

    def _resolve_single_file(
        self, path: Path, include_transitive: bool
    ) -> list[PackageIdentifier]:
        """Resolve when a specific file (manifest or lockfile) is provided."""
        is_lockfile = any(s.can_parse(path) for s in self.lockfile_sources)
        pkgs: list[PackageIdentifier] = []
        for source in self.sources:
            if source.can_parse(path):
                pkgs = source.parse(path)
                break

        if is_lockfile:
            # A lockfile alone has no manifest to distinguish direct vs
            # transitive; report the full set (all marked direct=unknown->True).
            return self._deduplicate(pkgs)

        # A manifest file: entries are direct. Optionally expand via installed env.
        for p in pkgs:
            p.is_direct = True
        if include_transitive:
            pkgs = self._expand_transitive_from_env(pkgs)
        return self._deduplicate(pkgs)

    def resolve_installed(self) -> list[PackageIdentifier]:
        """Return every distribution installed in the current environment.

        Versions are the actually-installed versions (not latest-on-PyPI).
        """
        from dhm.core.environment import installed_versions

        return [
            PackageIdentifier(name=name, version=version, is_direct=True)
            for name, version in sorted(installed_versions().items())
        ]

    def _combine(
        self,
        direct_pkgs: list[PackageIdentifier],
        locked_pkgs: list[PackageIdentifier],
        include_transitive: bool,
    ) -> list[PackageIdentifier]:
        """Combine manifest (direct) and lockfile (full) results."""
        direct_names = {p.normalized_name for p in direct_pkgs}

        if locked_pkgs:
            # Lockfile is authoritative for versions and the full graph.
            for p in locked_pkgs:
                p.is_direct = (p.normalized_name in direct_names) if direct_names else True
            if include_transitive or not direct_names:
                return self._deduplicate(locked_pkgs)
            return self._deduplicate([p for p in locked_pkgs if p.is_direct])

        # No lockfile: manifests give the direct set.
        for p in direct_pkgs:
            p.is_direct = True
        if include_transitive:
            direct_pkgs = self._expand_transitive_from_env(direct_pkgs)
        return self._deduplicate(direct_pkgs)

    def _expand_transitive_from_env(
        self, direct_pkgs: list[PackageIdentifier]
    ) -> list[PackageIdentifier]:
        """Add transitive deps of *direct_pkgs* using the installed-env graph."""
        from dhm.core.environment import (
            installed_requires_graph,
            installed_versions,
            transitive_closure,
        )

        direct_names = {p.normalized_name for p in direct_pkgs}
        graph = installed_requires_graph()
        versions = installed_versions()
        transitive = transitive_closure(direct_names, graph) - direct_names

        result = list(direct_pkgs)
        for name in sorted(transitive):
            result.append(
                PackageIdentifier(name=name, version=versions.get(name), is_direct=False)
            )
        return result

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

    def _iter_scan_dirs(self, project_path: Path):
        """Yield project_path and its subdirectories, pruning noise/vendor dirs.

        Bounded by MAX_SCAN_DEPTH so a scan of a large tree stays fast; skips
        VCS, cache, virtualenv, and vendored-dependency directories that would
        otherwise flood results with irrelevant manifests.
        """
        yield project_path
        root_depth = len(project_path.parts)
        for dirpath, dirnames, _ in os.walk(project_path):
            depth = len(Path(dirpath).parts) - root_depth
            if depth >= self.MAX_SCAN_DEPTH:
                dirnames[:] = []
                continue
            dirnames[:] = [
                d
                for d in dirnames
                if d not in self.IGNORED_DIR_NAMES and not d.startswith(".")
            ]
            for d in sorted(dirnames):
                yield Path(dirpath) / d

    def _find_manifest_files(self, project_path: Path) -> list[Path]:
        """Find manifest files (declaring direct dependencies), searching
        project_path and its subdirectories."""
        found: list[Path] = []
        for directory in self._iter_scan_dirs(project_path):
            for filename in self.MANIFEST_FILENAMES:
                file_path = directory / filename
                if file_path.exists() and file_path not in found:
                    found.append(file_path)
            for path in sorted(directory.glob("requirements*.txt")):
                if path not in found:
                    found.append(path)
        return found

    def _find_lockfiles(self, project_path: Path) -> list[Path]:
        """Find lockfiles (full pinned resolution), searching project_path
        and its subdirectories."""
        found: list[Path] = []
        for directory in self._iter_scan_dirs(project_path):
            for filename in self.LOCKFILE_FILENAMES:
                file_path = directory / filename
                if file_path.exists() and file_path not in found:
                    found.append(file_path)
        return found

    def _find_dependency_files(self, project_path: Path) -> list[Path]:
        """Find all dependency files (manifests + lockfiles) in a directory."""
        return self._find_manifest_files(project_path) + self._find_lockfiles(project_path)

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
                # A package seen as both direct and transitive is direct.
                is_direct = existing.is_direct or pkg.is_direct
                # Prefer the one with a version specified
                if pkg.version and not existing.version:
                    seen[key] = pkg
                seen[key].is_direct = is_direct
                # Merge extras
                if pkg.extras or existing.extras:
                    merged_extras = tuple(set(existing.extras) | set(pkg.extras))
                    seen[key] = PackageIdentifier(
                        name=seen[key].name,
                        version=seen[key].version or pkg.version,
                        extras=merged_extras,
                        is_direct=is_direct,
                    )

        return list(seen.values())
