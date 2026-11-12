"""API key storage: on macOS the key goes to the keychain, never in config.json nor in a command line."""
import importlib
import json
import subprocess
import sys
from types import SimpleNamespace


def test_macos_key_goes_to_the_keychain(monkeypatch):
    import settings_store

    keychain: dict[str, str] = {}
    calls: list[dict] = []

    def fake_run(args, input=None, **kwargs):
        calls.append({"args": args, "input": input})
        if args[:2] == ["security", "-i"]:
            keychain["key"] = input.split(" -w ", 1)[1].strip().strip('"')
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args[1] == "find-generic-password":
            return SimpleNamespace(returncode=0 if "key" in keychain else 44, stdout=keychain.get("key", "") + "\n", stderr="")
        if args[1] == "delete-generic-password":
            keychain.pop("key", None)
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(args)

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(subprocess, "run", fake_run)
    store = importlib.reload(settings_store)
    try:
        store.save_settings("https://llm.example/v1", "sk-secret-123", "mistral", 300)
        saved = json.loads((store.config_dir() / "config.json").read_text(encoding="utf-8"))
        assert saved["api_key"] == {"scheme": "keychain", "data": ""}
        assert "sk-secret-123" not in json.dumps(saved)
        assert all("sk-secret-123" not in " ".join(call["args"]) for call in calls)
        assert store.saved_api_key() == "sk-secret-123"
        store.clear_settings()
        assert "key" not in keychain
    finally:
        monkeypatch.undo()
        importlib.reload(settings_store)
