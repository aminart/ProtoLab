"""Turns the Mermaid flow into the structure of the app: modules, screens and navigation.

Decisions and system actions are not screens: a link goes from a screen to the next screens,
through them, and keeps their labels (the decision's answer becomes a condition).
"""
from __future__ import annotations

from typing import Any

from mermaid_reader import MermaidGraph

OTHER_MODULE = {"id": "_autres", "title": "Autres écrans"}


def _module_title(graph: MermaidGraph, sub_id: str | None) -> tuple[str, str]:
    if not sub_id or sub_id not in graph.subgraphs:
        return OTHER_MODULE["id"], OTHER_MODULE["title"]
    titles, current = [], sub_id
    while current and current in graph.subgraphs:
        titles.append(graph.subgraphs[current]["title"])
        current = graph.subgraphs[current]["parent"]
    return sub_id, " / ".join(reversed(titles))


def _outgoing(graph: MermaidGraph) -> dict[str, list[dict[str, Any]]]:
    edges: dict[str, list[dict[str, Any]]] = {}
    for edge in graph.edges:
        edges.setdefault(edge["source"], []).append(edge)
        if edge.get("bidirectional"):
            edges.setdefault(edge["target"], []).append({**edge, "source": edge["target"], "target": edge["source"]})
    return edges


def _links_from(graph: MermaidGraph, outgoing: dict[str, list[dict[str, Any]]], screen_id: str) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []

    def walk(node_id: str, trigger: str, conditions: list[dict[str, str]], via: list[str], seen: set[str]) -> None:
        for edge in outgoing.get(node_id, []):
            target = graph.nodes.get(edge["target"])
            if target is None or target.id in seen:
                continue
            node = graph.nodes[node_id]
            label = edge["label"]
            next_conditions = conditions + ([{"decision": node.label, "answer": label}] if node.kind == "decision" else [])
            next_trigger = trigger or (label if node.kind != "decision" else "")
            if target.kind == "screen":
                links.append({"target": target.id, "label": next_trigger, "conditions": next_conditions, "via": via})
            elif target.kind != "terminal":
                walk(target.id, next_trigger, next_conditions, via + ([target.label] if target.kind == "action" else []), seen | {target.id})

    walk(screen_id, "", [], [], {screen_id})
    unique: dict[tuple, dict[str, Any]] = {}
    for link in links:
        key = (link["target"], link["label"], tuple((c["decision"], c["answer"]) for c in link["conditions"]))
        unique.setdefault(key, link)
    return list(unique.values())


def build_structure(graph: MermaidGraph) -> dict[str, Any]:
    outgoing = _outgoing(graph)
    screens = [node for node in graph.nodes.values() if node.kind == "screen"]
    modules: dict[str, dict[str, Any]] = {}
    result_screens = []
    for node in screens:
        module_id, module_title = _module_title(graph, node.subgraph)
        modules.setdefault(module_id, {"id": module_id, "title": module_title, "screens": []})["screens"].append(node.id)
        result_screens.append({"id": node.id, "name": node.label, "module": module_id, "links": _links_from(graph, outgoing, node.id)})

    incoming = {link["target"] for screen in result_screens for link in screen["links"]}
    start = None
    for node in graph.nodes.values():
        if node.kind == "terminal" and not any(edge["target"] == node.id for edge in graph.edges):
            reachable = _links_from(graph, outgoing, node.id)
            if reachable:
                start = reachable[0]["target"]
                break
    if start is None:
        start = next((screen["id"] for screen in result_screens if screen["id"] not in incoming), None)
    if start is None and result_screens:
        start = result_screens[0]["id"]

    ordered_modules = sorted(modules.values(), key=lambda module: module["id"] == OTHER_MODULE["id"])
    return {
        "screens": result_screens,
        "modules": ordered_modules,
        "start": start,
        "decisions": [node.label for node in graph.nodes.values() if node.kind == "decision"],
        "actions": [node.label for node in graph.nodes.values() if node.kind == "action"],
    }
