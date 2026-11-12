"""File locations, valid both from sources and from the packaged .exe (PyInstaller)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "ProtoLab"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_dir() -> Path:
    """Read-only files shipped with the app (built frontend, prototype player)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


def app_dir() -> Path:
    """Folder the user sees: next to the .exe, or the repository root from sources."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def frontend_dist_dir() -> Path:
    if is_frozen():
        return resource_dir() / "frontend_dist"
    return app_dir() / "frontend" / "dist"


def player_bundle() -> Path:
    """Standalone prototype player (one JS file), inlined into the HTML exports."""
    if is_frozen():
        return resource_dir() / "player" / "protolab-player.js"
    return app_dir() / "frontend" / "dist-player" / "protolab-player.js"


def env_file() -> Path:
    return app_dir() / ".env"


def config_dir() -> Path:
    """Per-user writable folder holding the settings saved from the app."""
    override = os.getenv("PROTOLAB_CONFIG_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        return Path(os.getenv("APPDATA") or Path.home() / "AppData" / "Roaming") / APP_NAME
    return Path(os.getenv("XDG_CONFIG_HOME") or Path.home() / ".config") / APP_NAME.lower()
