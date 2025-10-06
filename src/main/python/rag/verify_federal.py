"""
Módulo para verificação de normas federais no sistema RAG.
Fornece funcionalidades para verificar e validar normas federais específicas.
"""

import re
import logging
from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class FederalDocumentType(Enum):
    """Tipos de documentos federais"""
    LEI_FEDERAL = "lei_federal"
    DECRETO_FEDERAL = "decreto_federal"
    MEDIDA_PROVISORIA = "medida_provisoria"
    LEI_COMPLEMENTAR = "lei_complementar"
    EMENDA_CONSTITUCIONAL = "emenda_constitucional"
    PORTARIA_MINISTERIAL = "portaria_ministerial"
    INSTRUCAO_NORMATIVA = "instrucao_normativa"
    RESOLUCAO_FEDERAL = "resolucao_federal"

@dataclass
class FederalNorm:
    """Estrutura de dados para norma federal"""
    document_type: FederalDocumentType
    number: str
    year: Optional[str] = None
    issuing_body: Optional[str] = None
    title: Optional[str] = None
    publication_date: Optional[datetime] = None
    is_valid: bool = True
    revoked_by: Optional[str] = None
    summary: Optional[str] = None

class FederalNormVerifier:
    """Verificador de normas federais"""
    
    def __init__(self):
        self.federal_bodies = {
            'presidencia': ['presidência da república', 'casa civil', 'secretaria-geral'],
            'ministerios': [
                'ministério da justiça', 'ministério da fazenda', 'ministério da saúde',
                'ministério da educação', 'ministério do trabalho', 'ministério da defesa',
                'ministério do desenvolvimento regional', 'ministério da economia',
                'ministério da infraestrutura', 'ministério do meio ambiente',
                'ministério da cidadania', 'ministério da agricultura',
                'ministério de minas e energia', 'ministério das comunicações',
                'ministério do turismo', 'ministério da ciência e tecnologia'
            ],
            'orgaos_controle': [
                'controladoria-geral da união', 'cgu', 'tribunal de contas da união',
                'tcu', 'advocacia-geral da união', 'agu'
            ],
            'legislativo': [
                'congresso nacional', 'senado federal', 'câmara dos deputados',
                'camara dos deputados'
            ]
        }
        
        self.known_federal_laws = {
            # Leis importantes e frequentemente citadas
            '8666/1993': {
                'title': 'Lei de Licitações e Contratos (revogada)',
                'status': 'revogada',
                'revoked_by': 'Lei 14.133/2021'
            },
            '14133/2021': {
                'title': 'Nova Lei de Licitações e Contratos',
                'status': 'vigente'
            },
            '8112/1990': {
                'title': 'Regime Jurídico dos Servidores Públicos Civis da União',
                'status': 'vigente'
            },
            '12527/2011': {
                'title': 'Lei de Acesso à Informação',
                'status': 'vigente'
            },
            '13709/2018': {
                'title': 'Lei Geral de Proteção de Dados Pessoais (LGPD)',
                'status': 'vigente'
            },
            '4320/1964': {
                'title': 'Lei de Normas Gerais de Direito Financeiro',
                'status': 'vigente'
            },
            '101/2000': {
                'title': 'Lei de Responsabilidade Fiscal',
                'status': 'vigente'
            }
        }

    def verify_federal_norm(self, text: str) -> Dict:
        """
        Verifica se o texto contém normas federais válidas.
        
        Args:
            text: Texto para verificação
            
        Returns:
            Dicionário com resultado da verificação
        """
        result = {
            'is_federal': False,
            'federal_norms': [],
            'issuing_bodies': [],
            'confidence_score': 0.0,
            'verification_details': []
        }
        
        try:
            # Buscar normas federais no texto
            federal_norms = self._extract_federal_norms(text)
            
            # Buscar órgãos emissores
            issuing_bodies = self._identify_issuing_bodies(text)
            
            # Calcular score de confiança
            confidence = self._calculate_federal_confidence(text, federal_norms, issuing_bodies)
            
            result.update({
                'is_federal': confidence > 0.6,
                'federal_norms': federal_norms,
                'issuing_bodies': issuing_bodies,
                'confidence_score': confidence,
                'verification_details': self._generate_verification_details(
                    text, federal_norms, issuing_bodies, confidence
                )
            })
            
        except Exception as e:
            logger.error(f"Erro na verificação federal: {str(e)}")
            result['verification_details'].append(f"Erro: {str(e)}")
        
        return result

    def _extract_federal_norms(self, text: str) -> List[Dict]:
        """Extrai normas federais específicas do texto"""
        federal_norms = []
        text_lower = text.lower()
        
        # Padrões para diferentes tipos de normas federais
        patterns = {
            FederalDocumentType.LEI_FEDERAL: [
                r'lei\s+(?:federal\s+)?n[oº°]?\s*(\d+(?:[\.\/\-]\d+)*)',
                r'lei\s+(\d+(?:[\.\/\-]\d+)*)'
            ],
            FederalDocumentType.DECRETO_FEDERAL: [
                r'decreto\s+(?:federal\s+)?n[oº°]?\s*(\d+(?:[\.\/\-]\d+)*)'
            ],
            FederalDocumentType.MEDIDA_PROVISORIA: [
                r'medida\s+provis[óo]ria\s+n[oº°]?\s*(\d+(?:[\.\/\-]\d+)*)',
                r'mp\s+n[oº°]?\s*(\d+(?:[\.\/\-]\d+)*)'
            ],
            FederalDocumentType.LEI_COMPLEMENTAR: [
                r'lei\s+complementar\s+n[oº°]?\s*(\d+(?:[\.\/\-]\d+)*)'
            ]
        }
        
        for doc_type, type_patterns in patterns.items():
            for pattern in type_patterns:
                matches = re.finditer(pattern, text_lower, re.IGNORECASE)
                
                for match in matches:
                    norm_number = match.group(1)
                    
                    # Verificar se é uma norma conhecida
                    known_info = self.known_federal_laws.get(norm_number, {})
                    
                    federal_norm = {
                        'type': doc_type,
                        'number': norm_number,
                        'full_match': match.group(0),
                        'position': (match.start(), match.end()),
                        'is_known': bool(known_info),
                        'title': known_info.get('title', ''),
                        'status': known_info.get('status', 'unknown'),
                        'context': self._extract_norm_context(text, match.start(), match.end())
                    }
                    
                    federal_norms.append(federal_norm)
        
        return self._deduplicate_norms(federal_norms)

    def _identify_issuing_bodies(self, text: str) -> List[Dict]:
        """Identifica órgãos emissores federais no texto"""
        issuing_bodies = []
        text_lower = text.lower()
        
        for category, bodies in self.federal_bodies.items():
            for body in bodies:
                if body in text_lower:
                    # Encontrar posição exata (case-insensitive)
                    pattern = re.escape(body)
                    matches = re.finditer(pattern, text_lower, re.IGNORECASE)
                    
                    for match in matches:
                        issuing_bodies.append({
                            'name': body,
                            'category': category,
                            'position': (match.start(), match.end()),
                            'context': self._extract_norm_context(
                                text, match.start(), match.end(), context_size=100
                            )
                        })
        
        return issuing_bodies

    def _calculate_federal_confidence(self, text: str, norms: List[Dict], 
                                    bodies: List[Dict]) -> float:
        """Calcula score de confiança de que o texto trata de normas federais"""
        score = 0.0
        text_lower = text.lower()
        
        # Peso por normas federais encontradas
        if norms:
            score += min(len(norms) * 0.3, 0.6)  # Máximo 0.6
            
            # Bonus para normas conhecidas
            known_norms = sum(1 for norm in norms if norm['is_known'])
            score += min(known_norms * 0.1, 0.2)  # Máximo 0.2
        
        # Peso por órgãos emissores identificados
        if bodies:
            score += min(len(bodies) * 0.15, 0.3)  # Máximo 0.3
        
        # Indicadores textuais de âmbito federal
        federal_indicators = [
            'união', 'federal', 'república', 'brasil', 'nacional',
            'congresso nacional', 'presidente da república',
            'ministério', 'secretaria especial'
        ]
        
        found_indicators = sum(1 for indicator in federal_indicators if indicator in text_lower)
        score += min(found_indicators * 0.05, 0.25)  # Máximo 0.25
        
        # Penalizar se houver indicadores de outros âmbitos
        other_scope_indicators = ['estadual', 'municipal', 'prefeitura', 'governo do estado']
        other_indicators = sum(1 for indicator in other_scope_indicators if indicator in text_lower)
        score -= min(other_indicators * 0.1, 0.3)
        
        return max(0.0, min(1.0, score))

    def _extract_norm_context(self, text: str, start_pos: int, end_pos: int, 
                            context_size: int = 150) -> str:
        """Extrai contexto ao redor de uma norma ou órgão"""
        context_start = max(0, start_pos - context_size)
        context_end = min(len(text), end_pos + context_size)
        return text[context_start:context_end].strip()

    def _deduplicate_norms(self, norms: List[Dict]) -> List[Dict]:
        """Remove normas duplicadas"""
        seen = set()
        unique_norms = []
        
        for norm in norms:
            key = (norm['type'], norm['number'])
            if key not in seen:
                seen.add(key)
                unique_norms.append(norm)
        
        return unique_norms

    def _generate_verification_details(self, text: str, norms: List[Dict], 
                                     bodies: List[Dict], confidence: float) -> List[str]:
        """Gera detalhes da verificação"""
        details = []
        
        if norms:
            details.append(f"Encontradas {len(norms)} normas federais no texto")
            known_count = sum(1 for norm in norms if norm['is_known'])
            if known_count > 0:
                details.append(f"{known_count} normas são reconhecidas na base de dados")
        
        if bodies:
            details.append(f"Identificados {len(bodies)} órgãos emissores federais")
            
        details.append(f"Score de confiança federal: {confidence:.2f}")
        
        if confidence > 0.8:
            details.append("Alta confiança: documento claramente federal")
        elif confidence > 0.6:
            details.append("Confiança moderada: provável documento federal")
        elif confidence > 0.3:
            details.append("Baixa confiança: possível documento federal")
        else:
            details.append("Confiança muito baixa: provavelmente não é documento federal")
        
        return details

    def validate_federal_law_reference(self, law_reference: str) -> Tuple[bool, Dict]:
        """
        Valida uma referência específica de lei federal.
        
        Args:
            law_reference: Referência à lei (ex: "Lei 14.133/2021")
            
        Returns:
            Tupla com (é_válida, informações)
        """
        try:
            # Extrair número da lei
            pattern = r'(?:lei\s+)?(?:federal\s+)?(?:complementar\s+)?(?:n[oº°]?\s*)?(\d+(?:[\.\/\-]\d+)*)'
            match = re.search(pattern, law_reference.lower())
            
            if not match:
                return False, {'error': 'Formato de referência inválido'}
            
            law_number = match.group(1)
            
            # Verificar se é uma lei conhecida
            if law_number in self.known_federal_laws:
                law_info = self.known_federal_laws[law_number].copy()
                law_info['number'] = law_number
                law_info['is_valid'] = law_info.get('status') != 'revogada'
                return True, law_info
            
            # Se não é conhecida, fazer validação básica
            return True, {
                'number': law_number,
                'title': 'Lei federal não catalogada',
                'status': 'unknown',
                'is_valid': True,
                'note': 'Lei não encontrada na base de dados local'
            }
            
        except Exception as e:
            return False, {'error': f'Erro na validação: {str(e)}'}

    def get_related_norms(self, law_number: str) -> List[Dict]:
        """Retorna normas relacionadas a uma lei específica"""
        related = []
        
        # Verificar se a lei foi revogada ou revoga outras
        if law_number in self.known_federal_laws:
            law_info = self.known_federal_laws[law_number]
            
            # Se foi revogada
            if law_info.get('revoked_by'):
                revoked_by = law_info['revoked_by']
                related.append({
                    'type': 'revoga',
                    'norm': revoked_by,
                    'description': f'Esta lei foi revogada pela {revoked_by}'
                })
            
            # Se revoga outras (buscar na base)
            for other_number, other_info in self.known_federal_laws.items():
                if other_info.get('revoked_by') and law_number in other_info['revoked_by']:
                    related.append({
                        'type': 'revogada',
                        'norm': f'Lei {other_number}',
                        'description': f'Esta lei revoga a Lei {other_number}'
                    })
        
        return related


def verify_federal_document(text: str) -> Dict:
    """
    Função de conveniência para verificar se um documento é federal.
    
    Args:
        text: Texto do documento
        
    Returns:
        Resultado da verificação federal
    """
    verifier = FederalNormVerifier()
    return verifier.verify_federal_norm(text)


def validate_law_reference(law_reference: str) -> Tuple[bool, Dict]:
    """
    Função de conveniência para validar referência de lei federal.
    
    Args:
        law_reference: Referência à lei
        
    Returns:
        Tupla com (é_válida, informações)
    """
    verifier = FederalNormVerifier()
    return verifier.validate_federal_law_reference(law_reference)


def get_federal_law_info(law_number: str) -> Optional[Dict]:
    """
    Função de conveniência para obter informações de uma lei federal.
    
    Args:
        law_number: Número da lei (ex: "14133/2021")
        
    Returns:
        Informações da lei ou None se não encontrada
    """
    verifier = FederalNormVerifier()
    
    if law_number in verifier.known_federal_laws:
        info = verifier.known_federal_laws[law_number].copy()
        info['number'] = law_number
        info['related_norms'] = verifier.get_related_norms(law_number)
        return info
    
    return None