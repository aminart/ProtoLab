"""Endpoints of the connection settings screen."""
from __future__ import annotations

import json
import ssl
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

import httpx
import openai
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from openai_client import build_client, get_max_output_tokens
from settings_store import (
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
    clear_settings,
    get_effective_settings,
    public_settings,
    save_settings,
    save_test_result,
    store_certificate,
)

router = APIRouter(prefix="/api/settings")

TEST_TIMEOUT_SECONDS = 30.0


class SettingsPayload(BaseModel):
    api_base: str = ""
    # None keeps the stored key.
    api_key: str | None = None
    model: str = DEFAULT_MODEL
    timeout: float = Field(default=DEFAULT_TIMEOUT_SECONDS, ge=10, le=1800)


@router.get("")
def read_settings() -> dict[str, Any]:
    return public_settings()


@router.put("")
def update_settings(payload: SettingsPayload) -> dict[str, Any]:
    save_settings(payload.api_base, payload.api_key, payload.model, payload.timeout)
    return public_settings()


@router.delete("")
def delete_settings() -> dict[str, Any]:
    clear_settings()
    return public_settings()


@router.post("/certificate")
def upload_certificate(file: UploadFile = File(...)) -> dict[str, Any]:
    try:
        store_certificate(file.filename or "certificat.crt", file.file.read())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return public_settings()


def _is_certificate_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(current):
            return True
        current = current.__cause__ or current.__context__
    return False


def _failure(field: str | None, title: str, message: str) -> dict[str, Any]:
    return {"ok": False, "field": field, "title": title, "message": message}


def _diagnose(exc: Exception) -> dict[str, Any]:
    if _is_certificate_error(exc):
        return _failure(
            "certificate",
            "Échec de la connexion : certificat non reconnu",
            "Le serveur a été joint, mais la connexion sécurisée a été refusée. Vérifiez que le fichier .crt est bien celui fourni par votre service informatique.",
        )
    if isinstance(exc, openai.APITimeoutError):
        return _failure("api_base", "Échec de la connexion : délai dépassé", "Le service n’a pas répondu à temps. Vérifiez l’URL et votre accès au réseau de l’entreprise.")
    if isinstance(exc, openai.APIConnectionError):
        return _failure("api_base", "Échec de la connexion : serveur injoignable", "Impossible de joindre le service. Vérifiez l’URL et votre accès au réseau de l’entreprise (VPN).")
    if isinstance(exc, (openai.AuthenticationError, openai.PermissionDeniedError)):
        return _failure("api_key", "Échec de la connexion : clé API refusée", "Le service a refusé la clé API. Vérifiez qu’elle a été copiée en entier et qu’elle est toujours valide.")
    if isinstance(exc, openai.NotFoundError):
        return _failure("api_base", "Échec de la connexion : adresse ou modèle introuvable", "Le service répond, mais l’URL ou le modèle demandé n’existe pas. Vérifiez l’URL (elle se termine souvent par /v1) et le modèle.")
    if isinstance(exc, openai.APIStatusError):
        return _failure(None, f"Échec de la connexion : erreur {exc.status_code}", str(exc.message))
    return _failure(None, "Échec de la connexion", str(exc))


PROBE_TIMEOUT_SECONDS = 180.0
MAX_PROMPT_CHARS = 60_000
_FILLER = (
    "Ce paragraphe sert uniquement à mesurer la taille de texte que le service accepte en une seule requête. "
)


def _chars(value: int) -> str:
    return f"{value:,}".replace(",", "\u202f")  # French thousands separator


def _check(name: str, ok: bool, message: str) -> dict[str, Any]:
    return {"name": name, "ok": ok, "message": message}


def _probe_output_length(client: Any, model: str) -> dict[str, Any]:
    tokens = get_max_output_tokens()
    try:
        client.chat.completions.create(model=model, max_tokens=tokens, messages=[{"role": "user", "content": "Réponds OK."}])
    except openai.BadRequestError as exc:
        return _check(
            "Longueur de réponse",
            False,
            f"{_chars(tokens)} tokens refusés ({exc.message}). La génération continuera sans limite explicite ; "
            "fixez une valeur acceptée avec CUSTOM_MAX_OUTPUT_TOKENS dans le .env.",
        )
    return _check("Longueur de réponse", True, f"{_chars(tokens)} tokens acceptés ; une réponse plus longue est reprise automatiquement.")


