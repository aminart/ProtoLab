"""Reads the libraries of the prototypes: the global design system and the project library.

One import field takes any of these files, recognised by their content:
    - the Figma JSON of a library file (components and variants, colour styles);
    - the local variables of a file (REST API, Enterprise plans: GET /v1/files/:key/variables/local);
    - a design-token export (W3C / Tokens Studio style: {"color": {"primary": {"$value": "#…"}}}).
"""
from __future__ import annotations

import re
import uuid
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


COLOR_FUNCTION = re.compile(r"^(rgba?|hsla?)\(\s*[\d.%\s,/-]+\)$", re.I)
ALIAS = re.compile(r"^\{([^{}]+)\}$")
NUMBER = re.compile(r"^-?\d+(\.\d+)?(px|rem|em|%)?$")


def token_key(name: str) -> str:
    """Comparable name of a token: "color.brand.primary", "color/Brand/Primary" → "color/brand/primary"."""
    return "/".join(part.strip().lower() for part in re.split(r"[./]", name) if part.strip())


def _color(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        if HEX.match(text):
            return text.upper()
        if COLOR_FUNCTION.match(text):
            return text
    if isinstance(value, dict):  # W3C 2025: {"colorSpace": "srgb", "components": [r, g, b], "hex": "#…"}
        if isinstance(value.get("hex"), str) and HEX.match(value["hex"].strip()):
            return value["hex"].strip().upper()
        components = value.get("components")
        if isinstance(components, list) and len(components) >= 3 and all(isinstance(c, (int, float)) for c in components[:3]):
            return css_color({"r": components[0], "g": components[1], "b": components[2], "a": value.get("alpha", 1)})
    return None


def _design_tokens(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """W3C / Tokens Studio tokens. A value "{color.brand.primary}" is an alias, resolved later
    against every token file of the library (a component file points to the foundations)."""
    tokens: list[dict[str, Any]] = []

    def visit(node: Any, path: list[str], inherited_type: str | None) -> None:
        if not isinstance(node, dict):
            return
        declared = node.get("$type") or node.get("type")
        node_type = (declared if isinstance(declared, str) else inherited_type) or ""
        value_key = "$value" if "$value" in node else ("value" if "value" in node and isinstance(node.get("value"), (str, int, float)) else None)
        if value_key:
            value = node[value_key]
            name = "/".join(path)
            base = {"name": name, "collection": path[0] if path else "", "mode": ""}
            kind = node_type.lower()
            alias = ALIAS.match(value.strip()) if isinstance(value, str) else None
            color = _color(value)
            if alias:
                tokens.append({**base, "type": kind or "alias", "value": None, "alias": token_key(alias.group(1))})
            elif color and kind in ("", "color"):
                tokens.append({**base, "type": "color", "value": color})
            elif isinstance(value, (int, float)) or (isinstance(value, str) and NUMBER.match(value.strip())):
                tokens.append({**base, "type": "number", "value": value})
            elif isinstance(value, str) and kind in ("fontfamily", "fontfamilies"):
                tokens.append({**base, "type": "string", "value": value})
            elif isinstance(value, list) and kind in ("fontfamily", "fontfamilies") and value and isinstance(value[0], str):
                tokens.append({**base, "type": "string", "value": value[0]})
            return
        for key, child in node.items():
            if not key.startswith("$"):
                visit(child, [*path, key], node_type or None)

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
        "fichier non reconnu : attendu le JSON Figma d’une bibliothèque, les variables d’un fichier Figma, ou un export de design tokens."
    )


# --- A library = several files ------------------------------------------------------
#
# {"files": [{"id", "name", "kind", "imported_at", "components", "tokens"}]}. A file imported again
# under the same name replaces the previous one; a component (Figma key) or a token (name) found in
# several files comes from the most recent file.


def _upgrade(library: dict[str, Any] | None) -> dict[str, Any]:
    """Libraries saved by 0.1.0 (one components file + one tokens file) → list of files."""
    if not library:
        return {"files": []}
    if "files" in library:
        return library
    files = []
    if library.get("components") or library.get("style_tokens"):
        files.append({"id": "ancien-composants", "name": library.get("components_source") or "composants.json", "kind": "components",
                      "imported_at": "", "components": library.get("components") or [], "tokens": library.get("style_tokens") or []})
    if library.get("tokens"):
        files.append({"id": "ancien-tokens", "name": library.get("tokens_source") or "tokens.json", "kind": "tokens",
                      "imported_at": "", "components": [], "tokens": library["tokens"]})
    return {"files": files}


def add_files(library: dict[str, Any] | None, imported: list[dict[str, Any]], imported_at: str = "") -> dict[str, Any]:
    files = list(_upgrade(library)["files"])
    for item in imported:
        files = [existing for existing in files if existing["name"] != item["source"]]
        files.append({"id": uuid.uuid4().hex[:10], "name": item["source"], "kind": item["kind"], "imported_at": imported_at,
                      "components": item["components"], "tokens": item["tokens"]})
    return {"files": files}


def remove_file(library: dict[str, Any] | None, file_id: str) -> dict[str, Any] | None:
    files = [item for item in _upgrade(library)["files"] if item["id"] != file_id]
    return {"files": files} if files else None


def merged_components(library: dict[str, Any] | None) -> list[dict[str, Any]]:
    components: dict[str, dict[str, Any]] = {}
    for item in _upgrade(library)["files"]:
        for component in item["components"]:
            components[component.get("key") or component.get("id", "")] = component
    return list(components.values())


def merged_tokens(libraries: list[dict[str, Any] | None]) -> tuple[list[dict[str, Any]], list[str]]:
    """Every token of the libraries, aliases resolved across files. The first library wins over the
    next ones (project before global); inside a library, the latest file wins.
    Returns the resolved tokens and the names of the aliases that point nowhere."""
    by_key: dict[str, dict[str, Any]] = {}
    for library in reversed([lib for lib in libraries if lib]):
        for item in _upgrade(library)["files"]:
            for token in item["tokens"]:
                by_key[token_key(token["name"])] = token

    def resolve(token: dict[str, Any], depth: int = 0) -> dict[str, Any] | None:
        if not token.get("alias"):
            return token
        target = by_key.get(token["alias"])
        if target is None or depth > 10:
            return None
        return resolve(target, depth + 1)

    resolved, unresolved = [], []
    for token in by_key.values():
        target = resolve(token)
        if target is None:
            unresolved.append(token["name"])
        else:
            resolved.append({key: value for key, value in {**token, "type": target["type"], "value": target["value"]}.items() if key != "alias"})
    return resolved, unresolved


def library_summary(library: dict[str, Any] | None, resolve_with: list[dict[str, Any] | None] | None = None) -> dict[str, Any]:
    """Counts shown in the app. `resolve_with`: other libraries an alias may point to."""
    upgraded = _upgrade(library)
    tokens, unresolved = merged_tokens([library, *(resolve_with or [])])
    own = {token_key(token["name"]) for item in upgraded["files"] for token in item["tokens"]}
    return {
        "files": [
            {"id": item["id"], "name": item["name"], "kind": item["kind"], "imported_at": item.get("imported_at", ""),
             "components": len(item["components"]), "tokens": len(item["tokens"])}
            for item in upgraded["files"]
        ],
        "components": len(merged_components(library)),
        "tokens": len([token for token in tokens if token_key(token["name"]) in own]),
        "unresolved": sorted(name for name in unresolved if token_key(name) in own)[:50],
    }


def theme_from(libraries: list[dict[str, Any] | None]) -> dict[str, str]:
    """Colours of the generated screens (screens without a frame, messages): taken from the tokens,
    the project library first, then the global design system. Foundation colours (short names,
    under "color") win over component tokens ("button/primary/background")."""
    theme = dict(DEFAULT_THEME)
    tokens, _ = merged_tokens(libraries)
    colors = [token for token in tokens if token["type"] == "color" and isinstance(token.get("value"), str)]

    def rank(token: dict[str, Any]) -> tuple[int, int]:
        name = normalize(token["name"])
        return (0 if re.search(r"\b(color|colors|colour|couleur|couleurs|palette|semantic)\b", name) else 1, len(name.split()))

    for role, hints in THEME_HINTS.items():
        for hint in hints:
            matches = sorted((token for token in colors if hint in normalize(token["name"])), key=rank)
            if matches:
                theme[role] = str(matches[0]["value"])
                break
    font = next((token for token in tokens if token["type"] == "string" and "font" in normalize(token["name"])), None)
    if font:
        theme["font"] = f'"{font["value"]}", system-ui, sans-serif'
    return theme


def inventory(instances: list[dict[str, Any]], project_library: dict[str, Any] | None, global_library: dict[str, Any] | None,
              local_keys: set[str]) -> dict[str, Any]:
    """Where each component used by the mockup comes from."""
    project_keys = {c["key"] for c in merged_components(project_library) if c.get("key")}
    global_keys = {c["key"] for c in merged_components(global_library) if c.get("key")}
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
