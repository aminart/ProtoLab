"""Shared fixtures. The model is never called: `fake_llm` replaces it and returns queued answers,
recording every request so tests can check the prompts."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

BACKEND = Path(__file__).resolve().parent.parent / "backend"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Isolate the tests from the settings and .env of the machine, before importing the app.
os.environ["PROTOLAB_CONFIG_DIR"] = tempfile.mkdtemp(prefix="protolab-tests-")
for variable in list(os.environ):
    if variable.startswith("CUSTOM_"):
        del os.environ[variable]
sys.path.insert(0, str(BACKEND))


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def mockup() -> dict[str, Any]:
    return load_fixture("figma_mockup.json")


@pytest.fixture
def context_md() -> str:
    return fixture_text("contexte.md")


@pytest.fixture
def spec_md() -> str:
    return fixture_text("spec-nouvelle-demande.md")


class FakeLLM:
    """Stands for the OpenAI client: `answers` are returned in order (a str or an exception);
    `calls` keeps every request."""

    def __init__(self) -> None:
        self.answers: list[Any] = []
        self.calls: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def queue(self, *answers: Any) -> "FakeLLM":
        self.answers.extend(json.dumps(a, ensure_ascii=False) if isinstance(a, dict) else a for a in answers)
        return self

    def _create(self, **request: Any) -> Any:
        self.calls.append(request)
        answer = self.answers.pop(0) if self.answers else "{}"
        if isinstance(answer, Exception):
            raise answer
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=answer), finish_reason="stop")])

    def user_prompt(self, index: int = 0) -> str:
        return self.calls[index]["messages"][1]["content"]


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeLLM:
    import main
    import openai_client

    llm = FakeLLM()
    monkeypatch.setattr(openai_client, "get_openai_client", lambda: llm)
    monkeypatch.setattr(main, "_require_llm", lambda: None)
    return llm


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    import main

    return TestClient(main.app)
