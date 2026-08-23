"""Regression tests for the 0.3.1 follow-up fixes (reconciled onto 0.3.0, 22AUG2026).

Covers findings from the code review that were still open in 0.3.0:
- B1: cache.set() raises CacheError (not a masking AttributeError) on bad values
- B3: open/fixed classification honors the OSV introduced lower bound
- B4: CVSS vector is computed to a base score (score + severity paths)
- I7: whole-token SPDX license matching (no substring false positives)
- I9: packaging-based pinned-version extraction
"""

import pytest

from dhm.cache.sqlite import CacheLayer
from dhm.collectors.vulnerability import (
    OSVClient,
    _compute_is_fixed,
    _extract_cvss_base_score,
    _is_version_affected,
)
from dhm.core.calculator import HealthCalculator
from dhm.core.exceptions import CacheError
from dhm.core.models import PyPIMetadata, RiskLevel
from dhm.core.resolver import _extract_pinned_version

# --- B1: cache error handling ------------------------------------------------

def test_cache_set_non_serializable_raises_cache_error(tmp_path):
    cache = CacheLayer(db_path=tmp_path / "c.db")
    with pytest.raises(CacheError):
        cache.set("bad", {"obj": object()})


def test_cache_set_circular_raises_cache_error(tmp_path):
    cache = CacheLayer(db_path=tmp_path / "c.db")
    circular: dict = {}
    circular["self"] = circular
    with pytest.raises(CacheError):
        cache.set("circular", circular)


# --- B3: introduced-bound range membership -----------------------------------

def test_version_below_introduced_not_affected():
    assert _is_version_affected("1.0.0", ">=2.0.0,<2.5.0") is False


def test_version_in_range_affected():
    assert _is_version_affected("2.3.0", ">=2.0.0,<2.5.0") is True


def test_wildcard_is_unknown():
    assert _is_version_affected("2.3.0", "*") is None


def test_compute_is_fixed_below_introduced_reports_fixed():
    assert _compute_is_fixed("1.0.0", ">=2.0.0,<2.5.0", "2.5.0") is True


def test_compute_is_fixed_in_range_reports_open():
    assert _compute_is_fixed("2.3.0", ">=2.0.0,<2.5.0", "2.5.0") is False


# --- B4: CVSS vector computation ---------------------------------------------

@pytest.mark.parametrize(
    "vector,expected",
    [
        ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", 9.8),
        ("CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N", 6.1),
        ("7.5", 7.5),
    ],
)
def test_extract_cvss_base_score(vector, expected):
    assert _extract_cvss_base_score(vector) == pytest.approx(expected)


def test_extract_cvss_unparseable_none():
    assert _extract_cvss_base_score("") is None
    assert _extract_cvss_base_score("AV:N/AC:L/Au:N") is None  # v2 unsupported


def test_parse_severity_from_vector_only():
    """Severity is derived from the CVSS vector even without a severity-text field."""
    client = OSVClient()
    data = {
        "severity": [
            {"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}
        ]
    }
    assert client._parse_severity(data) == RiskLevel.CRITICAL


# --- I7: license whole-token SPDX --------------------------------------------

def _license(text):
    calc = HealthCalculator()
    return calc._calculate_license_score(
        PyPIMetadata(name="x", version="1", summary="", author="", license=text), None
    )


def test_license_permissive_and_copyleft():
    assert _license("MIT License") == 100.0
    assert _license("Apache-2.0") == 100.0
    assert _license("LGPL-3.0") == 75.0
    assert _license("GPL-3.0") == 60.0


def test_license_verbose_blob_no_false_match():
    assert _license("THIS SOFTWARE IS PROVIDED AS IS; DISCLAIMER OF WARRANTIES") == 50.0


# --- I9: pinned version extraction -------------------------------------------

@pytest.mark.parametrize(
    "spec,expected",
    [
        ("==1.0.0rc1", "1.0.0rc1"),
        ("==1.2.*", "1.2"),
        (">=2.0", None),
        ("~=1.4", None),
    ],
)
def test_extract_pinned_version(spec, expected):
    assert _extract_pinned_version(spec) == expected
