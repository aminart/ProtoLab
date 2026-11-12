"""Reads a Mermaid flowchart (the flow produced by SpecGen), without the model.

Convention, kept by SpecGen's prompts:
    rectangle  id[Écran]          a screen
    losange    id{Montant > 500 ?} a decision
    arrondi    id(Envoi du mail)   a system action (also stadium, subroutine, cylinder, hexagon…)
    cercle     id((Début))         a start or an end
    subgraph   module              a module of the app
A `class x,y screen` (or `:::screen`) line overrides the shape: screen, decision, action, terminal.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any

from context_reader import normalize

NODE_ID = re.compile(r"[^\W\d][\w]*(?:-(?![-.>=])\w+)*|\d[\w]*(?:-(?![-.>=])\w+)*", re.UNICODE)
EDGE = re.compile(
    r"""\s*(?:
        (?P<a1><?(?:-{2,}|={2,}|-?\.+-?)[>ox]?)\s*\|(?P<l1>[^|]*)\|
      | (?P<open><?(?:--|==|-\.))\s+(?P<l2>[^|]+?)\s+(?P<close>-{2,}[>ox-]|={2,}[>=]|\.-+>?)
      | (?P<a3><?(?:-{2,}[>ox]?|={2,}[>=ox]?|-?\.+-*>?))
    )\s*""",
    re.X,
)
# Opening sequences, longest first, with their closing sequence and the kind of node they draw.
SHAPES: list[tuple[str, tuple[str, ...], str]] = [
    ("(((", (")))",), "terminal"),
    ("((", ("))",), "terminal"),
    ("([", ("])",), "action"),
    ("[[", ("]]",), "action"),
    ("[(", (")]",), "action"),
    ("{{", ("}}",), "action"),
    ("[/", ("/]", "\\]"), "action"),
    ("[\\", ("\\]", "/]"), "action"),
    ("(", (")",), "action"),
    ("[", ("]",), "screen"),
    ("{", ("}",), "decision"),
    (">", ("]",), "action"),
]
CLASS_KINDS = {
    "screen": "screen", "ecran": "screen", "page": "screen", "view": "screen", "vue": "screen",
    "decision": "decision", "condition": "decision", "choice": "decision", "choix": "decision",
    "action": "action", "system": "action", "systeme": "action", "process": "action", "traitement": "action",
    "api": "action", "data": "action", "donnees": "action", "service": "action",
    "start": "terminal", "end": "terminal", "debut": "terminal", "fin": "terminal", "terminal": "terminal",
}
DIRECTIVE = re.compile(r"^(classDef|style|linkStyle|click|direction|accTitle|accDescr|title)\b", re.I)


class MermaidError(ValueError):
    """The block is not a flowchart this reader understands."""


@dataclass
class MermaidNode:
    id: str
    label: str
    kind: str
    subgraph: str | None = None
    explicit_kind: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "kind": self.kind, "subgraph": self.subgraph}


@dataclass
class MermaidGraph:
    direction: str = "TD"
    nodes: dict[str, MermaidNode] = field(default_factory=dict)
    edges: list[dict[str, Any]] = field(default_factory=list)
    subgraphs: dict[str, dict[str, Any]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "nodes": [node.as_dict() for node in self.nodes.values()],
            "edges": self.edges,
            "subgraphs": list(self.subgraphs.values()),
            "warnings": self.warnings,
        }


def clean_label(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'`":
        text = text[1:-1]
    text = re.sub(r"#(\w+);", lambda m: {"quot": '"', "amp": "&", "lt": "<", "gt": ">"}.get(m.group(1), m.group(0)), text)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"fa:fa-[\w-]+", "", text)
    text = text.replace("**", "").replace("__", "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _split_statements(line: str) -> list[str]:
    """Splits on `;` outside quotes and brackets."""
    parts, depth, quote, start = [], 0, "", 0
    for index, char in enumerate(line):
        if quote:
            quote = "" if char == quote else quote
        elif char == '"':
            quote = char
        elif char in "[({":
            depth += 1
        elif char in "])}":
            depth = max(0, depth - 1)
        elif char == ";" and depth == 0:
            parts.append(line[start:index])
            start = index + 1
    parts.append(line[start:])
    return [part.strip() for part in parts if part.strip()]


class _Parser:
    def __init__(self) -> None:
        self.graph = MermaidGraph()
        self.stack: list[str] = []

    # --- nodes ------------------------------------------------------------------

    def _read_shape(self, text: str, pos: int) -> tuple[str | None, str | None, int]:
        for opening, closings, kind in SHAPES:
            if not text.startswith(opening, pos):
                continue
            start = pos + len(opening)
            search_from = start
            if start < len(text) and text[start] == '"':
                closing_quote = text.find('"', start + 1)
                if closing_quote > 0:
                    search_from = closing_quote + 1
            found = [(text.find(closing, search_from), closing) for closing in closings]
            found = [(index, closing) for index, closing in found if index >= 0]
            if not found:
                continue
            index, closing = min(found)
            return kind, text[start:index], index + len(closing)
        return None, None, pos

    def _read_node(self, text: str, pos: int) -> tuple[str | None, int]:
        match = NODE_ID.match(text, pos)
        if not match:
            return None, pos
        node_id, pos = match.group(0), match.end()
        kind, label, pos = self._read_shape(text, pos)
        existing = self.graph.nodes.get(node_id)
        if existing is not None and existing.subgraph is None and self.stack:
            # Mentioned again inside a subgraph: Mermaid draws it there.
            existing.subgraph = self.stack[-1]
        css_class = None
        class_match = re.match(r":::([\w-]+)", text[pos:])
        if class_match:
            css_class, pos = class_match.group(1), pos + class_match.end()
        self._declare(node_id, kind, label, css_class)
        return node_id, pos

    def _declare(self, node_id: str, kind: str | None, label: str | None, css_class: str | None) -> None:
        if node_id in self.graph.subgraphs:
            return
        node = self.graph.nodes.get(node_id)
        if node is None:
            node = MermaidNode(id=node_id, label=node_id, kind=kind or "screen", subgraph=self.stack[-1] if self.stack else None)
            self.graph.nodes[node_id] = node
        if label is not None:
            node.label = clean_label(label) or node_id
            if not node.explicit_kind and kind:
                node.kind = kind
        if css_class:
            self._apply_class(node, css_class)

    def _apply_class(self, node: MermaidNode, css_class: str) -> None:
        kind = CLASS_KINDS.get(normalize(css_class).replace(" ", ""))
        if kind:
            node.kind, node.explicit_kind = kind, True

    # --- statements ---------------------------------------------------------------

    def statement(self, text: str) -> None:
        lowered = text.lower()
        if lowered.startswith("subgraph"):
            self._open_subgraph(text[len("subgraph"):].strip())
            return
        if lowered == "end":
            if self.stack:
                self.stack.pop()
            return
        if lowered.startswith("class "):
            parts = text.split()
            if len(parts) >= 3:
                for node_id in parts[1].split(","):
                    if node_id in self.graph.nodes:
                        self._apply_class(self.graph.nodes[node_id], parts[2])
            return
        if DIRECTIVE.match(text) or text.startswith("%%"):
            return
        self._chain(text)

    def _open_subgraph(self, rest: str) -> None:
        match = re.match(r'^([\w-]+)\s*\[\s*(.*?)\s*\]\s*$', rest)
        if match:
            sub_id, title = match.group(1), clean_label(match.group(2))
        elif rest.startswith('"'):
            title = clean_label(rest)
            sub_id = normalize(title).replace(" ", "_") or f"module_{len(self.graph.subgraphs) + 1}"
        elif re.fullmatch(r"[\w-]+", rest):
            sub_id = title = rest
        else:
            title = clean_label(rest)
            sub_id = normalize(title).replace(" ", "_") or f"module_{len(self.graph.subgraphs) + 1}"
        self.graph.subgraphs[sub_id] = {"id": sub_id, "title": title or sub_id, "parent": self.stack[-1] if self.stack else None}
        self.stack.append(sub_id)

    def _group(self, text: str, pos: int) -> tuple[list[str], int]:
        ids: list[str] = []
        while True:
            node_id, new_pos = self._read_node(text, pos)
            if node_id is None:
                return ids, pos
            ids.append(node_id)
            pos = new_pos
            amp = re.match(r"\s*&\s*", text[pos:])
            if not amp:
                return ids, pos
            pos += amp.end()

    def _chain(self, text: str) -> None:
        pos = len(text) - len(text.lstrip())
        sources, pos = self._group(text, pos)
        if not sources:
            self.graph.warnings.append(f"Ligne ignorée : {text[:80]}")
            return
        while pos < len(text):
            edge = EDGE.match(text, pos)
            if not edge or edge.end() == pos:
                rest = text[pos:].strip()
                if rest:
                    self.graph.warnings.append(f"Fin de ligne ignorée : {rest[:80]}")
                return
            label = edge.group("l1") if edge.group("l1") is not None else edge.group("l2")
            arrow = edge.group("a1") or edge.group("a3") or f"{edge.group('open')}{edge.group('close')}"
            targets, new_pos = self._group(text, edge.end())
            if not targets:
                self.graph.warnings.append(f"Lien sans destination : {text[:80]}")
                return
            for source in sources:
                for target in targets:
                    self.graph.edges.append({
                        "source": source,
                        "target": target,
                        "label": clean_label(label) if label else "",
                        "dotted": "." in arrow,
                        "bidirectional": arrow.startswith("<"),
                    })
            sources, pos = targets, new_pos


def read_mermaid(code: str) -> MermaidGraph:
    lines = [line.strip() for line in code.replace("\r\n", "\n").split("\n")]
    lines = [line for line in lines if line and not line.startswith("%%")]
    if not lines:
        raise MermaidError("Le diagramme est vide.")
    header = re.match(r"^(flowchart|graph)\s*(TB|TD|BT|RL|LR)?\s*;?\s*(.*)$", lines[0], re.I)
    if not header:
        raise MermaidError("Seuls les diagrammes « flowchart » ou « graph » décrivent la structure de l’app.")
    parser = _Parser()
    parser.graph.direction = (header.group(2) or "TD").upper()
    body = [header.group(3)] if header.group(3) else []
    for line in body + lines[1:]:
        for statement in _split_statements(line):
            parser.statement(statement)
    return parser.graph
