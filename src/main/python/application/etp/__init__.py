"""
ETP (Estudo Técnico Preliminar) application layer.

This module provides types and assembly logic for decoupling
chat stages from document structure.
"""

from .types import ChatStage, DocSection, StagePayload, EtpParts
from .assembler import assemble_sections

__all__ = [
    'ChatStage',
    'DocSection',
    'StagePayload',
    'EtpParts',
    'assemble_sections',
]
