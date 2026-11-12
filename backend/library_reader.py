"""Reads the libraries of the prototypes: the global design system and the project library.

One import field takes any of these files, recognised by their content:
    - the Figma JSON of a library file (components and variants, colour styles);
    - the local variables of a file (REST API, Enterprise plans: GET /v1/files/:key/variables/local);
    - a design-token export (W3C / Tokens Studio style: {"color": {"primary": {"$value": "#…"}}}).
"""
from __future__ import annotations

import re
from typing import Any

from context_reader import normalize
from figma_reader import FigmaError, css_color, first_solid, iter_nodes, load_figma

THEME_HINTS = {
    "primary": ("primary", "primaire", "brand", "marque", "accent", "action"),
    "danger": ("danger", "error", "erreur", "critical", "negative", "alert"),
    "success": ("success", "succes", "positive", "valid"),
    "text": ("text primary", "text default", "texte", "text", "ink", "foreground", "on surface"),
    "background": ("background", "fond", "surface", "bg", "canvas"),
}
DEFAULT_THEME = {
    "primary": "#2F54EB",
    "danger": "#D92D20",
    "success": "#12B76A",
    "text": "#1D2939",
    "background": "#FFFFFF",
    "font": "system-ui, sans-serif",
}
HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}(?:[0-9a-fA-F]{2})?$")


class LibraryError(ValueError):
    """The file is neither a Figma library, nor variables, nor design tokens."""


def _variables_tokens(payload: dict[str, Any]) -> list[dict[str, Any]] | None:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else payload
    variables = meta.get("variables")
    collections = meta.get("variableCollections") or {}
    if not isinstance(variables, dict) or not variables:
        return None
    tokens = []

    def resolve(value: Any, depth: int = 0) -> Any:
        if isinstance(value, dict) and value.get("type") == "VARIABLE_ALIAS" and depth < 10:
            target = variables.get(value.get("id")) or {}
            collection = collections.get(target.get("variableCollectionId")) or {}
            mode = collection.get("defaultModeId") or next(iter(target.get("valuesByMode") or {}), None)
            return resolve((target.get("valuesByMode") or {}).get(mode), depth + 1)
        return value

    for variable in variables.values():
        if not isinstance(variable, dict):
            continue
        collection = collections.get(variable.get("variableCollectionId")) or {}
        modes = {mode.get("modeId"): mode.get("name") for mode in collection.get("modes") or []}
        default_mode = collection.get("defaultModeId") or next(iter(variable.get("valuesByMode") or {}), None)
        value = resolve((variable.get("valuesByMode") or {}).get(default_mode))
        kind = variable.get("resolvedType")
        if kind == "COLOR" and isinstance(value, dict):
            tokens.append({"name": variable.get("name", ""), "type": "color", "value": css_color(value), "collection": collection.get("name", ""), "mode": modes.get(default_mode, "")})
        elif kind == "FLOAT" and isinstance(value, (int, float)):
            tokens.append({"name": variable.get("name", ""), "type": "number", "value": value, "collection": collection.get("name", ""), "mode": modes.get(default_mode, "")})
        elif kind == "STRING" and isinstance(value, str):
            tokens.append({"name": variable.get("name", ""), "type": "string", "value": value, "collection": collection.get("name", ""), "mode": modes.get(default_mode, "")})
    return tokens


def _design_tokens(payload: dict[str, Any]) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []

    def visit(node: Any, path: list[str], inherited_type: str | None) -> None:
        if not isinstance(node, dict):
            return
        declared = node.get("$type") or node.get("type")
        node_type = declared if isinstance(declared, str) else inherited_type
        value_key = "$value" if "$value" in node else ("value" if "value" in node and not isinstance(node.get("value"), dict) else None)
        if value_key:
            value = node[value_key]
            if isinstance(value, str) and HEX.match(value.strip()):
                tokens.append({"name": "/".join(path), "type": "color", "value": value.strip().upper(), "collection": path[0] if path else "", "mode": ""})
            elif isinstance(value, (int, float)) or (isinstance(value, str) and re.fullmatch(r"-?\d+(\.\d+)?(px|rem)?", value.strip())):
                tokens.append({"name": "/".join(path), "type": "number", "value": value, "collection": path[0] if path else "", "mode": ""})
            elif isinstance(value, str) and (node_type or "").lower() in ("fontfamily", "fontfamilies"):
                tokens.append({"name": "/".join(path), "type": "string", "value": value, "collection": path[0] if path else "", "mode": ""})
            return
        for key, child in node.items():
            if not key.startswith("$"):
                visit(child, [*path, key], node_type)

    visit(payload, [], None)
    return tokens


