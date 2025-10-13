"""ORM models for legacy ETP components."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from domain.interfaces.dataprovider.DatabaseConfig import db


class EtpSession(db.Model):
    """SQLAlchemy ORM model for the ``etp_sessions`` table."""

    __tablename__ = "etp_sessions"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(255), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    status = db.Column(db.String(50), nullable=False, default="active")

    # Conversational flow data
    answers = db.Column(db.JSON, nullable=False, default=dict)
    requirements = db.Column(db.JSON, nullable=False, default=list)
    requirements_history = db.Column(db.JSON, nullable=False, default=list)
    requirements_source = db.Column(db.String(32), nullable=True)
    requirements_locked = db.Column(db.Boolean, default=False, nullable=False)
    stage = db.Column(db.String(64), nullable=True)
    current_section = db.Column(db.String(128), nullable=True)

    # Legacy fields used by the dynamic ETP flow
    answers_validated = db.Column(db.Boolean, default=False, nullable=False)
    generated_etp = db.Column(db.Text, nullable=True)
    preview_content = db.Column(db.Text, nullable=True)
    preview_approved = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def _ensure_dict(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str) and value:
            try:
                return dict(json.loads(value))
            except (TypeError, ValueError):
                return {}
        return {}

    def _ensure_list(self, value: Any) -> List[Dict[str, Any]]:
        if isinstance(value, list):
            return [dict(item) if isinstance(item, dict) else item for item in value]
        if isinstance(value, str) and value:
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else []
            except (TypeError, ValueError):
                return []
        return []

    # Compatibility helpers -------------------------------------------------
    def get_answers(self) -> Dict[str, Any]:
        return self._ensure_dict(self.answers)

    def set_answers(self, answers_dict: Dict[str, Any]) -> None:
        self.answers = dict(answers_dict or {})

    def get_requirements(self) -> List[Dict[str, Any]]:
        return self._ensure_list(self.requirements)

    def set_requirements(self, requirements_list: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        normalized = self._ensure_list(requirements_list)
        self.requirements = normalized
        return normalized

    def is_requirements_locked(self) -> bool:
        return bool(self.requirements_locked)

    def set_requirements_locked(self, locked: bool) -> None:
        self.requirements_locked = bool(locked)

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<EtpSession {self.session_id}>"
