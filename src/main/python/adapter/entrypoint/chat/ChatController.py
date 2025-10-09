from __future__ import annotations

from typing import Dict, List

from flask import Blueprint, jsonify, request

from domain.dto.EtpDto import EtpDto
from domain.services.requirements_interpreter import (
    RequirementIntent,
    normalize_requirements,
    parse_user_intent,
    requirements_to_plain,
)
from domain.usecase.etp.dynamic_prompt_generator import (
    choose_new_requirement,
    generate_requirements,
)

chat_bp = Blueprint("chat", __name__)

_SESSIONS: Dict[str, EtpDto] = {}


def _get_session(conversation_id: str) -> EtpDto:
    dto = _SESSIONS.get(conversation_id)
    if not dto:
        dto = EtpDto(conversation_id=conversation_id)
        _SESSIONS[conversation_id] = dto
    return dto


def _make_response(dto: EtpDto, message: str):
    payload = {
        "conversation_id": dto.conversation_id,
        "stage": dto.stage,
        "need": dto.need,
        "requirements": dto.requirements,
        "requirements_locked": dto.requirements_locked,
        "requirements_version": dto.requirements_version,
        "history": dto.history,
        "showJustificativa": dto.showJustificativa,
        "message": message,
    }
    return jsonify(payload)


@chat_bp.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "component": "chat"})


def _ensure_requirements(dto: EtpDto) -> None:
    if not dto.requirements:
        dto.requirements = generate_requirements(dto.need)
        dto.requirements_version = 1
        dto.history = [dto.snapshot()]
        dto.showJustificativa = False
        dto.requirements_locked = False
        dto.stage = "requirements_review"


def _update_requirements(dto: EtpDto, plain: List[str], confirmation_message: str):
    dto.requirements = normalize_requirements(plain)
    dto.requirements_version += 1
    dto.showJustificativa = False
    return _make_response(dto, confirmation_message)


def _handle_accept(dto: EtpDto):
    dto.requirements = normalize_requirements(dto.requirements)
    dto.requirements_locked = True
    dto.stage = "next_step"
    dto.showJustificativa = False
    return _make_response(dto, "Requisitos confirmados. Seguimos para o próximo passo.")


def _handle_generate_more(dto: EtpDto, intent: RequirementIntent):
    amount = intent.amount or 1
    dto.append_history()
    plain = requirements_to_plain(dto.requirements)
    for _ in range(amount):
        candidate = choose_new_requirement(dto.need, plain, hint=intent.payload)
        plain.append(candidate)
    return _update_requirements(dto, plain, "Adicionei novos requisitos para revisão.")


def _handle_replace_or_edit(dto: EtpDto, intent: RequirementIntent):
    target = intent.target
    if not target or target < 1 or target > len(dto.requirements):
        return _make_response(dto, "Informe o identificador do requisito que deseja ajustar.")
    dto.append_history()
    plain = requirements_to_plain(dto.requirements)
    replacement = choose_new_requirement(dto.need, plain, hint=intent.payload)
    plain[target - 1] = replacement
    return _update_requirements(dto, plain, f"Atualizei o R{target} conforme solicitado.")


def _handle_remove(dto: EtpDto, intent: RequirementIntent):
    target = intent.target
    if not target or target < 1 or target > len(dto.requirements):
        return _make_response(dto, "Não encontrei esse requisito para remover.")
    dto.append_history()
    plain = requirements_to_plain(dto.requirements)
    del plain[target - 1]
    if not plain:
        plain.append(choose_new_requirement(dto.need, [], hint=intent.payload))
    return _update_requirements(dto, plain, f"Removi o R{target}.")


def _handle_rephrase(dto: EtpDto, intent: RequirementIntent):
    dto.append_history()
    plain = []
    payload = (intent.payload or "").strip()
    for text in requirements_to_plain(dto.requirements):
        cleaned = text.rstrip(" .;")
        if payload:
            cleaned = f"{payload.strip().capitalize()}: {cleaned}"
        else:
            cleaned = cleaned[:1].upper() + cleaned[1:]
        plain.append(cleaned)
    return _update_requirements(dto, plain, "Padronizei o tom dos requisitos.")


def _handle_example(dto: EtpDto):
    example = dto.requirements[0] if dto.requirements else "R1 — Exemplo ilustrativo"
    return _make_response(dto, f"Exemplo de requisito aplicado: {example}")


@chat_bp.route("/message", methods=["POST"])
def handle_message():
    data = request.get_json(force=True) or {}
    conversation_id = data.get("conversation_id")
    user_text = (data.get("message") or "").strip()

    if not conversation_id:
        return jsonify({"error": "conversation_id obrigatório"}), 400
    if not user_text:
        return jsonify({"error": "mensagem obrigatória"}), 400

    dto = _get_session(conversation_id)

    if dto.stage == "requirements_need":
        dto.need = user_text
        _ensure_requirements(dto)
        return _make_response(dto, "Gerei requisitos iniciais para sua avaliação.")

    if dto.stage == "requirements_review":
        if dto.requirements_locked:
            return _make_response(dto, "Requisitos já confirmados; podemos avançar.")

        intent = parse_user_intent(user_text)

        if intent.intent == "accept":
            return _handle_accept(dto)
        if intent.intent in {"replace", "edit"}:
            return _handle_replace_or_edit(dto, intent)
        if intent.intent == "remove":
            return _handle_remove(dto, intent)
        if intent.intent == "generate_more":
            return _handle_generate_more(dto, intent)
        if intent.intent == "rephrase":
            return _handle_rephrase(dto, intent)
        if intent.intent == "example":
            return _handle_example(dto)

        return _make_response(
            dto,
            "Indique se deseja aceitar, substituir, editar, remover ou gerar novos requisitos.",
        )

    return _make_response(dto, "Estamos prontos para seguir com as próximas etapas.")
