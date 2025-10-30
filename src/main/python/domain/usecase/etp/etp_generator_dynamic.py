from typing import Dict

from domain.dto.EtpDto import EtpDto
from domain.services.requirements_interpreter import apply_update_command
from domain.usecase.etp.dynamic_prompt_generator import (
    generate_requirements_rag_first,
    regenerate_single,
    retrieve_from_kb,
    llm_generate_requirements,
)


def _new_requirement_line(necessity: str, existing: Dict[int, str], hint: str) -> str:
    rag_candidates = retrieve_from_kb(necessity)
    for line in rag_candidates:
        if line not in existing.values():
            return line
    llm_candidates = llm_generate_requirements(
        necessity,
        target_count=1,
        existing=list(existing.values()),
    )
    for line in llm_candidates:
        if line not in existing.values():
            return line
    if hint:
        return hint
    return "Requisito adicional"


def start_requirements(dto: EtpDto) -> EtpDto:
    if dto.requirements:
        requirements = dto.requirements
        source = dto.requirements_source or "llm"
    else:
        requirements, source = generate_requirements_rag_first(dto.necessity or "")
        dto.requirements = requirements
        dto.requirements_source = source
    dto.requirements_history = [dto.snapshot()] if requirements else []
    dto.requirements_locked = False
    dto.stage = "revise_requirements"
    return dto


def apply_revision(dto: EtpDto, cmd: Dict) -> EtpDto:
    if dto.requirements_locked:
        return dto

    ctype = cmd.get("type")
    if ctype == "regenerate_all":
        dto.push_history()
        requirements, source = generate_requirements_rag_first(dto.necessity or "")
        dto.requirements = requirements
        dto.requirements_source = source
        return dto

    if ctype == "append_one":
        dto.push_history()
        existing = {int(r["id"][1:]): r["text"].split(" — ", 1)[1] for r in dto.requirements}
        hint = (cmd.get("payload") or "").strip()
        new_line = _new_requirement_line(dto.necessity or "", existing, hint)
        updated_cmd = dict(cmd)
        updated_cmd["payload"] = new_line
        dto.requirements = apply_update_command(updated_cmd, dto.requirements)
        return dto

    if ctype == "remove_one":
        dto.push_history()
        dto.requirements = apply_update_command(cmd, dto.requirements)
        return dto

    if ctype == "replace_one" and cmd.get("targets"):
        dto.push_history()
        index1 = cmd["targets"][0]
        dto.requirements = regenerate_single(dto.necessity or "", dto.requirements, index1)
        return dto

    return dto


def accept_requirements(dto: EtpDto) -> EtpDto:
    dto.requirements_locked = True
    dto.stage = "approved_requirements"
    if not dto.current_section:
        dto.current_section = "objeto"
    return dto