def _components(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    figma = load_figma(payload)
    components: dict[str, dict[str, Any]] = {}
    style_tokens: dict[str, dict[str, Any]] = {}
    for root in figma.roots:
        for node in iter_nodes(root):
            if node.get("type") == "COMPONENT":
                meta = figma.components.get(node.get("id")) or {}
                set_meta = figma.component_sets.get(meta.get("componentSetId")) or {}
                props = {}
                if "=" in str(node.get("name", "")):
                    for pair in str(node["name"]).split(","):
                        if "=" in pair:
                            key, value = pair.split("=", 1)
                            props[key.strip()] = value.strip()
                key = meta.get("key") or node.get("key") or ""
                components[key or str(node.get("id"))] = {
                    "key": key,
                    "id": str(node.get("id")),
                    "name": str(node.get("name") or ""),
                    "set": str(set_meta.get("name") or ""),
                    "setKey": str(set_meta.get("key") or ""),
                    "props": props,
                }
            for kind, style_id in (node.get("styles") or {}).items():
                style = figma.styles.get(style_id) or {}
                if kind in ("fill", "fills") and style.get("name") and style.get("name") not in style_tokens:
                    color = first_solid(node.get("fills"))
                    if color:
                        style_tokens[style["name"]] = {"name": style["name"], "type": "color", "value": color, "collection": "Styles", "mode": ""}
    # Components published without their nodes in this export (only the table).
    for component_id, meta in figma.components.items():
        key = meta.get("key") or component_id
        if key not in components and not meta.get("remote"):
            set_meta = figma.component_sets.get(meta.get("componentSetId")) or {}
            components[key] = {"key": meta.get("key") or "", "id": component_id, "name": meta.get("name", ""), "set": set_meta.get("name", ""), "setKey": set_meta.get("key", ""), "props": {}}
    return list(components.values()), list(style_tokens.values())


def read_library(payload: Any, file_name: str = "") -> dict[str, Any]:
    """{"kind": "components"|"tokens", "components": [...], "tokens": [...]}"""
    if not isinstance(payload, dict):
        raise LibraryError("Le fichier n’est pas une bibliothèque : un objet JSON est attendu.")
    variable_tokens = _variables_tokens(payload)
    if variable_tokens is not None:
        return {"kind": "tokens", "source": file_name, "components": [], "tokens": variable_tokens}
    if payload.get("document") or payload.get("nodes") or (payload.get("type") and payload.get("id")):
        try:
            components, tokens = _components(payload)
        except FigmaError as exc:
            raise LibraryError(str(exc)) from exc
        return {"kind": "components", "source": file_name, "components": components, "tokens": tokens}
    tokens = _design_tokens(payload)
    if tokens:
        return {"kind": "tokens", "source": file_name, "components": [], "tokens": tokens}
    raise LibraryError(
        "Fichier non reconnu : attendu le JSON Figma d’une bibliothèque, les variables d’un fichier Figma, ou un export de design tokens."
    )


def merge_library(existing: dict[str, Any] | None, imported: dict[str, Any]) -> dict[str, Any]:
    """A library keeps one components file and one tokens file; a new import replaces its kind."""
    library = {"components": [], "tokens": [], "components_source": None, "tokens_source": None, "style_tokens": []}
    library.update(existing or {})
    if imported["kind"] == "components":
        library["components"] = imported["components"]
        library["components_source"] = imported["source"]
        library["style_tokens"] = imported["tokens"]
    else:
        library["tokens"] = imported["tokens"]
        library["tokens_source"] = imported["source"]
    return library


def library_summary(library: dict[str, Any] | None) -> dict[str, Any]:
    library = library or {}
    return {
        "components": len(library.get("components") or []),
        "tokens": len(library.get("tokens") or []) or len(library.get("style_tokens") or []),
        "components_source": library.get("components_source"),
        "tokens_source": library.get("tokens_source"),
        "tokens_from_styles": not library.get("tokens") and bool(library.get("style_tokens")),
    }


def theme_from(libraries: list[dict[str, Any] | None]) -> dict[str, str]:
    """Colours of the generated screens (screens without a frame, messages): taken from the tokens,
    the project library first, then the global design system."""
    theme = dict(DEFAULT_THEME)
    found: set[str] = set()
    for library in libraries:
        if not library:
            continue
        tokens = (library.get("tokens") or []) + (library.get("style_tokens") or [])
        for role, hints in THEME_HINTS.items():
            if role in found:
                continue
            for hint in hints:
                match = next((t for t in tokens if t["type"] == "color" and hint in normalize(t["name"])), None)
                if match:
                    theme[role] = str(match["value"])
                    found.add(role)
                    break
        if "font" not in found:
            font = next((t for t in tokens if t["type"] == "string" and "font" in normalize(t["name"])), None)
            if font:
                theme["font"] = f'"{font["value"]}", system-ui, sans-serif'
                found.add("font")
    return theme


def inventory(instances: list[dict[str, Any]], project_library: dict[str, Any] | None, global_library: dict[str, Any] | None,
              local_keys: set[str]) -> dict[str, Any]:
    """Where each component used by the mockup comes from."""
    project_keys = {c["key"] for c in (project_library or {}).get("components") or [] if c.get("key")}
    global_keys = {c["key"] for c in (global_library or {}).get("components") or [] if c.get("key")}
    rows = []
    for instance in instances:
        key = instance.get("key") or ""
        if key and key in project_keys:
            source = "project"
        elif key and key in global_keys:
            source = "global"
        elif key in local_keys or not instance.get("remote"):
            source = "local"
        else:
            source = "missing"
        rows.append({**instance, "source": source})
    counts = {source: sum(1 for row in rows if row["source"] == source) for source in ("project", "global", "local", "missing")}
    return {"components": rows, "counts": counts}
