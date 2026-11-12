"""Connection settings: saved from the app, overridable by a .env file next to the app.

The API key is encrypted with the Windows user account (DPAPI) before being
written to disk; it is never sent back to the frontend in clear.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding
from dotenv import load_dotenv

from app_paths import config_dir, env_file

DEFAULT_MODEL = "mistral"
DEFAULT_TIMEOUT_SECONDS = 300.0
CERTIFICATE_FILENAME = "ca.crt"
KEYCHAIN_SERVICE = "ProtoLab"
KEYCHAIN_ACCOUNT = "api_key"

# Field name -> environment variable that overrides it.
ENV_VARIABLES = {
    "api_base": "CUSTOM_API_BASE",
    "api_key": "CUSTOM_API_KEY",
    "ca_bundle": "CUSTOM_CA_BUNDLE",
    "model": "CUSTOM_MODEL",
    "timeout": "CUSTOM_TIMEOUT_SECONDS",
}
REQUIRED_FIELDS = {"api_base": "URL du service", "api_key": "Clé API", "ca_bundle": "Certificat de l’entreprise"}

load_dotenv(env_file())


@dataclass
class EffectiveSettings:
    api_base: str
    api_key: str
    ca_bundle: str
    model: str
    timeout: float
    env_fields: list[str]

    @property
    def missing(self) -> list[str]:
        return [label for field, label in REQUIRED_FIELDS.items() if not getattr(self, field)]

    @property
    def configured(self) -> bool:
        return not self.missing


# --- API key encryption -------------------------------------------------------

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _DataBlob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _blob(data: bytes) -> tuple[_DataBlob, Any]:
        buffer = ctypes.create_string_buffer(data, len(data))
        return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer

    def _dpapi(data: bytes, protect: bool) -> bytes:
        blob_in, _buffer = _blob(data)
        blob_out = _DataBlob()
        if protect:
            ok = ctypes.windll.crypt32.CryptProtectData(ctypes.byref(blob_in), "ProtoLab", None, None, None, 0, ctypes.byref(blob_out))
        else:
            ok = ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out))
        if not ok:
            raise ctypes.WinError()
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)

    def _encrypt(value: str) -> dict[str, str]:
        return {"scheme": "dpapi", "data": base64.b64encode(_dpapi(value.encode("utf-8"), True)).decode("ascii")}

elif sys.platform == "darwin":
    # macOS: the key goes to the user's login keychain; config.json only notes where it is.
    # The command is fed on stdin (security -i) so the key never shows in the process list.

    def _keychain(command: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["security", "-i"], input=command + "\n", capture_output=True, text=True, timeout=15)

    def _quote(value: str) -> str:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def _encrypt(value: str) -> dict[str, str]:
        result = _keychain(f"add-generic-password -U -s {KEYCHAIN_SERVICE} -a {KEYCHAIN_ACCOUNT} -w {_quote(value)}")
        if result.returncode != 0 or "error" in (result.stdout + result.stderr).lower():
            raise OSError("Impossible d’enregistrer la clé API dans le trousseau macOS.")
        return {"scheme": "keychain", "data": ""}

else:
    # Development on Linux only: no OS keystore wired, the key is merely encoded.
    def _encrypt(value: str) -> dict[str, str]:
        return {"scheme": "plain", "data": base64.b64encode(value.encode("utf-8")).decode("ascii")}


def _read_keychain() -> str:
    if sys.platform != "darwin":
        return ""
    result = subprocess.run(
        ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT, "-w"],
        capture_output=True, text=True, timeout=15,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _forget_keychain() -> None:
    if sys.platform == "darwin":
        subprocess.run(["security", "delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT], capture_output=True, timeout=15)


def _decrypt(stored: dict[str, str] | None) -> str:
    if not stored:
        return ""
    if stored.get("scheme") == "keychain":
        return _read_keychain()
    raw = base64.b64decode(stored["data"])
    if stored.get("scheme") == "dpapi":
        if sys.platform != "win32":
            return ""
        return _dpapi(raw, False).decode("utf-8")
    return raw.decode("utf-8")


# --- Saved settings -----------------------------------------------------------


def _config_file() -> Path:
    return config_dir() / "config.json"


def certificate_path() -> Path:
    return config_dir() / CERTIFICATE_FILENAME


def load_saved() -> dict[str, Any]:
    try:
        return json.loads(_config_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_saved(data: dict[str, Any]) -> None:
    config_dir().mkdir(parents=True, exist_ok=True)
    _config_file().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def saved_api_key() -> str:
    try:
        return _decrypt(load_saved().get("api_key"))
    except (OSError, subprocess.SubprocessError):
        # Encrypted by another Windows account, or keychain unavailable: treat as missing.
        return ""


def save_settings(api_base: str, api_key: str | None, model: str, timeout: float) -> None:
    data = load_saved()
    data.update(
        {
            "api_base": api_base.strip(),
            "model": model.strip() or DEFAULT_MODEL,
            "timeout": timeout,
        }
    )
    if api_key is not None:
        if not api_key.strip():
            _forget_keychain()
        data["api_key"] = _encrypt(api_key.strip()) if api_key.strip() else None
    _write_saved(data)


def save_test_result(result: dict[str, Any]) -> None:
    data = load_saved()
    data["last_test"] = result
    _write_saved(data)


def clear_settings() -> None:
    _forget_keychain()
    for path in (_config_file(), certificate_path()):
        path.unlink(missing_ok=True)


def store_certificate(filename: str, content: bytes) -> dict[str, Any]:
    """Validates a .crt (PEM or DER, possibly a chain) and stores it as PEM."""
    try:
        certificates = x509.load_pem_x509_certificates(content)
    except ValueError:
        try:
            certificates = [x509.load_der_x509_certificate(content)]
        except ValueError as exc:
            raise ValueError("Ce fichier n’est pas un certificat valide (.crt au format PEM ou DER attendu).") from exc

    config_dir().mkdir(parents=True, exist_ok=True)
    certificate_path().write_bytes(b"".join(certificate.public_bytes(Encoding.PEM) for certificate in certificates))
    info = {
        "name": filename,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": min(certificate.not_valid_after_utc for certificate in certificates).isoformat(),
    }
    data = load_saved()
    data["certificate"] = info
    data.pop("last_test", None)
    _write_saved(data)
    return info


# --- Effective settings (.env first, then saved) -------------------------------


def get_effective_settings() -> EffectiveSettings:
    saved = load_saved()
    env_fields = [field for field, variable in ENV_VARIABLES.items() if os.getenv(variable)]

    def pick(field: str, saved_value: Any) -> Any:
        return os.getenv(ENV_VARIABLES[field]) or saved_value

    saved_certificate = str(certificate_path()) if saved.get("certificate") and certificate_path().is_file() else ""
    timeout = pick("timeout", saved.get("timeout"))
    try:
        timeout_seconds = float(timeout) if timeout else DEFAULT_TIMEOUT_SECONDS
    except ValueError:
        timeout_seconds = DEFAULT_TIMEOUT_SECONDS

    return EffectiveSettings(
        api_base=pick("api_base", saved.get("api_base") or ""),
        api_key=pick("api_key", "") or saved_api_key(),
        ca_bundle=pick("ca_bundle", saved_certificate),
        model=pick("model", saved.get("model") or DEFAULT_MODEL),
        timeout=timeout_seconds,
        env_fields=env_fields,
    )


def public_settings() -> dict[str, Any]:
    """What the settings screen may show: never the API key itself."""
    saved = load_saved()
    effective = get_effective_settings()
    return {
        "configured": effective.configured,
        "missing": effective.missing,
        "env_fields": effective.env_fields,
        "env_file": str(env_file()) if env_file().is_file() else None,
        "storage_dir": str(config_dir()),
        "api_base": effective.api_base,
        "has_api_key": bool(effective.api_key),
        "api_key_hint": effective.api_key[-4:] if len(effective.api_key) >= 8 else "",
        "certificate": saved.get("certificate") if "ca_bundle" not in effective.env_fields else {"name": Path(effective.ca_bundle).name},
        "model": effective.model,
        "timeout": effective.timeout,
        "last_test": saved.get("last_test"),
    }
