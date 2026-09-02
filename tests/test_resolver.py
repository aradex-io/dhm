"""
Tests for the dependency resolver.
"""


import pytest

from dhm.core.exceptions import ParsingError
from dhm.core.resolver import (
    DependencyResolver,
    PyProjectTomlSource,
    RequirementsTxtSource,
)


class TestRequirementsTxtSource:
    """Tests for RequirementsTxtSource parser."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return RequirementsTxtSource()

    def test_can_parse_requirements_txt(self, parser, tmp_path):
        """Test detection of requirements.txt files."""
        assert parser.can_parse(tmp_path / "requirements.txt")
        assert parser.can_parse(tmp_path / "requirements-dev.txt")
        assert parser.can_parse(tmp_path / "requirements-test.txt")
        assert not parser.can_parse(tmp_path / "pyproject.toml")

    def test_parse_simple(self, parser, tmp_path):
        """Test parsing simple requirements."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests\nclick\n")

        packages = parser.parse(req_file)

        assert len(packages) == 2
        assert any(p.name == "requests" for p in packages)
        assert any(p.name == "click" for p in packages)

    def test_parse_with_versions(self, parser, tmp_path):
        """Test parsing requirements with version specifiers."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.28.0\nclick>=8.0.0\n")

        packages = parser.parse(req_file)

        requests_pkg = next(p for p in packages if p.name == "requests")
        assert requests_pkg.version == "2.28.0"

    def test_parse_with_extras(self, parser, tmp_path):
        """Test parsing requirements with extras."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests[security,socks]==2.28.0\n")

        packages = parser.parse(req_file)

        assert len(packages) == 1
        assert packages[0].name == "requests"
        assert "security" in packages[0].extras
        assert "socks" in packages[0].extras

    def test_parse_ignores_comments(self, parser, tmp_path):
        """Test that comments are ignored."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("# This is a comment\nrequests\n# Another comment\n")

        packages = parser.parse(req_file)

        assert len(packages) == 1
        assert packages[0].name == "requests"

    def test_parse_ignores_empty_lines(self, parser, tmp_path):
        """Test that empty lines are ignored."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests\n\n\nclick\n")

        packages = parser.parse(req_file)

        assert len(packages) == 2

    def test_parse_with_includes(self, parser, tmp_path):
        """Test parsing with -r includes."""
        base_file = tmp_path / "requirements-base.txt"
        base_file.write_text("requests\n")

        main_file = tmp_path / "requirements.txt"
        main_file.write_text("-r requirements-base.txt\nclick\n")

        packages = parser.parse(main_file)

        assert len(packages) == 2
        assert any(p.name == "requests" for p in packages)
        assert any(p.name == "click" for p in packages)

    def test_parse_skips_options(self, parser, tmp_path):
        """Test that pip options are skipped."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text(
            "--index-url https://pypi.org/simple\n"
            "-e ./local_package\n"
            "requests\n"
        )

        packages = parser.parse(req_file)

        assert len(packages) == 1
        assert packages[0].name == "requests"


class TestPyProjectTomlSource:
    """Tests for PyProjectTomlSource parser."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return PyProjectTomlSource()

    def test_can_parse_pyproject(self, parser, tmp_path):
        """Test detection of pyproject.toml files."""
        assert parser.can_parse(tmp_path / "pyproject.toml")
        assert not parser.can_parse(tmp_path / "requirements.txt")

    def test_parse_pep621(self, parser, tmp_path):
        """Test parsing PEP 621 format."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"
version = "1.0.0"
dependencies = [
    "requests>=2.28.0",
    "click",
]
""")

        packages = parser.parse(pyproject)

        assert len(packages) == 2
        assert any(p.name == "requests" for p in packages)
        assert any(p.name == "click" for p in packages)

    def test_parse_optional_dependencies(self, parser, tmp_path):
        """Test parsing optional dependencies."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"
version = "1.0.0"
dependencies = ["requests"]

[project.optional-dependencies]
dev = ["pytest", "mypy"]
""")

        packages = parser.parse(pyproject)

        assert len(packages) == 3
        assert any(p.name == "pytest" for p in packages)

    def test_parse_poetry_format(self, parser, tmp_path):
        """Test parsing Poetry format."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.poetry]
name = "test"
version = "1.0.0"

[tool.poetry.dependencies]
python = "^3.10"
requests = "^2.28.0"
click = {version = "^8.0", extras = ["testing"]}

[tool.poetry.dev-dependencies]
pytest = "^7.0"
""")

        packages = parser.parse(pyproject)

        # Should exclude python
        assert not any(p.name.lower() == "python" for p in packages)
        assert any(p.name == "requests" for p in packages)
        assert any(p.name == "click" for p in packages)
        assert any(p.name == "pytest" for p in packages)

    def test_parse_poetry_groups(self, parser, tmp_path):
        """Test parsing Poetry 1.2+ group format."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.poetry]
name = "test"
version = "1.0.0"

[tool.poetry.dependencies]
python = "^3.10"
requests = "^2.28.0"

[tool.poetry.group.dev.dependencies]
pytest = "^7.0"
""")

        packages = parser.parse(pyproject)

        assert any(p.name == "pytest" for p in packages)

    def test_parse_invalid_toml(self, parser, tmp_path):
        """Test parsing invalid TOML raises error."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("this is not valid toml [[[")

        with pytest.raises(ParsingError):
            parser.parse(pyproject)


class TestDependencyResolver:
    """Tests for DependencyResolver class."""

    @pytest.fixture
    def resolver(self):
        """Create a resolver instance."""
        return DependencyResolver()

    def test_resolve_requirements_file(self, resolver, tmp_requirements_txt):
        """Test resolving a requirements.txt file directly."""
        packages = resolver.resolve(tmp_requirements_txt)

        assert len(packages) >= 3
        assert any(p.name == "requests" for p in packages)
        assert any(p.name == "click" for p in packages)
        assert any(p.name == "rich" for p in packages)

    def test_resolve_pyproject_file(self, resolver, tmp_pyproject_toml):
        """Test resolving a pyproject.toml file directly."""
        packages = resolver.resolve(tmp_pyproject_toml)

        assert any(p.name == "requests" for p in packages)
        assert any(p.name == "click" for p in packages)

    def test_resolve_project_directory(self, resolver, tmp_project_dir):
        """Test resolving all dependency files in a directory."""
        packages = resolver.resolve(tmp_project_dir)

        # Should find packages from multiple files
        assert any(p.name == "requests" for p in packages)
        assert any(p.name == "click" for p in packages)
        assert any(p.name == "rich" for p in packages)
        assert any(p.name == "pytest" for p in packages)

    def test_resolve_deduplicates(self, resolver, tmp_path):
        """Test that duplicate packages are deduplicated."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests\nrequests==2.28.0\n")

        packages = resolver.resolve(req_file)

        requests_pkgs = [p for p in packages if p.name == "requests"]
        assert len(requests_pkgs) == 1
        # Should prefer the one with version
        assert requests_pkgs[0].version == "2.28.0"

    def test_resolve_merges_extras(self, resolver, tmp_path):
        """Test that extras are merged for duplicate packages."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests[security]\nrequests[socks]\n")

        packages = resolver.resolve(req_file)

        requests_pkgs = [p for p in packages if p.name == "requests"]
        assert len(requests_pkgs) == 1
        assert "security" in requests_pkgs[0].extras
        assert "socks" in requests_pkgs[0].extras

    def test_resolve_file_specific(self, resolver, tmp_requirements_txt):
        """Test resolve_file method."""
        packages = resolver.resolve_file(tmp_requirements_txt)

        assert len(packages) >= 3

    def test_resolve_file_unsupported(self, resolver, tmp_path):
        """Test that unsupported files raise error."""
        unknown_file = tmp_path / "unknown.xyz"
        unknown_file.write_text("something")

        with pytest.raises(ParsingError):
            resolver.resolve_file(unknown_file)

    def test_find_dependency_files(self, resolver, tmp_project_dir):
        """Test finding dependency files in a directory."""
        files = resolver._find_dependency_files(tmp_project_dir)

        filenames = [f.name for f in files]
        assert "requirements.txt" in filenames
        assert "requirements-dev.txt" in filenames
        assert "pyproject.toml" in filenames

    def test_find_manifest_files_nested_subdirectory(self, resolver, tmp_path):
        """Manifests one or more levels below project_path are still found.

        Regression test: many real-world repos keep requirements.txt in a
        subdirectory (e.g. python/requirements.txt) rather than at the repo
        root, and resolve() previously returned an empty result for them.
        """
        nested_dir = tmp_path / "python"
        nested_dir.mkdir()
        (nested_dir / "requirements.txt").write_text("requests>=2.28.0\n")

        files = resolver._find_manifest_files(tmp_path)

        assert (nested_dir / "requirements.txt") in files

        packages = resolver.resolve(tmp_path)
        assert any(p.name == "requests" for p in packages)

    def test_find_manifest_files_skips_vendor_dirs(self, resolver, tmp_path):
        """Vendored/virtualenv/VCS directories are not searched."""
        for ignored in (".git", "node_modules", ".venv", "site-packages"):
            d = tmp_path / ignored
            d.mkdir()
            (d / "requirements.txt").write_text("should-not-be-found\n")

        files = resolver._find_manifest_files(tmp_path)

        assert files == []

    def test_find_manifest_files_respects_max_depth(self, resolver, tmp_path):
        """Manifests beyond MAX_SCAN_DEPTH levels deep are not found."""
        deep_dir = tmp_path
        for i in range(resolver.MAX_SCAN_DEPTH + 2):
            deep_dir = deep_dir / f"level{i}"
        deep_dir.mkdir(parents=True)
        (deep_dir / "requirements.txt").write_text("too-deep\n")

        files = resolver._find_manifest_files(tmp_path)

        assert files == []
