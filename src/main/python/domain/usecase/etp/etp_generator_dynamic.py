from __future__ import annotations

from typing import List

from domain.dto.EtpDto import EtpDto
from domain.services.requirements_interpreter import requirements_to_plain
from domain.usecase.etp.dynamic_prompt_generator import (
    choose_new_requirement,
    generate_requirements,
)


def start_requirements(dto: EtpDto, k: int = 5) -> EtpDto:
    dto.requirements = generate_requirements(dto.need, k=k)
    dto.requirements_version = 1
    dto.history = [dto.snapshot()]
    dto.requirements_locked = False
    dto.stage = "requirements_review"
    dto.showJustificativa = False
    return dto


def replace_requirement(dto: EtpDto, index1: int, hint: str | None = None) -> EtpDto:
    if dto.requirements_locked or index1 < 1 or index1 > len(dto.requirements):
        return dto
    dto.append_history()
    plain = requirements_to_plain(dto.requirements)
    plain[index1 - 1] = choose_new_requirement(dto.need, plain, hint=hint)
    dto.requirements = generate_requirements_from_plain(plain)
    dto.requirements_version += 1
    return dto


def generate_requirements_from_plain(plain: List[str]) -> List[str]:
    from domain.services.requirements_interpreter import normalize_requirements

    return normalize_requirements(plain)


def append_requirement(dto: EtpDto, hint: str | None = None) -> EtpDto:
    if dto.requirements_locked:
        return dto
    dto.append_history()
    plain = requirements_to_plain(dto.requirements)
    plain.append(choose_new_requirement(dto.need, plain, hint=hint))
    dto.requirements = generate_requirements_from_plain(plain)
    dto.requirements_version += 1
    return dto


def remove_requirement(dto: EtpDto, index1: int) -> EtpDto:
    if dto.requirements_locked or index1 < 1 or index1 > len(dto.requirements):
        return dto
    dto.append_history()
    plain = requirements_to_plain(dto.requirements)
    del plain[index1 - 1]
    dto.requirements = generate_requirements_from_plain(plain)
    dto.requirements_version += 1
    return dto


def accept_requirements(dto: EtpDto) -> EtpDto:
    dto.requirements_locked = True
    dto.stage = "next_step"
    return dto
