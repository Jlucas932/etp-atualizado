"""
Módulo para processamento e validação de normas legais no sistema RAG.
Fornece funcionalidades para categorizar e validar normas jurídicas.
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)

class LegalNormType(Enum):
    """Tipos de normas legais"""
    LEI = "lei"
    DECRETO = "decreto"
    PORTARIA = "portaria"
    RESOLUCAO = "resolucao"
    INSTRUCAO_NORMATIVA = "instrucao_normativa"
    MEDIDA_PROVISORIA = "medida_provisoria"
    LEI_COMPLEMENTAR = "lei_complementar"
    EMENDA_CONSTITUCIONAL = "emenda_constitucional"
    UNKNOWN = "unknown"

class LegalScope(Enum):
    """Âmbito da norma legal"""
    FEDERAL = "federal"
    ESTADUAL = "estadual"
    MUNICIPAL = "municipal"
    UNKNOWN = "unknown"

class LegalNormProcessor:
    """Processador de normas legais"""
    
    def __init__(self):
        self.norm_patterns = {
            LegalNormType.LEI: [
                r'lei\s+(?:federal\s+)?(?:complementar\s+)?n[oº°]?\s*(\d+(?:[\.\/\-]\d+)*)',
                r'lei\s+(\d+(?:[\.\/\-]\d+)*)',
                r'l\.?\s*(\d+(?:[\.\/\-]\d+)*)'
            ],
            LegalNormType.DECRETO: [
                r'decreto\s+n[oº°]?\s*(\d+(?:[\.\/\-]\d+)*)',
                r'decreto\s+(\d+(?:[\.\/\-]\d+)*)',
                r'd\.?\s*(\d+(?:[\.\/\-]\d+)*)'
            ],
            LegalNormType.PORTARIA: [
                r'portaria\s+n[oº°]?\s*(\d+(?:[\.\/\-]\d+)*)',
                r'portaria\s+(\d+(?:[\.\/\-]\d+)*)'
            ],
            LegalNormType.RESOLUCAO: [
                r'resolu[cç][aã]o\s+n[oº°]?\s*(\d+(?:[\.\/\-]\d+)*)',
                r'resolu[cç][aã]o\s+(\d+(?:[\.\/\-]\d+)*)'
            ],
            LegalNormType.INSTRUCAO_NORMATIVA: [
                r'instru[cç][aã]o\s+normativa\s+n[oº°]?\s*(\d+(?:[\.\/\-]\d+)*)',
                r'in\s+n[oº°]?\s*(\d+(?:[\.\/\-]\d+)*)'
            ],
            LegalNormType.MEDIDA_PROVISORIA: [
                r'medida\s+provis[oó]ria\s+n[oº°]?\s*(\d+(?:[\.\/\-]\d+)*)',
                r'mp\s+n[oº°]?\s*(\d+(?:[\.\/\-]\d+)*)'
            ]
        }
        
        self.federal_indicators = [
            'federal', 'união', 'republica', 'brasil', 'cgu', 'tcu', 'tcf',
            'congresso nacional', 'senado federal', 'camara dos deputados',
            'presidencia da republica', 'ministerio', 'secretaria especial'
        ]

    def extract_legal_norms(self, text: str) -> List[Dict]:
        """
        Extrai normas legais do texto fornecido.
        
        Args:
            text: Texto para análise
            
        Returns:
            Lista de normas legais encontradas
        """
        norms = []
        text_lower = text.lower()
        
        for norm_type, patterns in self.norm_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text_lower, re.IGNORECASE)
                
                for match in matches:
                    norm_info = {
                        'type': norm_type,
                        'number': match.group(1),
                        'full_match': match.group(0),
                        'start_pos': match.start(),
                        'end_pos': match.end(),
                        'scope': self._determine_scope(text, match.start(), match.end()),
                        'context': self._extract_context(text, match.start(), match.end())
                    }
                    norms.append(norm_info)
        
        # Remover duplicatas e ordenar por posição
        norms = self._remove_duplicates(norms)
        norms.sort(key=lambda x: x['start_pos'])
        
        return norms

    def _determine_scope(self, text: str, start_pos: int, end_pos: int) -> LegalScope:
        """Determina o âmbito da norma legal"""
        # Analisar contexto ao redor da norma (100 caracteres antes e depois)
        context_start = max(0, start_pos - 100)
        context_end = min(len(text), end_pos + 100)
        context = text[context_start:context_end].lower()
        
        # Verificar indicadores federais
        for indicator in self.federal_indicators:
            if indicator in context:
                return LegalScope.FEDERAL
        
        # Verificar indicadores estaduais
        if any(word in context for word in ['estadual', 'estado', 'governo do estado']):
            return LegalScope.ESTADUAL
        
        # Verificar indicadores municipais
        if any(word in context for word in ['municipal', 'municipio', 'prefeitura', 'camara municipal']):
            return LegalScope.MUNICIPAL
        
        return LegalScope.UNKNOWN

    def _extract_context(self, text: str, start_pos: int, end_pos: int, 
                        context_chars: int = 200) -> str:
        """Extrai contexto ao redor da norma"""
        context_start = max(0, start_pos - context_chars)
        context_end = min(len(text), end_pos + context_chars)
        return text[context_start:context_end].strip()

    def _remove_duplicates(self, norms: List[Dict]) -> List[Dict]:
        """Remove normas duplicadas baseado no número e tipo"""
        seen = set()
        unique_norms = []
        
        for norm in norms:
            key = (norm['type'], norm['number'])
            if key not in seen:
                seen.add(key)
                unique_norms.append(norm)
        
        return unique_norms

    def categorize_by_subject(self, text: str) -> List[str]:
        """
        Categoriza o texto por assunto jurídico.
        
        Args:
            text: Texto para categorização
            
        Returns:
            Lista de categorias identificadas
        """
        categories = []
        text_lower = text.lower()
        
        # Dicionário de categorias e palavras-chave
        category_keywords = {
            'licitacoes': [
                'licitação', 'licitações', 'pregão', 'tomada de preços',
                'concorrência', 'convite', 'dispensa', 'inexigibilidade',
                'edital', 'proposta', 'habilitação'
            ],
            'contratos_publicos': [
                'contrato', 'contratos', 'contratação', 'aditivo',
                'rescisão', 'fiscalização', 'executor', 'gestor'
            ],
            'orcamento_financas': [
                'orçamento', 'crédito', 'empenho', 'liquidação',
                'pagamento', 'receita', 'despesa', 'dotação'
            ],
            'recursos_humanos': [
                'servidor', 'funcionário', 'concurso', 'cargo',
                'função', 'remuneração', 'benefício', 'aposentadoria'
            ],
            'transparencia': [
                'transparência', 'acesso à informação', 'dados abertos',
                'portal', 'publicidade', 'divulgação'
            ],
            'meio_ambiente': [
                'meio ambiente', 'ambiental', 'sustentabilidade',
                'licenciamento', 'impacto ambiental'
            ],
            'saude': [
                'saúde', 'sus', 'vigilância sanitária', 'epidemiologia',
                'medicamento', 'vacina'
            ],
            'educacao': [
                'educação', 'ensino', 'escola', 'universidade',
                'professor', 'aluno', 'currículo'
            ],
            'seguranca': [
                'segurança', 'defesa', 'polícia', 'bombeiro',
                'emergência', 'proteção'
            ]
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                categories.append(category)
        
        return categories

    def validate_norm_format(self, norm_text: str) -> Tuple[bool, str]:
        """
        Valida o formato de uma norma legal.
        
        Args:
            norm_text: Texto da norma para validação
            
        Returns:
            Tupla com (é_válido, mensagem)
        """
        if not norm_text or not norm_text.strip():
            return False, "Texto da norma não pode estar vazio"
        
        # Verificar se contém pelo menos uma referência legal
        norms_found = self.extract_legal_norms(norm_text)
        if not norms_found:
            return False, "Nenhuma referência legal válida encontrada"
        
        # Verificar tamanho mínimo
        if len(norm_text.strip()) < 50:
            return False, "Texto muito curto para ser uma norma legal válida"
        
        # Verificar se contém palavras-chave de contexto legal
        legal_keywords = [
            'artigo', 'art.', 'parágrafo', '§', 'inciso',
            'alínea', 'caput', 'estabelece', 'determina',
            'dispõe', 'regulamenta', 'institui'
        ]
        
        has_legal_context = any(
            keyword in norm_text.lower() 
            for keyword in legal_keywords
        )
        
        if not has_legal_context:
            return False, "Texto não parece conter contexto legal apropriado"
        
        return True, "Formato válido"

    def get_norm_priority(self, norm_type: LegalNormType, scope: LegalScope) -> int:
        """
        Retorna a prioridade hierárquica da norma (1 = maior prioridade).
        
        Args:
            norm_type: Tipo da norma
            scope: Âmbito da norma
            
        Returns:
            Valor de prioridade (menor = maior prioridade)
        """
        # Prioridade por tipo (Constituição seria 1, mas não está nos tipos)
        type_priority = {
            LegalNormType.EMENDA_CONSTITUCIONAL: 2,
            LegalNormType.LEI_COMPLEMENTAR: 3,
            LegalNormType.LEI: 4,
            LegalNormType.MEDIDA_PROVISORIA: 5,
            LegalNormType.DECRETO: 6,
            LegalNormType.INSTRUCAO_NORMATIVA: 7,
            LegalNormType.PORTARIA: 8,
            LegalNormType.RESOLUCAO: 9,
            LegalNormType.UNKNOWN: 10
        }
        
        # Prioridade por âmbito
        scope_priority = {
            LegalScope.FEDERAL: 1,
            LegalScope.ESTADUAL: 2,
            LegalScope.MUNICIPAL: 3,
            LegalScope.UNKNOWN: 4
        }
        
        # Combinar prioridades (tipo tem peso maior)
        return (type_priority.get(norm_type, 10) * 10) + scope_priority.get(scope, 4)


def extract_legal_norms(text: str) -> List[Dict]:
    """
    Função de conveniência para extrair normas legais de um texto.
    
    Args:
        text: Texto para análise
        
    Returns:
        Lista de normas legais encontradas
    """
    processor = LegalNormProcessor()
    return processor.extract_legal_norms(text)


def categorize_legal_text(text: str) -> List[str]:
    """
    Função de conveniência para categorizar texto jurídico por assunto.
    
    Args:
        text: Texto para categorização
        
    Returns:
        Lista de categorias identificadas
    """
    processor = LegalNormProcessor()
    return processor.categorize_by_subject(text)


def validate_legal_norm(norm_text: str) -> Tuple[bool, str]:
    """
    Função de conveniência para validar formato de norma legal.
    
    Args:
        norm_text: Texto da norma para validação
        
    Returns:
        Tupla com (é_válido, mensagem)
    """
    processor = LegalNormProcessor()
    return processor.validate_norm_format(norm_text)