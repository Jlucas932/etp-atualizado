from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class EtpDto:
    conversation_id: str
    stage: str = "requirements_need"
    need: str = ""
    requirements: List[str] = field(default_factory=list)
    requirements_locked: bool = False
    requirements_version: int = 0
    history: List[dict] = field(default_factory=list)
    showJustificativa: bool = False

    def snapshot(self) -> dict:
        return {
            "version": self.requirements_version,
            "requirements": list(self.requirements),
        }

    def append_history(self) -> None:
        self.history.append(self.snapshot())


class _LegacyModel:
    """Placeholder compatível com importações antigas baseadas em SQLAlchemy."""

    __tablename__: Optional[str] = None

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class EtpSession(_LegacyModel):
    requirements: List[str]

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
