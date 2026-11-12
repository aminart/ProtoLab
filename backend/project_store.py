"""Projects and libraries, saved as files in the per-user settings folder.

    <config>/projects/<id>/project.json     sources, choices, what the model added, versions
    <config>/projects/<id>/context.md       document de contexte (SpecGen)
    <config>/projects/<id>/specs/<id>.md    specifications (SpecGen)
    <config>/projects/<id>/figma.json       maquette (JSON de l'API Figma)
    <config>/projects/<id>/versions/<id>.json   prototype figé
    <config>/libraries/global.json          design system global (composants + tokens)
Everything stays on this computer.
"""
from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app_paths import config_dir

SAFE_ID = re.compile(r"^[a-z0-9_-]{1,64}$")


class NotFound(LookupError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def _projects_dir() -> Path:
    return config_dir() / "projects"


def _project_dir(project_id: str) -> Path:
    if not SAFE_ID.match(project_id):
        raise NotFound(project_id)
    return _projects_dir() / project_id


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    temporary.replace(path)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


# --- Projects -----------------------------------------------------------------------


def list_projects() -> list[dict[str, Any]]:
    projects = []
    if _projects_dir().is_dir():
        for folder in _projects_dir().iterdir():
            try:
                project = _read_json(folder / "project.json")
            except (OSError, ValueError):
                continue
            projects.append({key: project.get(key) for key in ("id", "name", "created_at", "updated_at")})
    return sorted(projects, key=lambda project: project.get("updated_at") or "", reverse=True)


def create_project(name: str) -> dict[str, Any]:
    project = {
        "id": new_id(),
        "name": name.strip() or "Nouveau projet",
        "created_at": now(),
        "updated_at": now(),
        "context": None,
        "specs": [],
        "figma": None,
        "library": None,
        "overrides": {"screens": {}, "start": None},
        "analysis": None,
        "behaviors": {},
        "versions": [],
    }
    save_project(project)
    return project


def load_project(project_id: str) -> dict[str, Any]:
    try:
        return _read_json(_project_dir(project_id) / "project.json")
    except (OSError, ValueError) as exc:
        raise NotFound(project_id) from exc


def save_project(project: dict[str, Any]) -> None:
    project["updated_at"] = now()
    _write_json(_project_dir(project["id"]) / "project.json", project)


def delete_project(project_id: str) -> None:
    folder = _project_dir(project_id)
    if not folder.is_dir():
        raise NotFound(project_id)
    shutil.rmtree(folder)


def write_text(project_id: str, relative: str, content: str) -> None:
    path = _project_dir(project_id) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_text(project_id: str, relative: str) -> str | None:
    try:
        return (_project_dir(project_id) / relative).read_text(encoding="utf-8")
    except OSError:
        return None


def delete_file(project_id: str, relative: str) -> None:
    (_project_dir(project_id) / relative).unlink(missing_ok=True)


def write_figma(project_id: str, payload: Any) -> None:
    _write_json(_project_dir(project_id) / "figma.json", payload)


def read_figma(project_id: str) -> Any:
    path = _project_dir(project_id) / "figma.json"
    return _read_json(path) if path.is_file() else None


def read_specs(project: dict[str, Any]) -> dict[str, str]:
    specs = {}
    for spec in project.get("specs") or []:
        content = read_text(project["id"], f"specs/{spec['id']}.md")
        if content is not None:
            specs[spec["id"]] = content
    return specs


# --- Frozen versions ---------------------------------------------------------------------


def save_version(project_id: str, version_id: str, model: dict[str, Any]) -> None:
    _write_json(_project_dir(project_id) / "versions" / f"{version_id}.json", model)


def load_version(project_id: str, version_id: str) -> dict[str, Any]:
    if not SAFE_ID.match(version_id):
        raise NotFound(version_id)
    try:
        return _read_json(_project_dir(project_id) / "versions" / f"{version_id}.json")
    except (OSError, ValueError) as exc:
        raise NotFound(version_id) from exc


def delete_version(project_id: str, version_id: str) -> None:
    if SAFE_ID.match(version_id):
        (_project_dir(project_id) / "versions" / f"{version_id}.json").unlink(missing_ok=True)


# --- Global library ------------------------------------------------------------------------


def _global_library_file() -> Path:
    return config_dir() / "libraries" / "global.json"


def load_global_library() -> dict[str, Any] | None:
    try:
        return _read_json(_global_library_file())
    except (OSError, ValueError):
        return None


def save_global_library(library: dict[str, Any] | None) -> None:
    if library is None:
        _global_library_file().unlink(missing_ok=True)
    else:
        _write_json(_global_library_file(), library)
