"""Tests for DHM 0.4.0 capabilities (23AUG2026).

- F1: installed-environment + lockfile scanning
- F2: transitive dependency graph + is_direct marking
- F6: CycloneDX SBOM emit
"""

import json

import pytest

from dhm.core.environment import (
    installed_requires_graph,
    installed_versions,
    normalize_name,
    transitive_closure,
)
from dhm.core.models import (
    DependencyReport,
    HealthGrade,
    HealthScore,
    PackageIdentifier,
    RiskLevel,
    Vulnerability,
)
from dhm.core.resolver import (
    DependencyResolver,
    PipfileLockSource,
    PoetryLockSource,
    UvLockSource,
)
from dhm.reports.formatters import CycloneDXFormatter

# ===========================================================================
# environment.py
# ===========================================================================

def test_normalize_name():
    assert normalize_name("Foo_Bar.Baz") == "foo-bar-baz"
    assert normalize_name("requests") == "requests"
    assert normalize_name("ruamel.yaml") == "ruamel-yaml"


def test_transitive_closure_basic():
    graph = {"a": {"b", "c"}, "b": {"d"}, "c": set(), "d": set()}
    assert transitive_closure({"a"}, graph) == {"b", "c", "d"}


def test_transitive_closure_handles_cycles():
    graph = {"a": {"b"}, "b": {"a"}}  # cycle
    result = transitive_closure({"a"}, graph)
    assert result == {"a", "b"}  # a is reachable from b (cycle)


def test_transitive_closure_excludes_unreachable():
    graph = {"a": {"b"}, "b": set(), "z": {"y"}, "y": set()}
    assert transitive_closure({"a"}, graph) == {"b"}


def test_installed_versions_and_graph_smoke():
    versions = installed_versions()
    graph = installed_requires_graph()
    # DHM depends on these, so they must be installed in the test env.
    assert "packaging" in versions
    assert "click" in versions
    assert isinstance(versions["packaging"], str)
    assert isinstance(graph.get("dependency-health-monitor", set()), set)


# ===========================================================================
# Lockfile sources
# ===========================================================================

POETRY_LOCK = """\
[[package]]
name = "requests"
version = "2.31.0"
category = "main"
optional = false

[[package]]
name = "urllib3"
version = "2.0.7"
category = "main"
optional = false
"""

UV_LOCK = """\
[[package]]
name = "flask"
version = "3.0.0"

[[package]]
name = "werkzeug"
version = "3.0.1"
"""

PIPFILE_LOCK = """\
{
  "_meta": {"hash": {"sha256": "x"}},
  "default": {
    "django": {"version": "==4.2.7"},
    "asgiref": {"version": "==3.7.2"}
  },
  "develop": {
    "pytest": {"version": "==7.4.3"}
  }
}
"""


def test_poetry_lock_source(tmp_path):
    p = tmp_path / "poetry.lock"
    p.write_text(POETRY_LOCK)
    src = PoetryLockSource()
    assert src.can_parse(p)
    pkgs = {pk.normalized_name: pk.version for pk in src.parse(p)}
    assert pkgs == {"requests": "2.31.0", "urllib3": "2.0.7"}


def test_uv_lock_source(tmp_path):
    p = tmp_path / "uv.lock"
    p.write_text(UV_LOCK)
    src = UvLockSource()
    assert src.can_parse(p)
    pkgs = {pk.normalized_name: pk.version for pk in src.parse(p)}
    assert pkgs == {"flask": "3.0.0", "werkzeug": "3.0.1"}


def test_pipfile_lock_source(tmp_path):
    p = tmp_path / "Pipfile.lock"
    p.write_text(PIPFILE_LOCK)
    src = PipfileLockSource()
    assert src.can_parse(p)
    pkgs = {pk.normalized_name: pk.version for pk in src.parse(p)}
    assert pkgs == {"django": "4.2.7", "asgiref": "3.7.2", "pytest": "7.4.3"}


