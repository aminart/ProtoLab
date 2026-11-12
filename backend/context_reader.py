"""Reads the context document exported by SpecGen (Markdown), without the model.

The document is cut into sections by its headings, and its ```mermaid blocks are extracted.
The main diagram (the structure of the app) is the one placed under a heading that names the
structure or the flow; otherwise the largest flowchart.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE = re.compile(r"^(`{3,}|~{3,})\s*([\w-]*)")
STRUCTURE_HINTS = ("structure", "arborescence", "flow", "flux", "parcours", "navigation", "sitemap", "plan de l")


def normalize(text: str) -> str:
    """Lower case, no accents, single spaces: used to compare names."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()


@dataclass
class Section:
    title: str
    level: int
    path: list[str]
    text: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"title": self.title, "level": self.level, "path": self.path, "chars": len(self.text)}


@dataclass
class MermaidBlock:
    code: str
    section_path: list[str]
    index: int

    @property
    def is_flowchart(self) -> bool:
        first = next((line.strip() for line in self.code.splitlines() if line.strip() and not line.strip().startswith("%%")), "")
        return bool(re.match(r"^(flowchart|graph)\b", first, re.I))


@dataclass
class ContextDocument:
    title: str
    sections: list[Section] = field(default_factory=list)
    mermaid: list[MermaidBlock] = field(default_factory=list)

    def main_diagram(self) -> MermaidBlock | None:
        flowcharts = [block for block in self.mermaid if block.is_flowchart]
        if not flowcharts:
            return None
        for block in flowcharts:
            if any(hint in normalize(" ".join(block.section_path)) for hint in STRUCTURE_HINTS):
                return block
        return max(flowcharts, key=lambda block: len(block.code))

    def text_without_diagrams(self, max_chars: int | None = None) -> str:
        parts = []
        for section in self.sections:
            heading = "#" * section.level + " " + section.title if section.level else ""
            body = section.text.strip()
            if heading or body:
                parts.append("\n".join(part for part in (heading, body) if part))
        text = "\n\n".join(parts)
        return text if max_chars is None or len(text) <= max_chars else text[:max_chars] + "\n[…]"


def read_context(markdown: str) -> ContextDocument:
    lines = markdown.replace("\r\n", "\n").split("\n")
    document = ContextDocument(title="")
    current = Section(title="", level=0, path=[])
    stack: list[tuple[int, str]] = []
    fence: str | None = None
    fence_lang = ""
    fence_lines: list[str] = []
    body: list[str] = []

    def close_section() -> None:
        current.text = "\n".join(body).strip()
        if current.title or current.text:
            document.sections.append(current)

    for line in lines:
        if fence is not None:
            if line.strip().startswith(fence):
                if fence_lang == "mermaid":
                    document.mermaid.append(MermaidBlock("\n".join(fence_lines), list(current.path), len(document.mermaid)))
                else:
                    body.extend([f"{fence}{fence_lang}", *fence_lines, fence])
                fence = None
                continue
            fence_lines.append(line)
            continue
        opening = FENCE.match(line.strip())
        if opening:
            fence, fence_lang, fence_lines = opening.group(1), opening.group(2).lower(), []
            continue
        heading = HEADING.match(line)
        if heading:
            close_section()
            level, title = len(heading.group(1)), heading.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            if level == 1 and not document.title:
                document.title = title
            current = Section(title=title, level=level, path=[name for _, name in stack])
            body = []
            continue
        body.append(line)
    close_section()
    return document
