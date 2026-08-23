"""Installed-environment introspection for real-world dependency health.

Reads the *currently installed* distributions (via ``importlib.metadata``) so
DHM can report on what is actually present rather than the latest PyPI release,
and builds the requirement graph used to compute the transitive closure of a
project's direct dependencies.
"""

from __future__ import annotations

import importlib.metadata as importlib_metadata
import re

from packaging.requirements import InvalidRequirement, Requirement

__all__ = [
    "normalize_name",
    "installed_versions",
    "installed_requires_graph",
    "transitive_closure",
]


def normalize_name(name: str) -> str:
    """Return the PEP 503 normalized distribution name (lowercase, ``-`` joined)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def installed_versions() -> dict[str, str]:
    """Map normalized distribution name -> installed version for this environment."""
    result: dict[str, str] = {}
    for dist in importlib_metadata.distributions():
        try:
            name = dist.metadata["Name"]
        except Exception:
            name = None
        if not name:
            continue
        # Multiple dists with the same name can appear (e.g. shadowed installs);
        # keep the first seen, matching import resolution order.
        result.setdefault(normalize_name(name), dist.version)
    return result


def installed_requires_graph() -> dict[str, set[str]]:
    """Build the runtime requirement graph of installed distributions.

    Returns a mapping of normalized name -> set of normalized names it requires.
    Dependencies gated by an environment marker that is false in this
    environment (e.g. ``extra == "dev"`` or a non-matching ``python_version``)
    are excluded, so the graph reflects the runtime closure.
    """
    graph: dict[str, set[str]] = {}
    for dist in importlib_metadata.distributions():
        try:
            name = dist.metadata["Name"]
        except Exception:
            name = None
        if not name:
            continue

        deps: set[str] = set()
        for req_str in dist.requires or []:
            try:
                req = Requirement(req_str)
            except InvalidRequirement:
                continue
            # Skip deps whose marker is false in this environment (extras, other
            # python versions/platforms). No-marker deps are always included.
            if req.marker is not None and not req.marker.evaluate():
                continue
            deps.add(normalize_name(req.name))

        # setdefault so the first (import-order) dist wins on name collisions.
        graph.setdefault(normalize_name(name), deps)
    return graph


def transitive_closure(roots: set[str], graph: dict[str, set[str]]) -> set[str]:
    """Return all names reachable from *roots* via *graph*, excluding the roots.

    Cycles are handled. Names in ``roots`` are only present in the result if they
    are reachable from another root (i.e. part of a cycle).
    """
    seen: set[str] = set()
    stack: list[str] = [dep for root in roots for dep in graph.get(root, set())]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        for dep in graph.get(node, set()):
            if dep not in seen:
                stack.append(dep)
    return seen
