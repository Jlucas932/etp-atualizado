"""
Intent detection module for robust handling of user inputs.
Provides functions to detect vague acknowledgments, uncertainty expressions,
numeric selections, and strategy name selections.
"""

import re
from typing import Optional
import unicodedata


def _normalize_text(text: str) -> str:
    """
    Normalizes text by:
    - Converting to lowercase
    - Removing accents
    - Collapsing whitespace
    
    Args:
        text: Input text to normalize
        
    Returns:
        Normalized text string
    """
    # Convert to lowercase
    text = text.lower()
    
    # Remove accents using Unicode normalization
    text = ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )
    
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def is_vague_ack(text: str) -> bool:
    """
    Detects vague acknowledgments that should not trigger data storage or stage advancement.
    
    Matches patterns like:
    - ok, okay
    - vamos, pode seguir, pode continuar, segue
    - beleza, blz, tá bom, certo
    - uai, partiu
    
    Args:
        text: User input text
        
    Returns:
        True if text is a vague acknowledgment, False otherwise
    """
    if not text:
        return False
    
    normalized = _normalize_text(text)
    
    # Pattern for vague acknowledgments (must match entire string or be very short)
    vague_pattern = r'^\s*(ok(ay)?|vamos|pode\s+(seguir|continuar)|segue|blz|beleza|ta\s+bom|certo|uai|partiu|entendido|perfeito|manda)\s*\.?!?\s*$'
    
    return bool(re.match(vague_pattern, normalized, re.IGNORECASE))


def is_uncertain_value(text: str) -> bool:
    """
    Detects expressions of uncertainty or lack of knowledge about a value/information.
    
    Matches patterns like:
    - "não sei", "nao sei", "não tenho ideia"
    - "ainda não sei o valor"
    - "não faço ideia do valor"
    - "sem noção do preço"
    - "difícil estimar"
    - "não sei as normas"
    - "sem base", "sem ideia"
    - "por enquanto nada"
    - "desconheço"
    
    Args:
        text: User input text
        
    Returns:
        True if text expresses uncertainty, False otherwise
    """
    if not text:
        return False
    
    normalized = _normalize_text(text)
    
    # Patterns for uncertainty expressions
    uncertainty_keywords = [
        r'nao\s+sei',
        r'n\s+sei',
        r'\bns\b',
        r'desconheco',
        r'nao\s+tenho\s+(certeza|ideia|nocao)',
        r'sem\s+(nocao|ideia|base)',
        r'dificil\s+estimar',
        r'nao\s+faco\s+ideia',
        r'ainda\s+nao\s+sei',
        r'por\s+enquanto\s+nada',
        r'nao\s+tenho\s+isso',
    ]
    
    for pattern in uncertainty_keywords:
        if re.search(pattern, normalized):
            return True
    
    return False


def is_select_number(text: str) -> Optional[int]:
    """
    Detects if text is a simple numeric selection (1-9).
    
    Args:
        text: User input text
        
    Returns:
        The selected number (1-9) if valid, None otherwise
    """
    if not text:
        return None
    
    normalized = text.strip()
    
    # Pattern for single digit selection
    match = re.match(r'^\s*([1-9])\s*$', normalized)
    
    if match:
        return int(match.group(1))
    
    return None


def select_strategy_by_name(text: str, strategy_titles: list) -> Optional[int]:
    """
    Attempts to match user input to a strategy title using fuzzy matching.
    
    Matches both:
    - Exact substring matches (case-insensitive, accent-insensitive)
    - Partial word matches (Jaccard similarity)
    
    Args:
        text: User input text
        strategy_titles: List of available strategy titles
        
    Returns:
        Index of matched strategy (0-based), or None if no match
    """
    if not text or not strategy_titles:
        return None
    
    normalized_input = _normalize_text(text)
    
    # Try exact substring match first
    for i, title in enumerate(strategy_titles):
        normalized_title = _normalize_text(title)
        
        # Check if input is substring of title or vice versa
        if normalized_input in normalized_title or normalized_title in normalized_input:
            return i
    
    # Try fuzzy word-based matching
    input_words = set(re.findall(r'\w+', normalized_input))
    if not input_words:
        return None
    
    best_score = 0
    best_idx = None
    
    for i, title in enumerate(strategy_titles):
        normalized_title = _normalize_text(title)
        title_words = set(re.findall(r'\w+', normalized_title))
        
        if not title_words:
            continue
        
        # Jaccard similarity
        intersection = len(input_words & title_words)
        union = len(input_words | title_words)
        
        if union > 0:
            score = intersection / union
            
            # Boost score if significant word overlap
            if score > 0.3 and score > best_score:
                best_score = score
                best_idx = i
    
    # Return match only if score is reasonably high
    if best_score >= 0.4:
        return best_idx
    
    return None


def is_explicit_pending_request(text: str) -> bool:
    """
    Detects if user explicitly requests to mark something as "Pendente".
    
    Matches patterns like:
    - "pode deixar pendente"
    - "aceito pendente"
    - "registre pendente"
    - "marque como pendente"
    
    Args:
        text: User input text
        
    Returns:
        True if user explicitly requests "Pendente", False otherwise
    """
    if not text:
        return False
    
    normalized = _normalize_text(text)
    
    # Patterns for explicit pending requests
    pending_patterns = [
        r'(pode\s+)?deixar\s+pendente',
        r'aceito?\s+pendente',
        r'registr(e|ar)\s+(como\s+)?pendente',
        r'marqu(e|ar)\s+(como\s+)?pendente',
        r'fica\s+pendente',
        r'deixa\s+pendente',
    ]
    
    for pattern in pending_patterns:
        if re.search(pattern, normalized):
            return True
    
    return False
