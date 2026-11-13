"""Reads the JSON of the Figma REST API (file, or nodes of a file), without the model.

Each top-level frame of a page becomes a screen. Its layers are converted into a tree of boxes
with CSS styles: auto-layout becomes flexbox, so the screen keeps behaving when a message
appears or a list gets longer. Layers outside auto-layout are placed at their position, at a
fixed size, and reported. The prototype interactions (on click → frame) become navigation.

Accepted inputs (what the user's script produces):
    GET /v1/files/:key                {"document": …, "components": …, "componentSets": …}
    GET /v1/files/:key/nodes?ids=…    {"nodes": {"1:2": {"document": …, "components": …}}}
    a single node                     {"id": …, "type": "FRAME", …}
With `geometry=paths` on the request, icons and shapes are drawn (fillGeometry / strokeGeometry).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterator

from context_reader import normalize

CONTAINERS = {"FRAME", "GROUP", "COMPONENT", "COMPONENT_SET", "INSTANCE", "SECTION"}
SHAPES = {"VECTOR", "BOOLEAN_OPERATION", "STAR", "POLYGON", "REGULAR_POLYGON", "LINE", "ELLIPSE", "RECTANGLE"}
SCREEN_TYPES = {"FRAME", "COMPONENT", "INSTANCE"}
PROTOTYPE_PAGE_HINTS = ("prototype", "proto", "ecrans", "screens", "maquette", "mockup", "ui")
CLICK_TRIGGERS = {"ON_CLICK", "ON_TAP", "ON_PRESS", "MOUSE_UP", "MOUSE_DOWN"}

ROLE_PATTERNS = [
    ("checkbox", re.compile(r"\b(checkbox|check box|case a cocher|case|toggle|switch|radio|interrupteur)\b")),
    ("input", re.compile(r"\b(input|champ|text ?field|textfield|textarea|text area|saisie|search ?bar|recherche|select|dropdown|liste deroulante|date ?picker|combobox|zone de texte|form field)\b")),
    ("button", re.compile(r"\b(button|bouton|btn|cta|link|lien|tab|onglet|chip)\b")),
]
VALUE_TEXT = re.compile(r"\b(value|valeur|placeholder|texte saisi|saisie|input|content|contenu|text)\b")
MULTILINE = re.compile(r"\b(textarea|text area|zone de texte|commentaire|comment|description|message)\b")


class FigmaError(ValueError):
    """The file is not a Figma JSON this reader understands."""


# --- Loading --------------------------------------------------------------------


@dataclass
class FigmaFile:
    name: str
    roots: list[dict[str, Any]]
    components: dict[str, dict[str, Any]] = field(default_factory=dict)
    component_sets: dict[str, dict[str, Any]] = field(default_factory=dict)
    styles: dict[str, dict[str, Any]] = field(default_factory=dict)


def load_figma(payload: Any) -> FigmaFile:
    if not isinstance(payload, dict):
        raise FigmaError("Le fichier n’est pas un JSON Figma : un objet est attendu.")
    figma = FigmaFile(name=str(payload.get("name") or ""), roots=[])

    def absorb(container: dict[str, Any]) -> None:
        figma.components.update(container.get("components") or {})
        figma.component_sets.update(container.get("componentSets") or {})
        figma.styles.update(container.get("styles") or {})

    if isinstance(payload.get("document"), dict):
        figma.roots.append(payload["document"])
        absorb(payload)
    elif isinstance(payload.get("nodes"), dict):
        for entry in payload["nodes"].values():
            if isinstance(entry, dict) and isinstance(entry.get("document"), dict):
                figma.roots.append(entry["document"])
                absorb(entry)
        absorb(payload)
    elif payload.get("type") and payload.get("id"):
        figma.roots.append(payload)
        absorb(payload)
    if not figma.roots:
        raise FigmaError(
            "Ce JSON ne ressemble pas à un export de l’API Figma : il faut une clé « document », « nodes », ou un node avec « id » et « type »."
        )
    return figma


def iter_nodes(node: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield node
    for child in node.get("children") or []:
        if isinstance(child, dict):
            yield from iter_nodes(child)


def _box(node: dict[str, Any]) -> dict[str, float]:
    box = node.get("absoluteBoundingBox") or node.get("absoluteRenderBounds") or {}
    size = node.get("size") or {}
    return {
        "x": float(box.get("x") or 0),
        "y": float(box.get("y") or 0),
        "width": float(box.get("width") or size.get("x") or 0),
        "height": float(box.get("height") or size.get("y") or 0),
    }


def _screen_frames(container: dict[str, Any]) -> list[dict[str, Any]]:
    frames = []
    for child in container.get("children") or []:
        if not isinstance(child, dict) or child.get("visible") is False:
            continue
        if child.get("type") == "SECTION":
            frames.extend(_screen_frames(child))
        elif child.get("type") in SCREEN_TYPES:
            frames.append(child)
    return frames


def list_pages(figma: FigmaFile) -> list[dict[str, Any]]:
    """Pages with their screens (top-level frames; frames inside sections count too)."""
    pages = []
    for root in figma.roots:
        kind = root.get("type")
        if kind == "DOCUMENT":
            candidates = [child for child in root.get("children") or [] if isinstance(child, dict) and child.get("type") == "CANVAS"]
        elif kind == "CANVAS":
            candidates = [root]
        elif kind == "SECTION":
            candidates = [root]
        elif kind in SCREEN_TYPES:
            candidates = [{"id": f"selection:{root.get('id')}", "name": root.get("name") or "Sélection", "children": [root]}]
        else:
            continue
        for page in candidates:
            frames = _screen_frames(page)
            pages.append({
                "id": str(page.get("id")),
                "name": str(page.get("name") or "Page"),
                "frames": [
                    {"id": str(frame.get("id")), "name": str(frame.get("name") or ""), "width": _box(frame)["width"], "height": _box(frame)["height"]}
                    for frame in frames
                ],
                "_frames": frames,
            })
    return pages


def default_page_id(pages: list[dict[str, Any]]) -> str | None:
    with_frames = [page for page in pages if page["frames"]]
    for page in with_frames:
        if any(hint in normalize(page["name"]).split() for hint in PROTOTYPE_PAGE_HINTS):
            return page["id"]
    return with_frames[0]["id"] if with_frames else (pages[0]["id"] if pages else None)


def public_pages(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in page.items() if not key.startswith("_")} for page in pages]


# --- Styles ---------------------------------------------------------------------


def _num(value: float) -> str:
    rounded = round(float(value), 2)
    return str(int(rounded)) if rounded == int(rounded) else str(rounded)


def _px(value: float) -> str:
    return f"{_num(value)}px"


def css_color(color: dict[str, Any] | None, opacity: float = 1.0) -> str:
    if not color:
        return "transparent"
    r, g, b = (max(0, min(255, round(float(color.get(channel, 0)) * 255))) for channel in "rgb")
    alpha = float(color.get("a", 1)) * opacity
    if alpha >= 0.999:
        return f"#{r:02X}{g:02X}{b:02X}"
    return f"rgba({r}, {g}, {b}, {round(alpha, 3)})"


def _visible(paints: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [paint for paint in paints or [] if isinstance(paint, dict) and paint.get("visible", True) is not False]


def _gradient(paint: dict[str, Any]) -> str:
    opacity = float(paint.get("opacity", 1))
    stops = ", ".join(
        f"{css_color(stop.get('color'), opacity)} {round(float(stop.get('position', 0)) * 100, 1)}%" for stop in paint.get("gradientStops") or []
    )
    if paint.get("type") == "GRADIENT_LINEAR":
        handles = paint.get("gradientHandlePositions") or []
        angle = 180.0
        if len(handles) >= 2:
            dx = float(handles[1].get("x", 0)) - float(handles[0].get("x", 0))
            dy = float(handles[1].get("y", 0)) - float(handles[0].get("y", 0))
            angle = math.degrees(math.atan2(dx, -dy)) % 360
        return f"linear-gradient({round(angle, 1)}deg, {stops})"
    return f"radial-gradient(circle, {stops})"


IMAGE_PLACEHOLDER = "#D0D5DD"


def fill_style(paints: list[dict[str, Any]] | None) -> tuple[dict[str, str], bool]:
    """Background of a box. Returns the style and whether one of the fills is an image."""
    fills = _visible(paints)
    has_image = any(paint.get("type") == "IMAGE" for paint in fills)
    if not fills:
        return {}, False
    if len(fills) == 1 and fills[0].get("type") in ("SOLID", "IMAGE"):
        paint = fills[0]
        color = IMAGE_PLACEHOLDER if paint.get("type") == "IMAGE" else css_color(paint.get("color"), float(paint.get("opacity", 1)))
        return {"backgroundColor": color}, has_image
    layers = []
    for paint in reversed(fills):  # Figma lists the bottom fill first, CSS the top layer first.
        kind = paint.get("type")
        if kind == "SOLID":
            color = css_color(paint.get("color"), float(paint.get("opacity", 1)))
            layers.append(f"linear-gradient({color}, {color})")
        elif kind and kind.startswith("GRADIENT"):
            layers.append(_gradient(paint))
        elif kind == "IMAGE":
            layers.append(f"linear-gradient({IMAGE_PLACEHOLDER}, {IMAGE_PLACEHOLDER})")
    return ({"backgroundImage": ", ".join(layers)} if layers else {}), has_image


def first_solid(paints: list[dict[str, Any]] | None) -> str | None:
    for paint in reversed(_visible(paints)):
        if paint.get("type") == "SOLID":
            return css_color(paint.get("color"), float(paint.get("opacity", 1)))
    return None


def _shadows(node: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    shadows: list[str] = []
    extra: dict[str, str] = {}
    strokes = _visible(node.get("strokes"))
    stroke_color = first_solid(strokes)
    weight = float(node.get("strokeWeight") or 0)
    if stroke_color and (weight > 0 or node.get("individualStrokeWeights")):
        individual = node.get("individualStrokeWeights")
        align = node.get("strokeAlign") or "INSIDE"
        if individual:
            for side, template in (("top", "inset 0 {w} 0 0"), ("bottom", "inset 0 -{w} 0 0"), ("left", "inset {w} 0 0 0"), ("right", "inset -{w} 0 0 0")):
                value = float(individual.get(side) or 0)
                if value > 0:
                    shadows.append(f"{template.format(w=_px(value))} {stroke_color}")
        elif align == "OUTSIDE":
            shadows.append(f"0 0 0 {_px(weight)} {stroke_color}")
        elif align == "CENTER":
            shadows.append(f"inset 0 0 0 {_px(weight / 2)} {stroke_color}")
            shadows.append(f"0 0 0 {_px(weight / 2)} {stroke_color}")
        else:
            shadows.append(f"inset 0 0 0 {_px(weight)} {stroke_color}")
    for effect in node.get("effects") or []:
        if not isinstance(effect, dict) or effect.get("visible") is False:
            continue
        kind = effect.get("type")
        if kind in ("DROP_SHADOW", "INNER_SHADOW"):
            offset = effect.get("offset") or {}
            shadow = (
                f"{_px(offset.get('x', 0))} {_px(offset.get('y', 0))} {_px(effect.get('radius', 0))} "
                f"{_px(effect.get('spread', 0))} {css_color(effect.get('color'))}"
            )
            shadows.append(("inset " if kind == "INNER_SHADOW" else "") + shadow)
        elif kind == "LAYER_BLUR":
            extra["filter"] = f"blur({_px(float(effect.get('radius', 0)) / 2)})"
        elif kind == "BACKGROUND_BLUR":
            extra["backdropFilter"] = f"blur({_px(float(effect.get('radius', 0)) / 2)})"
    return shadows, extra


def _radius(node: dict[str, Any]) -> dict[str, str]:
    radii = node.get("rectangleCornerRadii")
    if isinstance(radii, list) and len(radii) == 4 and any(radii):
        return {"borderRadius": " ".join(_px(value) for value in radii)}
    if node.get("cornerRadius"):
        return {"borderRadius": _px(node["cornerRadius"])}
    if node.get("type") == "ELLIPSE":
        return {"borderRadius": "50%"}
    return {}


def text_style(node: dict[str, Any]) -> dict[str, str]:
    style = node.get("style") or {}
    css: dict[str, str] = {}
    color = first_solid(node.get("fills"))
    if color:
        css["color"] = color
    family = style.get("fontFamily")
    css["fontFamily"] = f'"{family}", system-ui, sans-serif' if family else "system-ui, sans-serif"
    if style.get("fontSize"):
        css["fontSize"] = _px(style["fontSize"])
    if style.get("fontWeight"):
        css["fontWeight"] = str(int(style["fontWeight"]))
    if style.get("italic"):
        css["fontStyle"] = "italic"
    if style.get("lineHeightPx") and style.get("lineHeightUnit") != "INTRINSIC_%":
        css["lineHeight"] = _px(style["lineHeightPx"])
    if style.get("letterSpacing"):
        css["letterSpacing"] = _px(style["letterSpacing"])
    align = {"CENTER": "center", "RIGHT": "right", "JUSTIFIED": "justify"}.get(style.get("textAlignHorizontal", ""))
    if align:
        css["textAlign"] = align
    transform = {"UPPER": "uppercase", "LOWER": "lowercase", "TITLE": "capitalize"}.get(style.get("textCase", ""))
    if transform:
        css["textTransform"] = transform
    decoration = {"UNDERLINE": "underline", "STRIKETHROUGH": "line-through"}.get(style.get("textDecoration", ""))
    if decoration:
        css["textDecoration"] = decoration
    return css


# --- Layout ---------------------------------------------------------------------


def text_auto_resize(node: dict[str, Any]) -> str | None:
    """WIDTH_AND_HEIGHT, HEIGHT, TRUNCATE or NONE. The REST API puts it in the text style;
    older exports and plugins put it on the node."""
    return node.get("textAutoResize") or (node.get("style") or {}).get("textAutoResize")


def _is_auto_layout(node: dict[str, Any]) -> bool:
    return node.get("layoutMode") in ("HORIZONTAL", "VERTICAL")


def _sizing(node: dict[str, Any], axis: str, parent_mode: str | None) -> str:
    """FIXED, HUG or FILL along `axis` ("h" or "v") for a child of an auto-layout parent."""
    explicit = node.get("layoutSizingHorizontal" if axis == "h" else "layoutSizingVertical")
    if explicit in ("FIXED", "HUG", "FILL"):
        return explicit
    parent_primary = "h" if parent_mode == "HORIZONTAL" else "v"
    if axis == parent_primary and float(node.get("layoutGrow") or 0) >= 1:
        return "FILL"
    if axis != parent_primary and node.get("layoutAlign") == "STRETCH":
        return "FILL"
    if node.get("type") == "TEXT":
        resize = text_auto_resize(node)
        if resize == "WIDTH_AND_HEIGHT" or (resize == "HEIGHT" and axis == "v"):
            return "HUG"
        return "FIXED"
    if _is_auto_layout(node):
        own_primary = "h" if node["layoutMode"] == "HORIZONTAL" else "v"
        mode = node.get("primaryAxisSizingMode") if axis == own_primary else node.get("counterAxisSizingMode")
        if mode == "AUTO":
            return "HUG"
    return "FIXED"


def _container_style(node: dict[str, Any]) -> dict[str, str]:
    css: dict[str, str] = {"display": "flex", "flexDirection": "row" if node["layoutMode"] == "HORIZONTAL" else "column"}
    padding = [float(node.get(key) or 0) for key in ("paddingTop", "paddingRight", "paddingBottom", "paddingLeft")]
    if any(padding):
        css["padding"] = " ".join(_px(value) for value in padding)
    primary = node.get("primaryAxisAlignItems") or "MIN"
    css["justifyContent"] = {"MIN": "flex-start", "CENTER": "center", "MAX": "flex-end", "SPACE_BETWEEN": "space-between"}.get(primary, "flex-start")
    css["alignItems"] = {"MIN": "flex-start", "CENTER": "center", "MAX": "flex-end", "BASELINE": "baseline"}.get(
        node.get("counterAxisAlignItems") or "MIN", "flex-start"
    )
    spacing = float(node.get("itemSpacing") or 0)
    if spacing and primary != "SPACE_BETWEEN":
        css["columnGap" if css["flexDirection"] == "row" else "rowGap"] = _px(spacing)
    if node.get("layoutWrap") == "WRAP":
        css["flexWrap"] = "wrap"
        counter = float(node.get("counterAxisSpacing") or 0)
        if counter:
            css["rowGap" if css["flexDirection"] == "row" else "columnGap"] = _px(counter)
    return css


def _size_style(node: dict[str, Any], parent: dict[str, Any] | None, box: dict[str, float], parent_box: dict[str, float] | None) -> dict[str, str]:
    css: dict[str, str] = {}
    in_flow = parent is not None and _is_auto_layout(parent) and node.get("layoutPositioning") != "ABSOLUTE"
    if parent is None:
        css["width"] = _px(box["width"])
        css["minHeight"] = _px(box["height"])
        return css
    if not in_flow:
        css["position"] = "absolute"
        css["left"] = _px(box["x"] - (parent_box or box)["x"])
        css["top"] = _px(box["y"] - (parent_box or box)["y"])
        if node.get("type") == "LINE":
            # A line's box has no height: draw its stroke centred on it (Figma's default).
            weight = max(1.0, float(node.get("strokeWeight") or 1))
            offset = {"CENTER": weight / 2, "OUTSIDE": weight, "INSIDE": 0.0}.get(node.get("strokeAlign") or "CENTER", weight / 2)
            css["top"] = _px(box["y"] - (parent_box or box)["y"] - offset)
            css["width"] = _px(box["width"])
            return css
        if node.get("type") == "TEXT" and text_auto_resize(node) == "WIDTH_AND_HEIGHT":
            return css
        css["width"] = _px(box["width"])
        if not (node.get("type") == "TEXT" and text_auto_resize(node) == "HEIGHT"):
            css["height"] = _px(box["height"])
        return css
    row = parent["layoutMode"] == "HORIZONTAL"
    for axis, dimension, size in (("h", "width", box["width"]), ("v", "height", box["height"])):
        mode = _sizing(node, axis, parent["layoutMode"])
        primary = (axis == "h") == row
        if mode == "FIXED":
            css[dimension] = _px(size)
            if primary:
                css["flexShrink"] = "0"
        elif mode == "FILL":
            if primary:
                css["flex"] = "1 1 0px"
                css["min" + dimension.capitalize()] = "0px"
            else:
                css["alignSelf"] = "stretch"
        elif primary:
            css["flexShrink"] = "0"
    for key, css_key in (("minWidth", "minWidth"), ("maxWidth", "maxWidth"), ("minHeight", "minHeight"), ("maxHeight", "maxHeight")):
        if node.get(key):
            css[css_key] = _px(node[key])
    return css


# --- Conversion -----------------------------------------------------------------


@dataclass
class Report:
    """What the conversion of the screens found, shown after the import."""

    absolute_zones: list[dict[str, Any]] = field(default_factory=list)
    images: int = 0
    icons_without_geometry: int = 0
    interactions: int = 0
    instances: dict[str, dict[str, Any]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "absolute_zones": self.absolute_zones,
            "images": self.images,
            "icons_without_geometry": self.icons_without_geometry,
            "interactions": self.interactions,
            "instances": sorted(self.instances.values(), key=lambda item: -item["count"]),
        }


class Converter:
    def __init__(self, figma: FigmaFile, report: Report | None = None) -> None:
        self.figma = figma
        self.report = report or Report()
        self.screen_name = ""

    # Component behind an instance: name of its set ("Input"), its key, its variant properties.
    def component_info(self, node: dict[str, Any]) -> dict[str, Any] | None:
        component_id = node.get("componentId")
        if not component_id:
            return None
        component = self.figma.components.get(component_id) or {}
        set_id = component.get("componentSetId")
        component_set = self.figma.component_sets.get(set_id) or {} if set_id else {}
        props = {}
        for name, value in (node.get("componentProperties") or {}).items():
            if isinstance(value, dict) and value.get("type") == "VARIANT":
                props[name.split("#")[0]] = value.get("value")
        if not props and "=" in str(component.get("name", "")):
            for pair in str(component["name"]).split(","):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    props[key.strip()] = value.strip()
        return {
            "id": component_id,
            "key": component.get("key") or "",
            "name": component.get("name") or node.get("name") or "",
            "set": component_set.get("name") or "",
            "setKey": component_set.get("key") or "",
            "remote": bool(component.get("remote")),
            "props": props,
        }

    def _role(self, node: dict[str, Any], component: dict[str, Any] | None) -> str | None:
        if node.get("type") not in ("INSTANCE", "FRAME", "COMPONENT"):
            return None
        names = [component["set"], component["name"]] if component else []
        names.append(str(node.get("name") or ""))
        for kind, pattern in ROLE_PATTERNS:
            if any(pattern.search(normalize(name)) for name in names if name):
                if not any(child.get("type") == "TEXT" for child in iter_nodes(node)) and kind != "checkbox":
                    return None
                return kind
        return None

    def _navigation(self, node: dict[str, Any]) -> dict[str, Any] | None:
        for interaction in node.get("interactions") or []:
            trigger = (interaction.get("trigger") or {}).get("type")
            if trigger not in CLICK_TRIGGERS:
                continue
            for action in interaction.get("actions") or []:
                if not isinstance(action, dict):
                    continue
                kind = action.get("type")
                if kind == "NODE" and action.get("destinationId") and action.get("navigation", "NAVIGATE") in ("NAVIGATE", "OVERLAY", "SWAP"):
                    self.report.interactions += 1
                    return {"kind": "navigate", "frame": str(action["destinationId"]), "overlay": action.get("navigation") == "OVERLAY"}
                if kind in ("BACK", "CLOSE"):
                    self.report.interactions += 1
                    return {"kind": "back"}
                if kind == "URL" and action.get("url"):
                    self.report.interactions += 1
                    return {"kind": "url", "url": str(action["url"])}
        if node.get("transitionNodeID"):
            self.report.interactions += 1
            return {"kind": "navigate", "frame": str(node["transitionNodeID"]), "overlay": False}
        return None

    def _input_parts(self, node: dict[str, Any]) -> dict[str, Any]:
        """The box the user types in, the text inside it (replaced by a real field) and the label."""
        box = node
        for candidate in iter_nodes(node):
            if candidate is node or candidate.get("type") not in CONTAINERS | {"RECTANGLE"}:
                continue
            if first_solid(candidate.get("strokes")) or any(e.get("type") == "INNER_SHADOW" for e in candidate.get("effects") or []):
                box = candidate if candidate.get("type") != "RECTANGLE" else box
                break
        texts_in_box = [child for child in iter_nodes(box) if child.get("type") == "TEXT" and child.get("visible", True) is not False]
        value = next((text for text in texts_in_box if VALUE_TEXT.search(normalize(str(text.get("name", ""))))), None)
        value = value or (texts_in_box[0] if texts_in_box else None)
        box_ids = {id(child) for child in iter_nodes(box)}
        label = next(
            (text for text in iter_nodes(node) if text.get("type") == "TEXT" and id(text) not in box_ids and text.get("visible", True) is not False),
            None,
        )
        names = " ".join(normalize(str(part)) for part in (node.get("name"), label.get("characters") if label else ""))
        return {
            "box": str(box.get("id")),
            "valueText": str(value.get("id")) if value else None,
            "placeholder": str(value.get("characters", "")) if value else "",
            "label": str(label.get("characters", "")).strip() if label else "",
            "multiline": bool(MULTILINE.search(names)),
        }

    def convert(self, node: dict[str, Any], parent: dict[str, Any] | None = None, in_control: bool = False) -> dict[str, Any] | None:
        if node.get("visible") is False:
            return None
        kind = node.get("type")
        box = _box(node)
        parent_box = _box(parent) if parent is not None else None
        style: dict[str, str] = {"boxSizing": "border-box"}
        style.update(_size_style(node, parent, box, parent_box))
        if node.get("opacity") is not None and float(node["opacity"]) < 1:
            style["opacity"] = str(round(float(node["opacity"]), 3))
        out: dict[str, Any] = {"id": str(node.get("id")), "name": str(node.get("name") or "")}

        nav = self._navigation(node)
        if nav:
            out["nav"] = nav

        if kind == "TEXT":
            out["type"] = "text"
            out["text"] = str(node.get("characters") or "")
            style.update(text_style(node))
            resize = text_auto_resize(node)
            style["whiteSpace"] = "pre" if resize == "WIDTH_AND_HEIGHT" else "pre-wrap"
            style["overflowWrap"] = "break-word"
            if resize == "TRUNCATE" or (node.get("style") or {}).get("textTruncation") == "ENDING":
                style.update({"overflow": "hidden", "textOverflow": "ellipsis"})
            vertical = (node.get("style") or {}).get("textAlignVertical")
            if vertical in ("CENTER", "BOTTOM") and resize in (None, "NONE", "TRUNCATE"):
                style.update({"display": "flex", "flexDirection": "column", "justifyContent": "center" if vertical == "CENTER" else "flex-end"})
            out["style"] = style
            return out

        geometry = (node.get("fillGeometry") or []) + (node.get("strokeGeometry") or [])
        if kind in SHAPES and kind != "RECTANGLE" and not (kind == "ELLIPSE" and not geometry):
            size = node.get("size") or {"x": box["width"], "y": box["height"]}
            if geometry:
                fill_color = first_solid(node.get("fills"))
                stroke_color = first_solid(node.get("strokes"))
                paths = [
                    {"d": path.get("path", ""), "fill": fill_color, "rule": (path.get("windingRule") or "NONZERO").lower()}
                    for path in node.get("fillGeometry") or []
                    if fill_color
                ] + [
                    {"d": path.get("path", ""), "fill": stroke_color, "rule": (path.get("windingRule") or "NONZERO").lower()}
                    for path in node.get("strokeGeometry") or []
                    if stroke_color
                ]
                out.update({"type": "svg", "viewBox": f"0 0 {_num(size.get('x', 0))} {_num(size.get('y', 0))}", "paths": paths})
                style["overflow"] = "visible"
            elif kind == "LINE":
                out["type"] = "box"
                style["backgroundColor"] = first_solid(node.get("strokes")) or "transparent"
                style["height"] = _px(max(1.0, float(node.get("strokeWeight") or 1)))
            else:
                out["type"] = "box"
                self.report.icons_without_geometry += 1
            out["style"] = style
            return out

        out["type"] = "box"
        background, has_image = fill_style(node.get("fills"))
        style.update(background)
        if has_image:
            out["image"] = True
            self.report.images += 1
        shadows, extra = _shadows(node)
        if shadows:
            style["boxShadow"] = ", ".join(shadows)
        style.update(extra)
        style.update(_radius(node))
        if node.get("clipsContent") and parent is not None:
            style["overflow"] = "hidden"

        component = self.component_info(node) if kind == "INSTANCE" else None
        if component:
            out["component"] = {key: component[key] for key in ("key", "name", "set", "props")}
            entry = self.report.instances.setdefault(
                component["key"] or component["id"],
                {"key": component["key"], "id": component["id"], "name": component["set"] or component["name"], "remote": component["remote"], "count": 0},
            )
            entry["count"] += 1
        role = None if in_control else self._role(node, component)
        if role:
            out["role"] = role
            if role == "input":
                out["input"] = self._input_parts(node)

        children = [child for child in node.get("children") or [] if isinstance(child, dict)]
        if _is_auto_layout(node):
            style.update(_container_style(node))
            if any(child.get("layoutPositioning") == "ABSOLUTE" for child in children):
                style["position"] = style.get("position", "relative")
        elif children:
            style.setdefault("position", "relative")
            if parent is None and not style.get("minHeight"):
                style["minHeight"] = _px(box["height"])
            visible_children = [child for child in children if child.get("visible", True) is not False]
            if len(visible_children) >= 2 and kind not in ("GROUP", "BOOLEAN_OPERATION"):
                self.report.absolute_zones.append({"screen": self.screen_name, "node": str(node.get("id")), "name": out["name"]})
            if kind == "GROUP" or kind == "BOOLEAN_OPERATION":
                pass
        if parent is None:
            style.pop("overflow", None)
        out["style"] = style
        converted = [self.convert(child, node, in_control or role in ("input", "checkbox")) for child in children]
        out["children"] = [child for child in converted if child]
        return out


def convert_screen(converter: Converter, frame: dict[str, Any]) -> dict[str, Any]:
    converter.screen_name = str(frame.get("name") or "")
    root = converter.convert(frame) or {"id": str(frame.get("id")), "type": "box", "style": {}, "children": []}
    return root


# --- What the model needs: a compact outline of a screen, and its repeated groups ---


def repeat_groups(root: dict[str, Any]) -> list[dict[str, Any]]:
    """Containers whose children repeat the same component (rows of a list, cards…)."""
    groups = []

    def visit(node: dict[str, Any]) -> None:
        children = node.get("children") or []
        by_component: dict[str, list[dict[str, Any]]] = {}
        for child in children:
            component = child.get("component")
            signature = (component or {}).get("key") or (component or {}).get("name")
            if not signature and child.get("type") == "box" and child.get("children"):
                signature = "frame:" + normalize(child.get("name", ""))
            if signature:
                by_component.setdefault(signature, []).append(child)
        for items in by_component.values():
            if len(items) >= 2:
                template = items[0]
                texts = [
                    {"id": text["id"], "name": text.get("name", ""), "text": text.get("text", "")[:80]}
                    for text in iter_nodes(template)
                    if text.get("type") == "text"
                ]
                groups.append({"container": node["id"], "items": [item["id"] for item in items], "template": template["id"], "texts": texts})
                break
        for child in children:
            visit(child)

    visit(root)
    return groups


def outline(root: dict[str, Any], max_lines: int = 220) -> str:
    """One line per meaningful layer: what the model reads instead of the full JSON."""
    lines: list[str] = []

    def visit(node: dict[str, Any], depth: int) -> None:
        if len(lines) >= max_lines:
            return
        component = node.get("component")
        role = node.get("role")
        kind = node.get("type")
        meaningful = kind == "text" or component or role or node.get("nav")
        if meaningful:
            parts = [f"{'  ' * depth}[{node['id']}]"]
            if role:
                parts.append(role.upper())
            elif kind == "text":
                parts.append("TEXTE")
            if component:
                parts.append(f"composant « {component.get('set') or component.get('name')} »")
            if kind == "text":
                parts.append(f"« {node.get('text', '')[:70]} »")
            else:
                parts.append(f"calque « {node.get('name', '')} »")
            if role == "input":
                info = node.get("input") or {}
                if info.get("label"):
                    parts.append(f"libellé « {info['label'][:50]} »")
                if info.get("placeholder"):
                    parts.append(f"exemple « {info['placeholder'][:50]} »")
            lines.append(" ".join(parts))
        if role in ("input", "checkbox"):
            return
        for child in node.get("children") or []:
            visit(child, depth + (1 if meaningful else 0))

    visit(root, 0)
    if len(lines) >= max_lines:
        lines.append("[…] (écran tronqué)")
    return "\n".join(lines)
