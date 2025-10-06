import re
from typing import List, Dict, Any, Optional


def extract_citations(texto: str) -> List[Dict[str, Any]]:
    """
    Extrai citações de normas legais do texto usando regex robusta.
    
    Args:
        texto (str): Texto para análise de citações legais
        
    Returns:
        List[Dict[str, Any]]: Lista de dicionários com {tipo, numero, ano}
    """
    # Regex robusta para capturar diferentes formatos de normas legais
    pattern = r"(?i)\b(Lei(?:\s+(?:Complementar|Estadual|Municipal|Distrital|Federal))?|Decreto(?:\s+(?:Estadual|Municipal|Distrital|Federal))?|Instrução\s+Normativa|Portaria)\s*(?:n[ºo.]?\s*)?(\d{1,5}(?:\.\d{3})*)\s*(?:/|\s+de\s+)(\d{2,4})"
    
    citations = []
    matches = re.finditer(pattern, texto)
    
    for match in matches:
        tipo = match.group(1).strip()
        numero = match.group(2).strip().replace(".", "")  # Remove dots from number
        ano = match.group(3).strip()
        
        # Normalizar o tipo
        tipo_normalizado = _normalize_legal_type(tipo)
        
        # Garantir que o ano tenha 4 dígitos
        if len(ano) == 2:
            # Assumir que anos 00-30 são 2000-2030, 31-99 são 1931-1999
            if int(ano) <= 30:
                ano = "20" + ano
            else:
                ano = "19" + ano
        
        citation = {
            "tipo": tipo_normalizado,
            "numero": numero,
            "ano": ano,
            "texto_original": match.group(0)
        }
        
        citations.append(citation)
    
    return citations


