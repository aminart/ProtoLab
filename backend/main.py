"""HTTP API of ProtoLab, and the compiled interface (frontend/dist) served from the same process."""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import project_store as store
from ai_enrichment import analyze_context, enrich_screen
from app_info import APP_ID, APP_NAME, VERSION
from app_paths import frontend_dist_dir
from export_html import PlayerMissing, build_html
from library_reader import LibraryError, library_summary, merge_library, read_library
from openai_client import ModelAnswerError, get_missing_settings, get_model_name, is_custom_configured
from prototype_builder import Assembly, assemble, build_model, figma_summary, spec_title
from settings_api import router as settings_router

FRONTEND_DIST = frontend_dist_dir()

app = FastAPI(title="ProtoLab API", version=VERSION)
app.include_router(settings_router)


# --- Helpers ---------------------------------------------------------------------------


def _project(project_id: str) -> dict[str, Any]:
    try:
        return store.load_project(project_id)
    except store.NotFound as exc:
        raise HTTPException(status_code=404, detail="Projet introuvable.") from exc


def _read_upload(file: UploadFile) -> str:
    raw = file.file.read()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _read_json_upload(file: UploadFile) -> Any:
    try:
        return json.loads(_read_upload(file))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"« {file.filename} » n’est pas un JSON valide ({exc}).") from exc


def _assembly(project: dict[str, Any]) -> Assembly:
    context = store.read_text(project["id"], "context.md") if project.get("context") else None
    figma = store.read_figma(project["id"]) if project.get("figma") else None
    return assemble(project, context, store.read_specs(project), figma, store.load_global_library())


def _require_llm() -> None:
    if not is_custom_configured():
        raise HTTPException(
            status_code=503,
            detail=f"Paramètres de connexion incomplets : {', '.join(get_missing_settings())}. Renseignez-les dans Paramètres.",
        )


def _model_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ModelAnswerError):
        return HTTPException(status_code=502, detail=f"Réponse du modèle inexploitable : {exc}")
    name = type(exc).__name__
    if "Timeout" in name:
        return HTTPException(status_code=504, detail="Le modèle n’a pas répondu à temps. Réessayez, ou augmentez le délai dans Paramètres.")
    return HTTPException(status_code=502, detail=f"Échec de l’appel au modèle : {exc}")


def _safe_filename(title: str, fallback: str) -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z0-9]+", "-", ascii_title).strip("-").lower()[:60] or fallback


def _overview(project: dict[str, Any]) -> dict[str, Any]:
    result = _assembly(project)
    context = None
    if project.get("context"):
        document = result.context
        context = {
            **project["context"],
            "title": document.title if document else "",
            "sections": [section.title for section in document.sections if section.title and section.level <= 2] if document else [],
            "diagrams": len(document.mermaid) if document else 0,
            "screens": len(result.structure["screens"]),
            "modules": len([m for m in result.structure["modules"] if m["id"] != "_autres"]),
            "error": result.mermaid_error,
        }
    assigned = {screen["spec"]: screen["name"] for screen in result.screens if screen["spec"]}
    return {
        "id": project["id"],
        "name": project["name"],
        "updated_at": project.get("updated_at"),
        "context": context,
        "specs": [{**spec, "screen": assigned.get(spec["id"])} for spec in project.get("specs") or []],
        "figma": {**project["figma"], **figma_summary(result)} if project.get("figma") else None,
        "library": {**library_summary(project.get("library")), "inventory": result.inventory.get("counts")} if project.get("library") else None,
        "global_library": library_summary(store.load_global_library()) if store.load_global_library() else None,
        "analysis": _analysis_summary(project),
        "versions": project.get("versions") or [],
    }


def _analysis_summary(project: dict[str, Any]) -> dict[str, Any] | None:
    analysis = project.get("analysis")
    if not analysis:
        return None
    return {
        "at": analysis.get("at"),
        "entities": [{"name": e["name"], "label": e["label"], "fields": len(e["fields"]), "records": len((analysis.get("seed") or {}).get(e["name"]) or [])} for e in analysis.get("entities") or []],
        "profiles": analysis.get("profiles") or [],
        "warnings": analysis.get("warnings") or [],
    }


# --- Portal contract and settings ---------------------------------------------------------


@app.get("/health")
def portal_health() -> dict[str, str]:
    """Portal contract: answers as soon as the server is up, whatever the AI settings."""
    return {"status": "ok", "app": APP_ID, "name": APP_NAME, "version": VERSION}


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"configured": is_custom_configured(), "missing": get_missing_settings(), "model": get_model_name(), "version": VERSION}