# ===========================================================================
# Resolver: direct vs transitive, lockfiles, hashed requirements
# ===========================================================================

def test_resolve_lockfile_marks_direct_vs_transitive(tmp_path):
    # pyproject declares only requests; poetry.lock adds urllib3 (transitive).
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "1"\ndependencies = ["requests>=2.0"]\n'
    )
    (tmp_path / "poetry.lock").write_text(POETRY_LOCK)
    resolver = DependencyResolver()

    # Default: direct only.
    direct = resolver.resolve(tmp_path)
    names = {p.normalized_name for p in direct}
    assert names == {"requests"}
    assert all(p.is_direct for p in direct)

    # include_transitive: both, with correct is_direct flags + locked versions.
    full = resolver.resolve(tmp_path, include_transitive=True)
    by_name = {p.normalized_name: p for p in full}
    assert set(by_name) == {"requests", "urllib3"}
    assert by_name["requests"].is_direct is True
    assert by_name["urllib3"].is_direct is False
    assert by_name["requests"].version == "2.31.0"  # from lockfile, not spec


def test_resolve_manifest_only_all_direct(tmp_path):
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\nflask==3.0.0\n")
    resolver = DependencyResolver()
    pkgs = resolver.resolve(tmp_path)
    assert {p.normalized_name for p in pkgs} == {"requests", "flask"}
    assert all(p.is_direct for p in pkgs)


def test_resolve_hashed_requirements(tmp_path):
    (tmp_path / "requirements.txt").write_text(
        "requests==2.31.0 \\\n"
        "    --hash=sha256:aaaa \\\n"
        "    --hash=sha256:bbbb\n"
    )
    resolver = DependencyResolver()
    pkgs = resolver.resolve(tmp_path)
    assert len(pkgs) == 1
    assert pkgs[0].normalized_name == "requests"
    assert pkgs[0].version == "2.31.0"  # backslash continuation stripped


def test_resolve_transitive_from_installed_graph(tmp_path):
    # No lockfile -> transitive expansion uses the installed-env requirement graph.
    # aiohttp is a DHM runtime dependency, so it and its deps are installed here.
    (tmp_path / "requirements.txt").write_text("aiohttp\n")
    resolver = DependencyResolver()

    direct = resolver.resolve(tmp_path)
    assert {p.normalized_name for p in direct} == {"aiohttp"}

    full = resolver.resolve(tmp_path, include_transitive=True)
    by_name = {p.normalized_name: p for p in full}
    assert by_name["aiohttp"].is_direct is True
    # multidict is an unconditional aiohttp runtime dependency.
    assert "multidict" in by_name
    assert by_name["multidict"].is_direct is False
    assert by_name["multidict"].version is not None  # version from installed env


def test_resolve_installed_returns_real_versions():
    resolver = DependencyResolver()
    pkgs = resolver.resolve_installed()
    by_name = {p.normalized_name: p for p in pkgs}
    assert "packaging" in by_name
    assert by_name["packaging"].version is not None
    assert all(p.is_direct for p in pkgs)


def test_resolve_single_lockfile_file(tmp_path):
    p = tmp_path / "poetry.lock"
    p.write_text(POETRY_LOCK)
    resolver = DependencyResolver()
    pkgs = resolver.resolve(p)
    assert {pk.normalized_name for pk in pkgs} == {"requests", "urllib3"}


# ===========================================================================
# CycloneDX SBOM
# ===========================================================================

def _report(name, version, grade=HealthGrade.A, direct=True, vulns=None):
    return DependencyReport(
        package=PackageIdentifier(name=name, version=version, is_direct=direct),
        health=HealthScore(
            overall=90.0,
            grade=grade,
            vulnerabilities=vulns or [],
        ),
        is_direct=direct,
    )


