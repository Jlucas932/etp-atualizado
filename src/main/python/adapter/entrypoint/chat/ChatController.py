from typing import Dict

from flask import Blueprint, jsonify, request

from domain.dto.EtpDto import EtpDto
from domain.services.requirements_interpreter import (
    detect_requirements_discussion,
    parse_update_command,
    format_for_ui,
)
from domain.services.etp_dynamic import (
    build_initial_requirements,
    regenerate_one,
)
from domain.usecase.etp.etp_generator_dynamic import (
    start_requirements,
    apply_revision,
    accept_requirements,
)

chat_bp = Blueprint("chat", __name__)

_SESSIONS: Dict[str, EtpDto] = {}


def _get_session(conversation_id: str) -> EtpDto:
    dto = _SESSIONS.get(conversation_id)
    if not dto:
        dto = EtpDto(conversation_id=conversation_id)
        _SESSIONS[conversation_id] = dto
    return dto


@chat_bp.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "component": "chat"})


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

    if dto.stage == "ask_necessity":
        dto.necessity = user_text
        requirements, source = build_initial_requirements(dto.necessity or "")
        dto.requirements = requirements
        dto.requirements_source = source
        start_requirements(dto)
        return jsonify({
            "stage": dto.stage,
            "requirements": format_for_ui(dto.requirements),
            "source": dto.requirements_source,
            "message": "Aqui estão os requisitos iniciais. Avalie e me diga se deseja ajustes.",
        })

    if dto.stage == "revise_requirements":
        if dto.requirements_locked:
            return jsonify({
                "stage": dto.stage,
                "requirements": format_for_ui(dto.requirements),
                "requirements_locked": True,
                "message": "Os requisitos já foram confirmados. Vamos avançar para a próxima etapa?",
            })

        if not detect_requirements_discussion(user_text):
            return jsonify({
                "stage": dto.stage,
                "requirements": format_for_ui(dto.requirements),
                "message": "Continuo à disposição para ajustar algum requisito específico.",
            })

        cmd = parse_update_command(user_text)
        ctype = cmd.get("type")

        if ctype == "accept_all":
            accept_requirements(dto)
            return jsonify({
                "stage": dto.stage,
                "requirements": format_for_ui(dto.requirements),
                "requirements_locked": True,
                "current_section": dto.current_section,
                "message": "Perfeito, requisitos confirmados. Vamos avançar para a seção do objeto da contratação?",
            })

        if ctype == "replace_one" and cmd.get("targets"):
            dto.push_history()
            index1 = cmd["targets"][0]
            dto.requirements = regenerate_one(dto.necessity or "", dto.requirements, index1)
            return jsonify({
                "stage": dto.stage,
                "requirements": format_for_ui(dto.requirements),
                "source": dto.requirements_source,
                "message": f"Atualizei o R{index1}. Revise a nova redação.",
            })

        if ctype in {"remove_one", "append_one", "regenerate_all"}:
            apply_revision(dto, cmd)
            return jsonify({
                "stage": dto.stage,
                "requirements": format_for_ui(dto.requirements),
                "source": dto.requirements_source,
                "message": "Lista atualizada conforme solicitado.",
            })

        return jsonify({
            "stage": dto.stage,
            "requirements": format_for_ui(dto.requirements),
            "message": "Certo, me indique se deseja trocar, remover, adicionar ou refazer algo.",
        })

    if dto.stage == "approved_requirements":
        dto.stage = "next_sections"
        dto.current_section = dto.current_section or "objeto"
        return jsonify({
            "stage": dto.stage,
            "requirements": format_for_ui(dto.requirements),
            "current_section": dto.current_section,
            "message": "Vamos detalhar o objeto da contratação. Pode me contar os principais pontos?",
        })

    return jsonify({
        "stage": dto.stage,
        "requirements": format_for_ui(dto.requirements),
        "current_section": dto.current_section,
        "message": "Continuo acompanhando. Compartilhe as próximas informações quando estiver pronto.",
    })