# --- Projects ------------------------------------------------------------------------------


class ProjectPayload(BaseModel):
    name: str = ""


@app.get("/api/projects")
def projects() -> list[dict[str, Any]]:
    return store.list_projects()


@app.post("/api/projects")
def create_project(payload: ProjectPayload) -> dict[str, Any]:
    return _overview(store.create_project(payload.name))


@app.get("/api/projects/{project_id}")
def project_overview(project_id: str) -> dict[str, Any]:
    return _overview(_project(project_id))


@app.patch("/api/projects/{project_id}")
def rename_project(project_id: str, payload: ProjectPayload) -> dict[str, Any]:
    project = _project(project_id)
    project["name"] = payload.name.strip() or project["name"]
    store.save_project(project)
    return _overview(project)


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str) -> dict[str, bool]:
    try:
        store.delete_project(project_id)
    except store.NotFound as exc:
        raise HTTPException(status_code=404, detail="Projet introuvable.") from exc
    return {"ok": True}


# --- Sources ---------------------------------------------------------------------------------


@app.post("/api/projects/{project_id}/context")
def upload_context(project_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    project = _project(project_id)
    markdown = _read_upload(file)
    if not markdown.strip():
        raise HTTPException(status_code=422, detail="Le document de contexte est vide.")
    store.write_text(project_id, "context.md", markdown)
    project["context"] = {"name": file.filename or "contexte.md", "imported_at": store.now()}
    store.save_project(project)
    return _overview(project)


@app.delete("/api/projects/{project_id}/context")
def delete_context(project_id: str) -> dict[str, Any]:
    project = _project(project_id)
    store.delete_file(project_id, "context.md")
    project["context"] = None
    store.save_project(project)
    return _overview(project)


@app.post("/api/projects/{project_id}/specs")
def upload_spec(project_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    project = _project(project_id)
    markdown = _read_upload(file)
    name = file.filename or "spec.md"
    existing = next((spec for spec in project["specs"] if spec["name"] == name), None)
    spec = existing or {"id": store.new_id(), "name": name}
    spec.update({"title": spec_title(markdown, name.rsplit(".", 1)[0]), "imported_at": store.now()})
    store.write_text(project_id, f"specs/{spec['id']}.md", markdown)
    if not existing:
        project["specs"].append(spec)
    store.save_project(project)
    return _overview(project)


@app.delete("/api/projects/{project_id}/specs/{spec_id}")
def delete_spec(project_id: str, spec_id: str) -> dict[str, Any]:
    project = _project(project_id)
    project["specs"] = [spec for spec in project["specs"] if spec["id"] != spec_id]
    if store.SAFE_ID.match(spec_id):
        store.delete_file(project_id, f"specs/{spec_id}.md")
    store.save_project(project)
    return _overview(project)


@app.post("/api/projects/{project_id}/figma")
def upload_figma(project_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    project = _project(project_id)
    payload = _read_json_upload(file)
    from figma_reader import FigmaError, default_page_id, list_pages, load_figma

    try:
        pages = list_pages(load_figma(payload))
    except FigmaError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not any(page["frames"] for page in pages):
        raise HTTPException(status_code=422, detail="Aucune frame trouvée dans ce JSON : exportez la page qui contient les écrans.")
    store.write_figma(project_id, payload)
    previous_page = (project.get("figma") or {}).get("page_id")
    page_id = previous_page if any(page["id"] == previous_page for page in pages) else default_page_id(pages)
    project["figma"] = {"name": file.filename or "maquette.json", "imported_at": store.now(), "page_id": page_id}
    store.save_project(project)
    return _overview(project)


class PagePayload(BaseModel):
    page_id: str


@app.put("/api/projects/{project_id}/figma/page")
def choose_page(project_id: str, payload: PagePayload) -> dict[str, Any]:
    project = _project(project_id)
    if not project.get("figma"):
        raise HTTPException(status_code=404, detail="Aucune maquette importée.")
    project["figma"]["page_id"] = payload.page_id
    store.save_project(project)
    return _overview(project)


@app.delete("/api/projects/{project_id}/figma")
def delete_figma(project_id: str) -> dict[str, Any]:
    project = _project(project_id)
    store.delete_file(project_id, "figma.json")
    project["figma"] = None
    store.save_project(project)
    return _overview(project)


@app.post("/api/projects/{project_id}/library")
def upload_project_library(project_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    project = _project(project_id)
    try:
        imported = read_library(_read_json_upload(file), file.filename or "bibliotheque.json")
    except LibraryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    project["library"] = merge_library(project.get("library"), imported)
    store.save_project(project)
    return _overview(project)


@app.delete("/api/projects/{project_id}/library")
def delete_project_library(project_id: str) -> dict[str, Any]:
    project = _project(project_id)
    project["library"] = None
    store.save_project(project)
    return _overview(project)


# --- Global library ----------------------------------------------------------------------------


@app.get("/api/libraries/global")
def global_library() -> dict[str, Any] | None:
    library = store.load_global_library()
    if not library:
        return None
    return {**library_summary(library), "components_list": [{"name": c["set"] or c["name"], "key": c["key"]} for c in library.get("components") or []][:500],
            "tokens_list": (library.get("tokens") or library.get("style_tokens") or [])[:500]}


@app.post("/api/libraries/global")
def upload_global_library(file: UploadFile = File(...)) -> dict[str, Any] | None:
    try:
        imported = read_library(_read_json_upload(file), file.filename or "design-system.json")
    except LibraryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    store.save_global_library(merge_library(store.load_global_library(), imported))
    return global_library()


@app.delete("/api/libraries/global")
def delete_global_library() -> None:
    store.save_global_library(None)


# --- Structure -----------------------------------------------------------------------------------


@app.get("/api/projects/{project_id}/structure")
def structure(project_id: str) -> dict[str, Any]:
    project = _project(project_id)
    result = _assembly(project)
    behaviors = project.get("behaviors") or {}
    return {
        "modules": result.modules,
        "screens": [
            {**screen, "frame_name": (result.frames.get(screen["frame"] or "") or {}).get("name"),
             "enriched": behaviors.get(screen["id"], {}).get("at"),
             "behavior_counts": {key: len(behaviors.get(screen["id"], {}).get(key) or {}) for key in ("fields", "actions", "lists", "bindings")}}
            for screen in result.screens
        ],
        "start": result.start,
        "warnings": result.warnings,
        "frames": [{"id": frame_id, "name": frame["name"]} for frame_id, frame in result.frames.items()],
        "specs": [{"id": spec["id"], "name": spec["name"], "title": spec.get("title")} for spec in project.get("specs") or []],
        "inventory": result.inventory,
        "mermaid_error": result.mermaid_error,
        "has_context": bool(project.get("context")),
        "has_figma": bool(project.get("figma")),
        "analysis": _analysis_summary(project),
        "decisions": result.structure.get("decisions") or [],
    }


class ScreenPayload(BaseModel):
    # Absent: unchanged. "auto": automatic choice. "none": nothing. Otherwise an id.
    frame: str | None = None
    spec: str | None = None
    excluded: bool | None = None
    name: str | None = None


@app.put("/api/projects/{project_id}/screens/{screen_id}")
def update_screen(project_id: str, screen_id: str, payload: ScreenPayload) -> dict[str, Any]:
    project = _project(project_id)
    overrides = project.setdefault("overrides", {}).setdefault("screens", {})
    override = overrides.setdefault(screen_id, {})
    for key in ("frame", "spec"):
        value = getattr(payload, key)
        if value == "auto":
            override.pop(key, None)
        elif value is not None:
            override[key] = value
    if payload.excluded is not None:
        override["excluded"] = payload.excluded
    if payload.name is not None:
        if payload.name.strip():
            override["name"] = payload.name.strip()
        else:
            override.pop("name", None)
    if not override:
        overrides.pop(screen_id, None)
    store.save_project(project)
    return structure(project_id)


class StartPayload(BaseModel):
    screen: str | None = None


@app.put("/api/projects/{project_id}/start")
def update_start(project_id: str, payload: StartPayload) -> dict[str, Any]:
    project = _project(project_id)
    project.setdefault("overrides", {})["start"] = payload.screen
    store.save_project(project)
    return structure(project_id)


# --- Model: data and behaviours -------------------------------------------------------------------


@app.post("/api/projects/{project_id}/analyze")
def analyze(project_id: str) -> dict[str, Any]:
    project = _project(project_id)
    _require_llm()
    result = _assembly(project)
    if result.context is None:
        raise HTTPException(status_code=400, detail="Importez d’abord le document de contexte.")
    try:
        analysis, warnings = analyze_context(result.context, [s for s in result.screens if not s["excluded"]])
    except Exception as exc:  # noqa: BLE001 - every failure of the model is reported the same way
        raise _model_error(exc) from exc
    project["analysis"] = {**analysis, "warnings": warnings, "at": store.now()}
    store.save_project(project)
    return {"analysis": _analysis_summary(project)}


@app.post("/api/projects/{project_id}/screens/{screen_id}/enrich")
def enrich(project_id: str, screen_id: str) -> dict[str, Any]:
    project = _project(project_id)
    _require_llm()
    result = _assembly(project)
    screen = next((item for item in result.screens if item["id"] == screen_id and not item["excluded"]), None)
    if screen is None:
        raise HTTPException(status_code=404, detail="Écran introuvable.")
    root = result.roots.get(screen["frame"] or "")
    if root is None:
        raise HTTPException(status_code=400, detail="Cet écran n’a pas de maquette : il est généré en version simple.")
    specs = store.read_specs(project)
    entities = (project.get("analysis") or {}).get("entities") or []
    screens = [{"id": item["id"], "name": item["name"]} for item in result.screens if not item["excluded"]]
    excerpt = ""
    if result.context and not screen["spec"]:
        excerpt = result.context.text_without_diagrams(6000)
    try:
        behaviors, dropped = enrich_screen(screen, root, specs.get(screen["spec"] or ""), entities, screens, excerpt)
    except Exception as exc:  # noqa: BLE001
        raise _model_error(exc) from exc
    project.setdefault("behaviors", {})[screen_id] = {**behaviors, "dropped": dropped, "at": store.now()}
    store.save_project(project)
    return {"screen": screen_id, "counts": {key: len(value) for key, value in behaviors.items()}, "dropped": dropped}


@app.delete("/api/projects/{project_id}/screens/{screen_id}/behaviors")
def clear_behaviors(project_id: str, screen_id: str) -> dict[str, Any]:
    project = _project(project_id)
    (project.get("behaviors") or {}).pop(screen_id, None)
    store.save_project(project)
    return structure(project_id)


# --- Prototype, versions, export ---------------------------------------------------------------------


@app.get("/api/projects/{project_id}/prototype")
def prototype(project_id: str) -> dict[str, Any]:
    project = _project(project_id)
    return build_model(project, _assembly(project), store.load_global_library())


class VersionPayload(BaseModel):
    label: str = ""


@app.post("/api/projects/{project_id}/versions")
def freeze(project_id: str, payload: VersionPayload) -> dict[str, Any]:
    project = _project(project_id)
    model = build_model(project, _assembly(project), store.load_global_library())
    if not model["screens"]:
        raise HTTPException(status_code=400, detail="Le prototype n’a aucun écran à figer.")
    version = {
        "id": store.new_id(),
        "label": payload.label.strip() or f"Version {len(project.get('versions') or []) + 1}",
        "created_at": store.now(),
        "screens": len(model["screens"]),
    }
    model["version"] = version
    store.save_version(project_id, version["id"], model)
    project.setdefault("versions", []).insert(0, version)
    store.save_project(project)
    return version


@app.get("/api/projects/{project_id}/versions/{version_id}")
def get_version(project_id: str, version_id: str) -> dict[str, Any]:
    _project(project_id)
    try:
        return store.load_version(project_id, version_id)
    except store.NotFound as exc:
        raise HTTPException(status_code=404, detail="Version introuvable.") from exc


@app.delete("/api/projects/{project_id}/versions/{version_id}")
def delete_version(project_id: str, version_id: str) -> list[dict[str, Any]]:
    project = _project(project_id)
    project["versions"] = [item for item in project.get("versions") or [] if item["id"] != version_id]
    store.delete_version(project_id, version_id)
    store.save_project(project)
    return project["versions"]


@app.get("/api/projects/{project_id}/export")
def export(project_id: str, version: str | None = None) -> Response:
    project = _project(project_id)
    if version:
        model = get_version(project_id, version)
        label = model.get("version", {}).get("label", "")
    else:
        model = build_model(project, _assembly(project), store.load_global_library())
        label = "brouillon"
    title = f"{project['name']} – {label}" if label else project["name"]
    try:
        content = build_html(model, title)
    except PlayerMissing as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    filename = f"{_safe_filename(project['name'], 'prototype')}-{_safe_filename(label, 'version')}.html"
    return Response(content=content, media_type="text/html; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# --- Interface ----------------------------------------------------------------------------------------

if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Route inconnue.")
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file() and FRONTEND_DIST in candidate.resolve().parents:
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
