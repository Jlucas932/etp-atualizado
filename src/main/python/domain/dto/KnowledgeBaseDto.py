# [DEPRECATED] Mantido apenas para compatibilidade com versões anteriores.
# Use: from domain.dto.KbDto import KbDocument, KbChunk
# Este módulo apenas reexporta símbolos para não quebrar imports antigos.

from domain.dto.KbDto import KbDocument, KbChunk  # noqa: F401

# O nome original "KnowledgeBaseDocument" continua disponível para quem ainda usa.
KnowledgeBaseDocument = KbDocument  # alias compatível

__all__ = ["KbDocument", "KbChunk", "KnowledgeBaseDocument"]
