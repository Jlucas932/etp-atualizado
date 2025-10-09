from dataclasses import dataclass, field
from typing import List, Dict, Optional, Literal

Requirement = Dict[str, str]  # {"id": "R1", "text": "R1 — ..."}
ReqSource = Literal["rag", "llm"]


def _clone_requirements(requirements: List[Requirement]) -> List[Requirement]:
    return [{"id": r.get("id", ""), "text": r.get("text", "")} for r in requirements]


@dataclass
class EtpDto:
    conversation_id: str
    necessity: Optional[str] = None

    # requisitos atuais NORMALIZADOS (somente "R# — texto")
    requirements: List[Requirement] = field(default_factory=list)

    # histórico de versões para auditoria/regressão
    requirements_history: List[List[Requirement]] = field(default_factory=list)

    # origem da versão atual (rag|llm)
    requirements_source: Optional[ReqSource] = None

    # se True, travar alterações e avançar o fluxo
    requirements_locked: bool = False

    # estágio do fluxo (para não resetar)
    stage: str = "ask_necessity"  # ask_necessity -> revise_requirements -> approved_requirements -> next_sections

    # seção corrente pós-requisitos
    current_section: Optional[str] = None  # ex.: "objeto", "estimativa_custos"... conforme seu fluxo existente

    def snapshot(self) -> List[Requirement]:
        return _clone_requirements(self.requirements)

    def push_history(self) -> None:
        if self.requirements:
            self.requirements_history.append(self.snapshot())


class _LegacyModel:
    """Placeholder compatível com importações antigas baseadas em SQLAlchemy."""

    __tablename__: Optional[str] = None

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class EtpSession(_LegacyModel):
    requirements: List[Requirement]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.requirements = kwargs.get("requirements", [])
        self.answers = kwargs.get("answers", {})
        self.requirements_locked = kwargs.get("requirements_locked", False)

    def get_answers(self):
        return dict(getattr(self, "answers", {}) or {})

    def set_answers(self, answers_dict):
        self.answers = dict(answers_dict)

    def get_requirements(self):
        return list(getattr(self, "requirements", []) or [])

    def set_requirements(self, requirements_list):
        self.requirements = list(requirements_list or [])
        return self.requirements

    def is_requirements_locked(self) -> bool:
        return bool(getattr(self, "requirements_locked", False))

    def set_requirements_locked(self, locked: bool) -> None:
        self.requirements_locked = bool(locked)


class DocumentAnalysis(_LegacyModel):
    pass


class KnowledgeBase(_LegacyModel):
    pass


class EtpTemplate(_LegacyModel):
    pass


class ChatSession(_LegacyModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.messages = kwargs.get("messages", []) or []

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