def _probe_json_mode(client: Any, model: str) -> dict[str, Any]:
    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=50,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": 'Réponds uniquement avec ce JSON : {"ok": true}'}],
        )
    except openai.BadRequestError:
        return _check("Mode JSON", False, "Non pris en charge : les réponses du modèle seront vérifiées et redemandées si besoin.")
    content = response.choices[0].message.content or ""
    try:
        json.loads(content[content.find("{") : content.rfind("}") + 1])
    except ValueError:
        return _check("Mode JSON", False, "Accepté, mais la réponse n’est pas un JSON valide.")
    return _check("Mode JSON", True, "Pris en charge.")


def _probe_prompt_size(client: Any, model: str) -> dict[str, Any]:
    """Largest prompt ProtoLab sends: one screen outline + its spec + the context excerpt."""
    target = MAX_PROMPT_CHARS
    for size in (target, target // 2, target // 4):
        prompt = (_FILLER * (size // len(_FILLER) + 1))[:size] + "\nRéponds OK."
        try:
            client.chat.completions.create(model=model, max_tokens=1, messages=[{"role": "user", "content": prompt}])
        except openai.BadRequestError:
            continue
        if size == target:
            return _check("Taille de prompt", True, f"{_chars(size)} caractères acceptés : les budgets actuels conviennent.")
        return _check(
            "Taille de prompt",
            False,
            f"{_chars(target)} caractères refusés, {_chars(size)} acceptés : les écrans très chargés ou les longues specs "
            "risquent d’être refusés par le service.",
        )
    return _check(
        "Taille de prompt",
        False,
        f"Même {_chars(target // 4)} caractères sont refusés : le service accepte des requêtes trop courtes pour ProtoLab.",
    )


def run_capability_checks(candidate: Any) -> list[dict[str, Any]]:
    """What the generation relies on, checked once the connection works."""
    client = build_client(candidate, timeout_seconds=PROBE_TIMEOUT_SECONDS)
    checks = []
    for probe in (_probe_output_length, _probe_json_mode, _probe_prompt_size):
        try:
            checks.append(probe(client, candidate.model))
        except (openai.OpenAIError, httpx.HTTPError, ssl.SSLError, OSError) as exc:
            name = {"_probe_output_length": "Longueur de réponse", "_probe_json_mode": "Mode JSON"}.get(probe.__name__, "Taille de prompt")
            checks.append(_check(name, False, f"Test impossible : {_diagnose(exc)['title']}"))
    return checks


@router.post("/test")
def test_connection(payload: SettingsPayload) -> dict[str, Any]:
    """Tests the values typed in the form (not yet saved) with the stored certificate."""
    settings = get_effective_settings()
    candidate = replace(
        settings,
        api_base=settings.api_base if "api_base" in settings.env_fields else payload.api_base.strip(),
        api_key=settings.api_key if payload.api_key is None or "api_key" in settings.env_fields else payload.api_key.strip(),
        model=settings.model if "model" in settings.env_fields else (payload.model.strip() or DEFAULT_MODEL),
    )
    tested_at = datetime.now(timezone.utc).isoformat()

    if not candidate.configured:
        return {**_failure(None, "Paramètres incomplets", f"À renseigner : {', '.join(candidate.missing)}."), "at": tested_at}

    try:
        client = build_client(candidate, timeout_seconds=TEST_TIMEOUT_SECONDS)
        client.chat.completions.create(model=candidate.model, max_tokens=1, messages=[{"role": "user", "content": "ping"}])
        result: dict[str, Any] = {"ok": True, "field": None, "title": "Connexion opérationnelle", "message": f"modèle {candidate.model}"}
        result["checks"] = run_capability_checks(candidate)
    except (openai.OpenAIError, httpx.HTTPError, ssl.SSLError, OSError) as exc:
        result = _diagnose(exc)

    result.update({"at": tested_at, "model": candidate.model})
    save_test_result(result)
    return result
