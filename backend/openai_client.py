from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
from openai import BadRequestError, OpenAI

from settings_store import EffectiveSettings, get_effective_settings


def get_missing_settings() -> list[str]:
    return get_effective_settings().missing


def is_custom_configured() -> bool:
    return get_effective_settings().configured


def get_model_name() -> str:
    return get_effective_settings().model


def build_client(settings: EffectiveSettings, timeout_seconds: float | None = None) -> OpenAI:
    timeout = timeout_seconds if timeout_seconds is not None else settings.timeout
    http_client = httpx.Client(
        verify=settings.ca_bundle or True,
        timeout=httpx.Timeout(timeout, connect=min(30.0, timeout)),
    )
    return OpenAI(base_url=settings.api_base, api_key=settings.api_key, http_client=http_client)


def get_openai_client() -> OpenAI:
    settings = get_effective_settings()
    if not settings.configured:
        raise RuntimeError(f"Paramètres de connexion incomplets : {', '.join(settings.missing)}")
    return build_client(settings)


# --- Completions ---------------------------------------------------------------

# Writing temperature recommended by Mistral for Mistral Small; structured passes use 0.
WRITING_TEMPERATURE = 0.15
DEFAULT_MAX_OUTPUT_TOKENS = 16000
MAX_OUTPUT_TOKENS_VARIABLE = "CUSTOM_MAX_OUTPUT_TOKENS"
MAX_CONTINUATIONS = 3
CONTINUE_PROMPT = (
    "Your answer was cut because it reached the length limit. Continue exactly where you stopped, "
    "without repeating anything and without any introduction."
)

logger = logging.getLogger(__name__)


def get_max_output_tokens() -> int:
    try:
        value = int(os.getenv(MAX_OUTPUT_TOKENS_VARIABLE, ""))
    except ValueError:
        return DEFAULT_MAX_OUTPUT_TOKENS
    return value if value > 0 else DEFAULT_MAX_OUTPUT_TOKENS


def _create(client: OpenAI, messages: list[dict[str, str]], temperature: float, json_mode: bool) -> Any:
    """One call; drops the optional parameters a server rejects instead of failing."""
    options: dict[str, Any] = {"max_tokens": get_max_output_tokens()}
    if json_mode:
        options["response_format"] = {"type": "json_object"}
    while True:
        try:
            response = client.chat.completions.create(
                model=get_model_name(), temperature=temperature, messages=messages, **options
            )
        except Exception as exc:
            if not isinstance(exc, BadRequestError) or not options:
                raise
            # Unsupported response_format first, then a max_tokens above the server limit.
            dropped = "response_format" if "response_format" in options else "max_tokens"
            logger.warning("Model service rejected %s, retrying without it: %s", dropped, exc)
            options.pop(dropped)
            continue
        return response


def complete(
    client: OpenAI, messages: list[dict[str, str]], *, temperature: float = WRITING_TEMPERATURE, json_mode: bool = False
) -> str:
    """Text of the answer. When the answer is cut by the length limit (finish_reason
    "length"), asks the model to continue and joins the parts."""
    response = _create(client, messages, temperature, json_mode)
    choice = response.choices[0]
    text = choice.message.content or ""
    continuations = 0
    while getattr(choice, "finish_reason", None) == "length" and continuations < MAX_CONTINUATIONS and not json_mode:
        continuations += 1
        follow_up = [*messages, {"role": "assistant", "content": text}, {"role": "user", "content": CONTINUE_PROMPT}]
        response = _create(client, follow_up, temperature, json_mode)
        choice = response.choices[0]
        text += choice.message.content or ""
    if getattr(choice, "finish_reason", None) == "length":
        logger.warning("Model answer still cut after %s continuations", continuations)
    return text


# --- Structured answers ---------------------------------------------------------


class ModelAnswerError(ValueError):
    """The model answered, but not with the JSON object that was asked for."""


def extract_json_object(text: str) -> dict[str, Any]:
    """The JSON object of an answer, tolerating a ```json fence or a sentence around it."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ModelAnswerError("La réponse du modèle ne contient pas d’objet JSON.")
    try:
        value = json.loads(text[start : end + 1])
    except ValueError as exc:
        raise ModelAnswerError(f"La réponse du modèle n’est pas un JSON valide ({exc}).") from exc
    if not isinstance(value, dict):
        raise ModelAnswerError("La réponse du modèle n’est pas un objet JSON.")
    return value


def complete_json(system: str, user: str, *, retries: int = 1) -> dict[str, Any]:
    """Asks for a JSON object (temperature 0, JSON mode when the service has it). An answer
    that does not parse is asked again once, with the parsing error."""
    client = get_openai_client()
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    last_error: ModelAnswerError | None = None
    for _ in range(retries + 1):
        text = complete(client, messages, temperature=0, json_mode=True)
        try:
            return extract_json_object(text)
        except ModelAnswerError as exc:
            last_error = exc
            messages = [
                *messages,
                {"role": "assistant", "content": text},
                {"role": "user", "content": f"{exc} Réponds uniquement avec l’objet JSON demandé, sans texte autour."},
            ]
    assert last_error is not None
    raise last_error
