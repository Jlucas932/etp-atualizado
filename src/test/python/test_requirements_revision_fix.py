import os
import sys
from types import SimpleNamespace

import pytest
from flask import Flask

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'main', 'python'))

from adapter.entrypoint.chat.ChatController import chat_bp, _SESSIONS  # noqa: E402
from domain.services.requirements_interpreter import (  # noqa: E402
    normalize_requirements,
    parse_user_intent,
)
from domain.usecase.etp import dynamic_prompt_generator as generator  # noqa: E402


class ApiClient:
    def __init__(self):
        _SESSIONS.clear()
        app = Flask(__name__)
        app.register_blueprint(chat_bp, url_prefix="/chat")
        app.config["TESTING"] = True
        self._client = app.test_client()
        self.conversation_id = "test-conversation"

    def start_etp(self, need: str) -> SimpleNamespace:
        resp = self._client.post(
            "/chat/message",
            json={"conversation_id": self.conversation_id, "message": need},
        )
        return SimpleNamespace(**resp.get_json())

    def message(self, text: str) -> SimpleNamespace:
        resp = self._client.post(
            "/chat/message",
            json={"conversation_id": self.conversation_id, "message": text},
        )
        return SimpleNamespace(**resp.get_json())


@pytest.fixture
def client():
    return ApiClient()


def test_format_only_Rn_dash_text():
    raw = """R1 - Texto 1. Justificativa: X
    R2 — Texto 2
    3) Texto 3
    - Texto 4"""
    out = normalize_requirements(raw)
    assert out == [
        "R1 — Texto 1",
        "R2 — Texto 2",
        "R3 — Texto 3",
        "R4 — Texto 4",
    ]
    assert all("Justificativa" not in r for r in out)


def test_flow_no_reset_accept_and_edit(client):
    dto = client.start_etp("carros para uma secretaria")
    assert dto.stage == "requirements_review"
    assert dto.conversation_id == client.conversation_id
    assert all(r.startswith("R") for r in dto.requirements)

    dto = client.message("não gostei do r1, gere outro")
    assert dto.stage == "requirements_review"
    assert len(dto.requirements) >= 5

    dto = client.message("pode manter")
    assert dto.requirements_locked is True
    assert dto.stage == "next_step"
    assert dto.conversation_id == client.conversation_id


def test_rag_first_then_fallback(monkeypatch):
    calls = {"rag": 0, "llm": 0}

    def fake_retrieve(need, topk=5):
        calls["rag"] += 1
        return [
            ("Requisito baseado em base 1", 0.9),
            ("Requisito baseado em base 2", 0.8),
        ][:topk]

    def fake_llm(need, amount=5, hint=None):
        calls["llm"] += 1
        return [f"Requisito LLM {i+1}" for i in range(amount)]

    monkeypatch.setattr(generator, "retrieve_from_kb", fake_retrieve)
    monkeypatch.setattr(generator, "llm_generate_requirements", fake_llm)

    out = generator.generate_requirements("necessidade teste")

    assert calls["rag"] == 1
    assert calls["llm"] == 1
    assert len(out) >= 5
    assert out[0].startswith("R1 —")
    assert all("Justificativa" not in line for line in out)


def test_intents_supported():
    assert parse_user_intent("remova o R4").intent == "remove"
    assert parse_user_intent("remova o R4").target == 4
    assert parse_user_intent("gera mais 2 requisitos").amount == 2
    replace = parse_user_intent("refaça o r2 deixando objetivo")
    assert replace.intent in {"replace", "edit"}
    assert replace.target == 2
    assert parse_user_intent("pode manter todos").intent == "accept"
