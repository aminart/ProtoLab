"""Puts the sources of a project together: the structure from the Mermaid flow, the screens from
the Figma mockup, the specs, the libraries, and what the model added (data, behaviours).

The result is the prototype model, a JSON read by the player: the same model is shown in the
app, frozen as a version for the tests, and embedded in the HTML export.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from context_reader import ContextDocument, normalize, read_context
from figma_reader import Converter, FigmaError, Report, convert_screen, default_page_id, iter_nodes, list_pages, load_figma
from library_reader import inventory, theme_from
from mermaid_reader import MermaidError, read_mermaid
from structure_builder import OTHER_MODULE, build_structure

MODEL_VERSION = 1
FIGMA_ONLY_MODULE = {"id": "_figma", "title": "Écrans Figma hors du flow"}
NAME_NOISE = re.compile(r"^(ecran|screen|page|vue|view|frame)\s+|\s+(v\d+|version \d+|copy|copie|final|ok)$")


def _key(text: str) -> str:
    key = normalize(text)
    key = re.sub(r"^\d+(\s+\d+)*\s+", "", key)  # "01 - Connexion", "2.1 Liste"
    previous = None
    while previous != key:
        previous, key = key, NAME_NOISE.sub("", key).strip()
    return key


def _similarity(a: str, b: str) -> int:
    if not a or not b:
        return 0
    if a == b:
        return 3
    if (len(a) >= 4 and a in b) or (len(b) >= 4 and b in a):
        return 2
    words_a, words_b = set(a.split()), set(b.split())
    if words_a and words_b and len(words_a & words_b) / len(words_a | words_b) >= 0.6:
        return 1
    return 0


def _match(left: list[tuple[str, list[str]]], right: list[tuple[str, list[str]]]) -> dict[str, str]:
    """Best one-to-one matches between two lists of (id, names)."""
    candidates = []
    for left_id, left_names in left:
        for right_id, right_names in right:
            score = max((_similarity(_key(a), _key(b)) for a in left_names for b in right_names), default=0)
            if score:
                candidates.append((score, left_id, right_id))
    matches: dict[str, str] = {}
    used: set[str] = set()
    for _, left_id, right_id in sorted(candidates, key=lambda item: -item[0]):
        if left_id not in matches and right_id not in used:
            matches[left_id] = right_id
            used.add(right_id)
    return matches


def spec_title(markdown: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", markdown, re.M)
    return match.group(1).strip() if match else fallback


@dataclass
class Assembly:
    context: ContextDocument | None = None
    structure: dict[str, Any] = field(default_factory=lambda: {"screens": [], "modules": [], "start": None, "decisions": [], "actions": []})
    mermaid_error: str | None = None
    pages: list[dict[str, Any]] = field(default_factory=list)
    page_id: str | None = None
    frames: dict[str, dict[str, Any]] = field(default_factory=dict)
    roots: dict[str, dict[str, Any]] = field(default_factory=dict)
    report: Report = field(default_factory=Report)
    local_component_keys: set[str] = field(default_factory=set)
    figma_error: str | None = None
    screens: list[dict[str, Any]] = field(default_factory=list)
    modules: list[dict[str, Any]] = field(default_factory=list)
    start: str | None = None
    warnings: list[dict[str, str]] = field(default_factory=list)
    inventory: dict[str, Any] = field(default_factory=dict)


def assemble(project: dict[str, Any], context_markdown: str | None, specs: dict[str, str], figma_payload: Any,
             global_library: dict[str, Any] | None) -> Assembly:
    result = Assembly()
    overrides = (project.get("overrides") or {}).get("screens") or {}

    # Structure: the Mermaid flow of the context document.
    if context_markdown:
        result.context = read_context(context_markdown)
        diagram = result.context.main_diagram()
        if diagram is None:
            result.mermaid_error = "Le document de contexte ne contient pas de diagramme Mermaid « flowchart »."
        else:
            try:
                graph = read_mermaid(diagram.code)
                result.structure = build_structure(graph)
                for warning in graph.warnings:
                    result.warnings.append({"level": "info", "message": f"Diagramme : {warning}"})
            except MermaidError as exc:
                result.mermaid_error = str(exc)

    # Screens of the mockup: the frames of the chosen page.
    if figma_payload is not None:
        try:
            figma = load_figma(figma_payload)
            result.pages = list_pages(figma)
            wanted = (project.get("figma") or {}).get("page_id")
            result.page_id = wanted if any(page["id"] == wanted for page in result.pages) else default_page_id(result.pages)
            page = next((page for page in result.pages if page["id"] == result.page_id), None)
            converter = Converter(figma, result.report)
            for frame in (page or {}).get("_frames", []):
                frame_id = str(frame.get("id"))
                info = next(item for item in page["frames"] if item["id"] == frame_id)
                result.frames[frame_id] = info
                result.roots[frame_id] = convert_screen(converter, frame)
            result.local_component_keys = {meta.get("key") for meta in figma.components.values() if meta.get("key") and not meta.get("remote")}
        except FigmaError as exc:
            result.figma_error = str(exc)

    # Frames ↔ screens of the flow: by name, unless the user chose.
    flow_screens = result.structure["screens"]
    automatic = _match(
        [(screen["id"], [screen["name"], screen["id"].replace("_", " ")]) for screen in flow_screens],
        [(frame_id, [frame["name"]]) for frame_id, frame in result.frames.items()],
    )
    spec_names = [(spec_id, [spec_title(markdown, spec_id)]) for spec_id, markdown in specs.items()]
    spec_meta = {spec["id"]: spec for spec in project.get("specs") or []}
    spec_names = [(spec_id, names + [spec_meta.get(spec_id, {}).get("name", "").rsplit(".", 1)[0]]) for spec_id, names in spec_names]
    automatic_specs = _match([(screen["id"], [screen["name"]]) for screen in flow_screens], spec_names)

    used_frames: set[str] = set()
    names = {screen["id"]: screen["name"] for screen in flow_screens}
    for screen in flow_screens:
        override = overrides.get(screen["id"]) or {}
        frame_id = override.get("frame") if override.get("frame") is not None else automatic.get(screen["id"])
        frame_id = frame_id if frame_id in result.frames else None
        if frame_id:
            used_frames.add(frame_id)
        spec_id = override.get("spec") if override.get("spec") is not None else automatic_specs.get(screen["id"])
        spec_id = spec_id if spec_id in specs else None
        result.screens.append({
            "id": screen["id"],
            "name": override.get("name") or screen["name"],
            "module": screen["module"],
            "frame": frame_id,
            "spec": spec_id,
            "kind": "figma" if frame_id else "deduced",
            "excluded": bool(override.get("excluded")),
            "links": [{**link, "target_name": names.get(link["target"], link["target"])} for link in screen["links"]],
        })
    result.modules = [dict(module) for module in result.structure["modules"]]

    # Frames that are not in the flow still become screens: the Figma links may lead to them.
    leftovers = [frame_id for frame_id in result.frames if frame_id not in used_frames]
    if leftovers:
        if flow_screens:
            result.modules.append({**FIGMA_ONLY_MODULE, "screens": []})
        else:
            result.modules.append({"id": OTHER_MODULE["id"], "title": "Écrans", "screens": []})
        module = result.modules[-1]
        frame_specs = _match([(frame_id, [result.frames[frame_id]["name"]]) for frame_id in leftovers], spec_names)
        for frame_id in leftovers:
            screen_id = f"figma_{frame_id.replace(':', '_').replace(';', '_')}"
            override = overrides.get(screen_id) or {}
            spec_id = override.get("spec") if override.get("spec") is not None else frame_specs.get(frame_id)
            module["screens"].append(screen_id)
            result.screens.append({
                "id": screen_id,
                "name": override.get("name") or result.frames[frame_id]["name"],
                "module": module["id"],
                "frame": frame_id,
                "spec": spec_id if spec_id in specs else None,
                "kind": "figma_only" if flow_screens else "figma",
                "excluded": bool(override.get("excluded")),
                "links": [],
            })

    start_override = (project.get("overrides") or {}).get("start")
    active = [screen for screen in result.screens if not screen["excluded"]]
    active_ids = {screen["id"] for screen in active}
    result.start = (
        start_override if start_override in active_ids else result.structure.get("start") if result.structure.get("start") in active_ids
        else (active[0]["id"] if active else None)
    )
    _coherence(result)
    result.inventory = inventory(result.report.as_dict()["instances"], project.get("library"), global_library, result.local_component_keys)
    if result.inventory["counts"]["missing"]:
        result.warnings.append({
            "level": "warning",
            "message": f"{result.inventory['counts']['missing']} composant(s) de la maquette introuvable(s) dans les bibliothèques importées : ils sont affichés tels que dans la maquette, sans leurs autres états.",
        })
    return result


def _frame_to_screen(result: Assembly) -> dict[str, str]:
    return {screen["frame"]: screen["id"] for screen in result.screens if screen["frame"] and not screen["excluded"]}


def _coherence(result: Assembly) -> None:
    """Gaps between the flow and the mockup, shown before generating."""
    deduced = [screen["name"] for screen in result.screens if screen["kind"] == "deduced" and not screen["excluded"]]
    if deduced:
        result.warnings.append({"level": "info", "message": f"Sans maquette, générés en version simple : {', '.join(deduced)}."})
    outside = [screen["name"] for screen in result.screens if screen["kind"] == "figma_only" and not screen["excluded"]]
    if outside:
        result.warnings.append({"level": "warning", "message": f"Frames Figma absentes du diagramme : {', '.join(outside)}. Rattachez-les à un écran ou excluez-les."})
    frame_to_screen = _frame_to_screen(result)
    flow_links = {(screen["id"], link["target"]) for screen in result.screens for link in screen["links"]}
    names = {screen["id"]: screen["name"] for screen in result.screens}
    reported: set[tuple[str, str]] = set()
    for screen in result.screens:
        root = result.roots.get(screen["frame"] or "")
        if not root or screen["kind"] == "figma_only":
            continue
        for node in iter_nodes(root):
            nav = node.get("nav") or {}
            if nav.get("kind") != "navigate":
                continue
            target = frame_to_screen.get(nav.get("frame"))
            if target is None:
                if (screen["id"], nav.get("frame")) not in reported:
                    reported.add((screen["id"], nav.get("frame")))
                    result.warnings.append({"level": "warning", "message": f"« {screen['name']} » : un lien Figma mène à une frame hors de la page importée (ignoré)."})
            elif flow_links and (screen["id"], target) not in flow_links and target != screen["id"] and (screen["id"], target) not in reported:
                reported.add((screen["id"], target))
                result.warnings.append({"level": "info", "message": f"Lien Figma « {screen['name']} » → « {names.get(target)} » absent du diagramme."})
    by_screen: dict[str, int] = {}
    for zone in result.report.absolute_zones:
        by_screen[zone["screen"]] = by_screen.get(zone["screen"], 0) + 1
    for screen_name, count in by_screen.items():
        result.warnings.append({"level": "warning", "message": f"« {screen_name} » : {count} zone(s) sans auto-layout, affichée(s) à taille fixe."})


def _texts(node: dict[str, Any]) -> str:
    return " ".join(child.get("text", "") for child in iter_nodes(node) if child.get("type") == "text").strip()


def _resolve_navigation(root: dict[str, Any], screen: dict[str, Any], frame_to_screen: dict[str, str]) -> dict[str, Any]:
    """Figma links point to frames: point them to screens. A button without a Figma link whose
    text is the label of a link of the flow ("Envoyer") leads where the flow says."""
    by_label: dict[str, str] = {}
    for link in screen["links"]:
        if link["label"]:
            by_label.setdefault(normalize(link["label"]), link["target"])

    def visit(node: dict[str, Any]) -> dict[str, Any]:
        node = dict(node)
        nav = node.get("nav")
        if nav and nav.get("kind") == "navigate":
            target = frame_to_screen.get(nav.get("frame"))
            node["nav"] = {**nav, "screen": target} if target else None
            if not target:
                node.pop("nav")
        elif not nav and node.get("role") == "button" and by_label:
            target = by_label.get(normalize(_texts(node)))
            if target:
                node["nav"] = {"kind": "navigate", "screen": target, "from_flow": True}
        if node.get("children"):
            node["children"] = [visit(child) for child in node["children"]]
        return node

    return visit(root)


def build_model(project: dict[str, Any], result: Assembly, global_library: dict[str, Any] | None) -> dict[str, Any]:
    frame_to_screen = _frame_to_screen(result)
    analysis = project.get("analysis") or {}
    behaviors = project.get("behaviors") or {}
    screens = []
    for screen in result.screens:
        if screen["excluded"]:
            continue
        root = result.roots.get(screen["frame"] or "")
        frame = result.frames.get(screen["frame"] or "") or {}
        active_links = [link for link in screen["links"] if link["target"] in {s["id"] for s in result.screens if not s["excluded"]}]
        screens.append({
            "id": screen["id"],
            "name": screen["name"],
            "module": screen["module"],
            "kind": "figma" if root else "deduced",
            "width": frame.get("width") or 390,
            "height": frame.get("height") or 844,
            "root": _resolve_navigation(root, {**screen, "links": active_links}, frame_to_screen) if root else None,
            "links": [{"target": link["target"], "label": link["label"], "conditions": link["conditions"]} for link in active_links],
            "behaviors": {key: value for key, value in (behaviors.get(screen["id"]) or {}).items() if key in ("fields", "actions", "lists", "bindings")},
        })
    modules = [
        {"id": module["id"], "title": module["title"], "screens": [sid for sid in module["screens"] if any(s["id"] == sid for s in screens)]}
        for module in result.modules
    ]
    if not result.frames:
        reference = (390, 844)
    else:
        first = next(iter(result.frames.values()))
        reference = (first["width"], first["height"])
    for screen in screens:
        if screen["kind"] == "deduced":
            screen["width"], screen["height"] = reference
    return {
        "model_version": MODEL_VERSION,
        "project": project.get("name", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "start": result.start,
        "modules": [module for module in modules if module["screens"]],
        "screens": screens,
        "entities": analysis.get("entities") or [],
        "seed": analysis.get("seed") or {},
        "theme": theme_from([project.get("library"), global_library]),
    }


def figma_summary(result: Assembly) -> dict[str, Any]:
    from figma_reader import public_pages

    report = result.report.as_dict()
    return {
        "pages": public_pages(result.pages),
        "page_id": result.page_id,
        "frames": len(result.frames),
        "interactions": report["interactions"],
        "instances": sum(item["count"] for item in report["instances"]),
        "images": report["images"],
        "icons_without_geometry": report["icons_without_geometry"],
        "absolute_zones": len(report["absolute_zones"]),
        "error": result.figma_error,
    }
