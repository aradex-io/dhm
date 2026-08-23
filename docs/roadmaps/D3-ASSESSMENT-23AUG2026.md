# DHM — D3 Feature Sprint Assessment (23AUG2026)

Assessment of the D3 capability-expansion items (none started). Effort key:
**S** ≈ hours, **M** ≈ half day, **L** ≈ day+. Baseline: released 0.3.1.

| ID | Item | Value | Effort | Deps/Risk | Tier |
|----|------|-------|--------|-----------|------|
| F1 | Scan installed env + lockfiles | **High** | M–L | parsing only | **1 (do first)** |
| F2 | Transitive dependency graph | **High** | L | pairs with F1 | **1** |
| F6 | SBOM ingest/emit (CycloneDX/SPDX) | Med–High | M | stable spec | **2** |
| F5 | Code-quality signals → weighted score | Med | M–L | signal reliability; recalibration | 3 (partial) |
| F3 | Extra CVE sources (GHSA/PyPA) | Low–Med | M | largely redundant with OSV | 4 |
| F4 | Data-driven alternatives | Low | M | no good "similar package" signal | 5 |

## Details

### F1 — installed-environment + lockfile scanning  ★ #1 gap
Today `scan` evaluates the **latest** PyPI version when a requirement is
unpinned, not what is actually installed/locked. Add:
- `importlib.metadata` scanner ("scan my current venv") — **S**.
- Lockfile parsers: `poetry.lock`, `uv.lock` (TOML), `Pipfile.lock` (JSON),
  hashed `requirements.txt` — **S–M** each; the versions are already pinned so no
  resolution is needed.
Low risk, highest value/effort ratio — this is the review's headline capability gap.

### F2 — transitive dependency graph
Delivers the currently-inert `[tool.dhm] include_transitive` and the always-True
`is_direct` field. Building a general PyPI resolver is hard, but reading the
**already-resolved** graph from a lockfile or the installed environment
(`Requires-Dist` / metadata) is tractable and accurate. Tag `is_direct`
accordingly. Best done right after F1 (shares the env/lockfile plumbing).

### F6 — SBOM ingest/emit (CycloneDX / SPDX)
- **Emit**: produce a CycloneDX JSON from a scan (components + vulns) — the data
  already exists in `DependencyReport`. Straightforward.
- **Ingest**: read an SBOM's component list as scan input (a new resolver source)
  — pairs naturally with F1/F2.
Compliance value is rising; format is stable; hand-rollable JSON or an optional
`cyclonedx-python-lib` extra. Self-contained and testable.

### F5 — code-quality signals
The quality score is computed but excluded from the weighted total. Easy wins:
`py.typed` marker detection, presence of a CI workflow. Hard: real test-coverage
(_no reliable source_). Folding quality into the weighted score changes every
grade, so it needs recalibration and a CHANGELOG note. **Recommend the easy
signals + keeping quality informational until coverage is solvable.**

### F3 — extra CVE sources (GHSA / PyPA)
**OSV already aggregates GitHub Security Advisories and the PyPA Advisory DB**, so
adding them directly is mostly redundant; the CVSS-accuracy motivation was already
addressed in 0.3.1 (vector base-score computation). Low marginal value — defer
unless a concrete coverage gap surfaces.

### F4 — data-driven alternatives
Expanding the 160-line curated map via PyPI classifier/keyword similarity is
noisy (PyPI has no real "similar package" signal) and risks poor suggestions. The
curated map is adequate for now. Defer.

## Recommended DHM next release (0.4.0)
**F1 (installed env + lockfiles) + F2 (transitive graph) + F6 (SBOM emit, then
ingest).** This closes the top capability gaps (real installed-state accuracy,
transitive risk, SBOM interop). Do the easy slice of F5 (`py.typed`/CI presence)
opportunistically. Defer F3 (OSV-redundant) and F4 (weak signal).

---

## Delivered in 0.4.0 (23AUG2026)

- **F1** ✅ installed-env scanning (`--installed`, `scan_installed`) + lockfile
  parsers (`poetry.lock`, `uv.lock`, `Pipfile.lock`) + hashed requirements.
- **F2** ✅ transitive graph (`--include-transitive`); `is_direct` now set from
  the lockfile-vs-manifest cross-reference or the installed-env requirement graph.
- **F6** ✅ CycloneDX 1.5 SBOM emit (`-f cyclonedx`), no new runtime dependency.
- **Bug found via usage simulation & fixed:** `Collector._get_json` used
  `StreamReader.read(n)`, which returned partial bodies across TCP chunks →
  intermittent truncated-JSON errors. Now reassembles the full body with the
  size cap enforced while streaming.

Verification: 174 tests (was 149), `ruff` clean, mypy not regressed, plus a live
end-to-end simulation (lockfile version honored, transitive expansion, SBOM,
CVSS-from-vector, 429 retry) and edge cases (malformed lock, empty project,
vcs lock entries, markdown regression).

**Still deferred:** F5 (quality signals — partial/easy wins only), F3 (extra CVE
sources — OSV-redundant), F4 (data-driven alternatives — weak signal).