def test_cyclonedx_basic_structure():
    reports = [_report("requests", "2.31.0"), _report("urllib3", "2.0.7", direct=False)]
    bom = json.loads(CycloneDXFormatter().format(reports))

    assert bom["bomFormat"] == "CycloneDX"
    assert bom["specVersion"] == "1.5"
    assert len(bom["components"]) == 2

    comp = {c["name"]: c for c in bom["components"]}
    assert comp["requests"]["purl"] == "pkg:pypi/requests@2.31.0"
    assert comp["requests"]["version"] == "2.31.0"
    props = {p["name"]: p["value"] for p in comp["urllib3"]["properties"]}
    assert props["dhm:direct"] == "false"
    assert props["dhm:health:grade"] == "A"


def test_cyclonedx_open_vulnerabilities_emitted():
    open_vuln = Vulnerability(
        id="CVE-2024-1",
        severity=RiskLevel.HIGH,
        title="bad",
        description="",
        affected_versions="*",
        fixed_version="2.0.0",
        cvss_score=7.5,
        is_fixed_in_installed_version=False,  # open
    )
    fixed_vuln = Vulnerability(
        id="CVE-2023-9",
        severity=RiskLevel.LOW,
        title="old",
        description="",
        affected_versions="*",
        fixed_version="1.0.0",
        is_fixed_in_installed_version=True,  # fixed -> excluded
    )
    reports = [_report("requests", "1.5.0", vulns=[open_vuln, fixed_vuln])]
    bom = json.loads(CycloneDXFormatter().format(reports))

    assert "vulnerabilities" in bom
    ids = [v["id"] for v in bom["vulnerabilities"]]
    assert ids == ["CVE-2024-1"]  # only the open one
    v = bom["vulnerabilities"][0]
    assert v["affects"][0]["ref"] == "pkg:pypi/requests@1.5.0"
    assert v["ratings"][0]["severity"] == "high"
    assert v["ratings"][0]["score"] == 7.5


def test_cyclonedx_no_vulns_omits_key():
    bom = json.loads(CycloneDXFormatter().format([_report("requests", "2.31.0")]))
    assert "vulnerabilities" not in bom


def test_cyclonedx_missing_version_purl():
    bom = json.loads(CycloneDXFormatter().format([_report("mystery", None)]))
    comp = bom["components"][0]
    assert comp["purl"] == "pkg:pypi/mystery"
    assert "version" not in comp


# ===========================================================================
# _get_json: full body reassembly across chunks (truncation-bug regression)
# ===========================================================================

from dhm.collectors.base import Collector  # noqa: E402
from dhm.core.exceptions import ValidationError  # noqa: E402


class _FakeContent:
    def __init__(self, chunks):
        self._chunks = chunks

    async def iter_chunked(self, _n):
        for c in self._chunks:
            yield c


class _FakeResp:
    def __init__(self, chunks, status=200, headers=None):
        self.status = status
        self.headers = headers or {}
        self.content = _FakeContent(chunks)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _FakeSession:
    def __init__(self, resp):
        self._resp = resp

    def get(self, url, headers=None):
        return self._resp


class _DummyCollector(Collector):
    async def fetch(self, identifier):  # pragma: no cover
        return None


async def test_get_json_reassembles_multichunk_body():
    """A JSON body split across chunks must be fully reassembled (not truncated)."""
    resp = _FakeResp([b'{"a": "hel', b'lo", "b":', b" 123}"])
    coll = _DummyCollector()
    coll._session = _FakeSession(resp)
    status, data = await coll._get_json("https://example/api")
    assert status == 200
    assert data == {"a": "hello", "b": 123}


async def test_get_json_rejects_oversized_body():
    resp = _FakeResp([b"x" * 8, b"y" * 8])  # 16 bytes, no Content-Length
    coll = _DummyCollector()
    coll.MAX_RESPONSE_SIZE = 10
    coll._session = _FakeSession(resp)
    with pytest.raises(ValidationError):
        await coll._get_json("https://example/api")