def filter_federal(citations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filtra citações para manter apenas as federais e adiciona campo sphere="federal".
    
    Args:
        citations (List[Dict[str, Any]]): Lista de citações extraídas
        
    Returns:
        List[Dict[str, Any]]: Lista filtrada com citações federais
    """
    federal_citations = []
    
    # Tipos clássicos federais
    federal_types = {
        "Lei",
        "Lei Complementar", 
        "Decreto",
        "Instrução Normativa",
        "Portaria"
    }
    
    # Leis conhecidas como federais (exemplos importantes)
    known_federal_laws = {
        "8666",  # Lei de Licitações
        "14133", # Nova Lei de Licitações
        "8429",  # Lei de Improbidade
        "12527", # Lei de Acesso à Informação
        "13303", # Lei das Estatais
        "8112",  # Regime Jurídico Único
    }
    
    for citation in citations:
        is_federal = False
        
        # Verificar se o tipo é classicamente federal
        if citation.get("tipo") in federal_types:
            is_federal = True
            
        # Verificar se é uma lei conhecidamente federal
        if citation.get("tipo") == "Lei" and citation.get("numero") in known_federal_laws:
            is_federal = True
            
        # Verificar se há indicação explícita de esfera estadual/municipal no texto original
        texto_original = citation.get("texto_original", "").lower()
        if any(keyword in texto_original for keyword in ["estadual", "municipal", "distrital"]):
            is_federal = False
            
        if is_federal:
            federal_citation = citation.copy()
            federal_citation["sphere"] = "federal"
            federal_citations.append(federal_citation)
    
    return federal_citations


def suggest_federal(objective_slug: str, k: int = 6) -> List[Dict[str, Any]]:
    """
    Sugere normas federais baseado no slug do objetivo usando frequência e busca híbrida.
    
    Args:
        objective_slug (str): Slug do objetivo da contratação
        k (int): Número de sugestões a retornar (padrão: 6)
        
    Returns:
        List[Dict[str, Any]]: Lista ranqueada de normas federais sugeridas
    """
    # Base de conhecimento de normas federais por área/objetivo
    federal_norms_knowledge = {
        # Licitações e Contratos
        "licitacao": [
            {"tipo": "Lei", "numero": "14133", "ano": "2021", "relevancia": 10, "descricao": "Nova Lei de Licitações e Contratos"},
            {"tipo": "Lei", "numero": "8666", "ano": "1993", "relevancia": 9, "descricao": "Lei de Licitações (revogada parcialmente)"},
            {"tipo": "Decreto", "numero": "10024", "ano": "2019", "relevancia": 8, "descricao": "Regulamenta licitação eletrônica"},
        ],
        "contrato": [
            {"tipo": "Lei", "numero": "14133", "ano": "2021", "relevancia": 10, "descricao": "Nova Lei de Licitações e Contratos"},
            {"tipo": "Lei", "numero": "13303", "ano": "2016", "relevancia": 7, "descricao": "Lei das Estatais"},
        ],
        # Tecnologia da Informação
        "tecnologia": [
            {"tipo": "Instrução Normativa", "numero": "1", "ano": "2019", "relevancia": 9, "descricao": "Processo de Contratação de TIC"},
            {"tipo": "Lei", "numero": "13709", "ano": "2018", "relevancia": 8, "descricao": "Lei Geral de Proteção de Dados"},
            {"tipo": "Lei", "numero": "14133", "ano": "2021", "relevancia": 7, "descricao": "Nova Lei de Licitações"},
        ],
        "software": [
            {"tipo": "Instrução Normativa", "numero": "1", "ano": "2019", "relevancia": 10, "descricao": "Processo de Contratação de TIC"},
            {"tipo": "Lei", "numero": "13709", "ano": "2018", "relevancia": 8, "descricao": "LGPD"},
        ],
        # Obras e Serviços
        "obra": [
            {"tipo": "Lei", "numero": "14133", "ano": "2021", "relevancia": 10, "descricao": "Nova Lei de Licitações"},
            {"tipo": "Lei", "numero": "12462", "ano": "2011", "relevancia": 7, "descricao": "Regime Diferenciado de Contratações"},
        ],
        "servico": [
            {"tipo": "Lei", "numero": "14133", "ano": "2021", "relevancia": 10, "descricao": "Nova Lei de Licitações"},
            {"tipo": "Lei", "numero": "8666", "ano": "1993", "relevancia": 8, "descricao": "Lei de Licitações"},
        ],
        # Padrão geral
        "default": [
            {"tipo": "Lei", "numero": "14133", "ano": "2021", "relevancia": 10, "descricao": "Nova Lei de Licitações e Contratos"},
            {"tipo": "Lei", "numero": "8429", "ano": "1992", "relevancia": 7, "descricao": "Lei de Improbidade Administrativa"},
            {"tipo": "Lei", "numero": "12527", "ano": "2011", "relevancia": 6, "descricao": "Lei de Acesso à Informação"},
        ]
    }
    
    # Encontrar normas relevantes baseado no slug
    relevant_norms = []
    objective_lower = objective_slug.lower()
    
    # Buscar correspondências diretas por palavras-chave
    for category, norms in federal_norms_knowledge.items():
        if category in objective_lower or any(word in objective_lower for word in category.split("_")):
            for norm in norms:
                norm_copy = norm.copy()
                norm_copy["sphere"] = "federal"
                relevant_norms.append(norm_copy)
    
    # Se não encontrou correspondências específicas, usar padrão
    if not relevant_norms:
        for norm in federal_norms_knowledge["default"]:
            norm_copy = norm.copy()
            norm_copy["sphere"] = "federal"
            relevant_norms.append(norm_copy)
    
    # Remover duplicatas e ordenar por relevância
    seen = set()
    unique_norms = []
    for norm in relevant_norms:
        norm_key = (norm["tipo"], norm["numero"], norm["ano"])
        if norm_key not in seen:
            seen.add(norm_key)
            unique_norms.append(norm)
    
    # Ordenar por relevância (decrescente) e limitar ao número solicitado
    unique_norms.sort(key=lambda x: x.get("relevancia", 0), reverse=True)
    
    return unique_norms[:k]


def _normalize_legal_type(tipo: str) -> str:
    """
    Normaliza o tipo de norma legal para formato padrão.
    
    Args:
        tipo (str): Tipo original extraído do regex
        
    Returns:
        str: Tipo normalizado
    """
    tipo_lower = tipo.lower().strip()
    
    if "lei complementar" in tipo_lower:
        return "Lei Complementar"
    elif "lei" in tipo_lower:
        return "Lei"
    elif "decreto" in tipo_lower:
        return "Decreto"
    elif "instrução" in tipo_lower and "normativa" in tipo_lower:
        return "Instrução Normativa"
    elif "portaria" in tipo_lower:
        return "Portaria"
    else:
        # Capitalizar primeira letra de cada palavra
        return " ".join(word.capitalize() for word in tipo.split())