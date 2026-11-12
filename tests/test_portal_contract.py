"""Portal contract: /health, port, --no-browser and --version behave the same in every app of the suite."""
import socket

import pytest

import launcher
from app_info import APP_ID, DEFAULT_PORT, VERSION


def test_health_answers_without_ai_settings(client):
    body = client.get("/health").json()
    assert body == {"status": "ok", "app": APP_ID, "name": "ProtoLab", "version": VERSION}


def test_default_port_is_reserved_for_protolab():
    assert DEFAULT_PORT == 8030
    assert DEFAULT_PORT not in (8010, 8020, 8501)


def test_version_option(capsys):
    with pytest.raises(SystemExit) as exit_info:
        launcher.main(["--version"])
    assert exit_info.value.code == 0
    assert VERSION in capsys.readouterr().out


def test_imposed_port_taken_by_another_app_fails_explicitly(monkeypatch, capsys):
    with socket.socket() as other_app:
        other_app.bind(("127.0.0.1", 0))
        other_app.listen()
        port = other_app.getsockname()[1]
        started = []
        monkeypatch.setattr(launcher.uvicorn, "run", lambda *a, **k: started.append(k))
        with pytest.raises(SystemExit) as exit_info:
            launcher.main(["--port", str(port), "--no-browser"])
    assert exit_info.value.code == 2
    assert not started
    assert str(port) in capsys.readouterr().err


def test_no_browser_starts_on_imposed_port(monkeypatch):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    started, opened = [], []
    monkeypatch.setattr(launcher.uvicorn, "run", lambda app, **k: started.append(k))
    monkeypatch.setattr(launcher.webbrowser, "open", opened.append)
    launcher.main(["--port", str(port), "--no-browser"])
    assert started == [{"host": "127.0.0.1", "port": port, "log_level": "warning"}]
    assert not opened
