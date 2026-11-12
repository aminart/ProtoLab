"""The prototype as one HTML file: the player and the frozen model, opened without the app."""
from __future__ import annotations

import html
import json
from typing import Any

from app_info import APP_NAME, VERSION
from app_paths import player_bundle


class PlayerMissing(RuntimeError):
    pass


def _script_safe(text: str) -> str:
    return text.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def build_html(model: dict[str, Any], title: str) -> str:
    try:
        bundle = player_bundle().read_text(encoding="utf-8")
    except OSError as exc:
        raise PlayerMissing("Le lecteur de prototype n’est pas compilé (npm run build dans frontend).") from exc
    data = _script_safe(json.dumps(model, ensure_ascii=False, separators=(",", ":")))
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="{APP_NAME} {VERSION}">
<title>{html.escape(title)}</title>
<style>html,body{{margin:0;min-height:100%;background:#E4E7EC}}</style>
</head>
<body>
<div id="protolab-player"></div>
<script>window.__PROTOLAB_MODEL__ = {data};</script>
<script>{_script_safe(bundle)}</script>
</body>
</html>
"""
