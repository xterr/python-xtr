"""The root README's dependency graph is what the manifests declare.

The graph is drawn by hand and the manifests are the truth, so every solid edge in it
is a runtime dependency a package declares on a sibling, and every such dependency is
an edge. A package added, or a dependency taken on or dropped, then shows up here
rather than in a reader's out-of-date mental model. The dotted edges are extras: the
graph names the ones worth knowing about rather than all of them, so they are left out
of the comparison - the solid edges are the claim this checks.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_README = _ROOT / "README.md"

_GRAPH = re.compile(r"```mermaid\ngraph LR\n(?P<body>.*?)\n```", re.DOTALL)
_NODE = re.compile(r"(?P<id>\w+)\[(?P<name>xtr-[a-z-]+)\]")
_EDGE = re.compile(r"^\s*(?P<tail>\w+)(?:\[[^\]]*\])?\s*-->\s*(?P<head>\w+)(?:\[[^\]]*\])?\s*$")


def _graph() -> str:
    """Return the body of the README's dependency graph."""
    found = _GRAPH.search(_README.read_text(encoding="utf-8"))
    assert found is not None, "README.md has no mermaid graph"
    return found.group("body")


def _nodes() -> dict[str, str]:
    """Return each node id of the graph mapped to the distribution it is labelled with."""
    return {matched.group("id"): matched.group("name") for matched in _NODE.finditer(_graph())}


def _drawn() -> set[tuple[str, str]]:
    """Return every solid edge of the graph, as a pair of distribution names."""
    nodes = _nodes()
    drawn: set[tuple[str, str]] = set()
    for line in _graph().splitlines():
        edge = _EDGE.match(line)
        if edge is None:
            continue
        tail, head = edge.group("tail"), edge.group("head")
        assert tail in nodes, f"{tail} is never labelled with a package"
        assert head in nodes, f"{head} is never labelled with a package"
        drawn.add((nodes[tail], nodes[head]))
    return drawn


def _declared() -> set[tuple[str, str]]:
    """Return every runtime dependency a package declares on a sibling."""
    manifests = {
        pyproject: tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
        for pyproject in sorted(_ROOT.glob("packages/*/pyproject.toml"))
    }
    siblings = {project["name"] for project in manifests.values()}
    return {
        (project["name"], requirement.split(">", 1)[0].split("[", 1)[0].strip())
        for project in manifests.values()
        for requirement in project.get("dependencies", [])
        if requirement.split(">", 1)[0].split("[", 1)[0].strip() in siblings
    }


def test_the_graph_is_found() -> None:
    assert _drawn()
    assert _declared()


def test_every_solid_edge_is_a_runtime_dependency() -> None:
    invented = sorted(f"{tail} --> {head}" for tail, head in _drawn() - _declared())

    assert invented == [], "the graph draws what no manifest declares"


def test_every_runtime_dependency_is_drawn() -> None:
    undrawn = sorted(f"{tail} --> {head}" for tail, head in _declared() - _drawn())

    assert undrawn == [], "the graph is missing a runtime dependency"


def test_every_package_is_a_node() -> None:
    packages = {path.name for path in sorted(_ROOT.glob("packages/xtr-*")) if path.is_dir()}

    missing = sorted(packages - set(_nodes().values()))

    assert missing == [], "the graph has no node for these packages"
