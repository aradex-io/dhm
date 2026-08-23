"""CLI usage-simulation for DHM 0.4.0 capabilities (offline).

Stubs only the network layer (``ReportGenerator.generate_reports``) so the real
resolver, lockfile parsing, transitive expansion, formatters, and CLI flag
wiring are all exercised end-to-end without hitting PyPI/OSV/GitHub.
"""

import json

import pytest
from click.testing import CliRunner

from dhm.cli.main import cli
from dhm.core.models import DependencyReport, HealthGrade, HealthScore
from dhm.reports.generator import ReportGenerator

POETRY_LOCK = """\
[[package]]
name = "requests"
version = "2.31.0"

[[package]]
name = "urllib3"
version = "2.0.7"
"""


@pytest.fixture
def captured(monkeypatch):
    """Stub generate_reports; record the packages it receives, return synthetic reports."""
    seen: dict = {"packages": None}

    async def fake_generate_reports(self, packages):
        seen["packages"] = list(packages)
        return [
            DependencyReport(
                package=p,
                health=HealthScore(overall=90.0, grade=HealthGrade.A),
                is_direct=p.is_direct,
            )
            for p in packages
        ]

    monkeypatch.setattr(ReportGenerator, "generate_reports", fake_generate_reports)
    return seen


@pytest.fixture
def project(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "1"\ndependencies = ["requests>=2.0"]\n'
    )
    (tmp_path / "poetry.lock").write_text(POETRY_LOCK)
    return tmp_path


def test_scan_direct_only(captured, project):
    result = CliRunner().invoke(cli, ["scan", str(project), "-f", "json"])
    assert result.exit_code == 0
    names = {p.normalized_name for p in captured["packages"]}
    assert names == {"requests"}


def test_scan_include_transitive(captured, project):
    result = CliRunner().invoke(cli, ["scan", str(project), "--include-transitive", "-f", "json"])
    assert result.exit_code == 0
    names = {p.normalized_name for p in captured["packages"]}
    assert names == {"requests", "urllib3"}
    by_name = {p.normalized_name: p for p in captured["packages"]}
    assert by_name["urllib3"].is_direct is False


def test_scan_cyclonedx_output(captured, project):
    # mix_stderr=False so the Rich progress spinner (stderr) doesn't corrupt the
    # JSON on stdout.
    result = CliRunner(mix_stderr=False).invoke(
        cli, ["scan", str(project), "--include-transitive", "-f", "cyclonedx"]
    )
    assert result.exit_code == 0
    bom = json.loads(result.stdout)
    assert bom["bomFormat"] == "CycloneDX"
    comp_names = {c["name"] for c in bom["components"]}
    assert comp_names == {"requests", "urllib3"}


def test_scan_installed(captured):
    result = CliRunner().invoke(cli, ["scan", "--installed", "-f", "json"])
    assert result.exit_code == 0
    names = {p.normalized_name for p in captured["packages"]}
    # DHM's own runtime deps are installed in the test env.
    assert "packaging" in names
    assert "click" in names


def test_scan_cyclonedx_to_file(captured, project, tmp_path):
    out = tmp_path / "sbom.json"
    result = CliRunner().invoke(
        cli, ["scan", str(project), "-f", "cyclonedx", "-o", str(out)]
    )
    assert result.exit_code == 0
    assert out.exists()
    bom = json.loads(out.read_text())
    assert bom["bomFormat"] == "CycloneDX"
