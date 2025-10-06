import requests
import json
from datetime import datetime, timedelta
from lxml import etree
from typing import Dict, Optional, Any
import logging
import os

from domain.interfaces.dataprovider.DatabaseConfig import db
from domain.dto.KbDto import LegalNormCache

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def resolve_lexml(tipo: str, numero: str, ano: int) -> Dict[str, Any]:
    """
    Consulta o webservice SRU do LexML para verificar a vigência de uma norma federal.
    
    Args:
        tipo: Tipo da norma (Lei, Decreto, etc.)
        numero: Número da norma
        ano: Ano da norma
        
    Returns:
        Dict com urn, label, status e metadados da norma
    """
    
    # Construir identificador único para busca no cache
    norm_identifier = f"{tipo} {numero}/{ano}"
    
    # Verificar cache primeiro (busca por norm_label que contém a identificação)
    cache_entry = LegalNormCache.query.filter(
        LegalNormCache.norm_label.contains(f"{tipo} {numero}/{ano}"),
        LegalNormCache.sphere == "federal"
    ).first()
    
    if cache_entry and cache_entry.is_recent(days=7):
        logger.info(f"Cache hit for {tipo} {numero}/{ano}")
        return {
            'urn': cache_entry.norm_urn,
            'label': cache_entry.norm_label,
            'status': cache_entry.status,
            'metadados': cache_entry.get_source_data(),
            'verified': bool(cache_entry.norm_urn),
            'cached': True
        }
    
    # Se não está no cache ou expirou, consultar LexML
    logger.info(f"Querying LexML for {tipo} {numero}/{ano}")
    
    try:
        # Construir consulta CQL para o SRU do LexML
        # Restringir ao acervo federal
        cql_query = f'dc.type="{tipo}" AND dc.identifier="{numero}" AND dc.date="{ano}" AND dc.coverage="BR"'
        
        # URL do webservice SRU do LexML
        sru_url = "http://legis.senado.leg.br/dadosabertos/dados/ListaDocumentos"
        
        params = {
            'operation': 'searchRetrieve',
            'version': '1.2',
            'query': cql_query,
            'recordSchema': 'marcxml',
            'maximumRecords': '10'
        }
        
        # Fazer requisição HTTP
        response = requests.get(sru_url, params=params, timeout=30)
        response.raise_for_status()
        
        # Parsear XML usando lxml
        root = etree.fromstring(response.content)
        
        # Namespaces do SRU/XML
        namespaces = {
            'srw': 'http://www.loc.gov/zing/srw/',
            'marc': 'http://www.loc.gov/MARC21/slim'
        }
        
        # Verificar se encontrou registros
        num_records = root.xpath('//srw:numberOfRecords/text()', namespaces=namespaces)
        if not num_records or int(num_records[0]) == 0:
            # Não encontrou a norma
            result = {
                'urn': None,
                'label': f"{tipo} {numero}/{ano}",
                'status': 'não encontrada',
                'metadados': {},
                'verified': False,
                'cached': False
            }
        else:
            # Extrair dados do primeiro registro
            record = root.xpath('//srw:record[1]', namespaces=namespaces)[0]
            
            # Extrair URN (campo 024)
            urn_fields = record.xpath('.//marc:datafield[@tag="024"]/marc:subfield[@code="a"]/text()', 
                                    namespaces=namespaces)
            urn = urn_fields[0] if urn_fields else None
            
            # Extrair título/label (campo 245)
            title_fields = record.xpath('.//marc:datafield[@tag="245"]/marc:subfield[@code="a"]/text()', 
                                      namespaces=namespaces)
            label = title_fields[0].strip() if title_fields else f"{tipo} {numero}/{ano}"
            
            # Extrair status/situação (campo 500 ou similar)
            status_fields = record.xpath('.//marc:datafield[@tag="500"]/marc:subfield[@code="a"]/text()', 
                                       namespaces=namespaces)
            status = 'vigente' if urn else 'status desconhecido'
            
            # Coletar metadados adicionais
            metadados = {
                'fonte': 'LexML',
                'data_consulta': datetime.utcnow().isoformat(),
                'titulo_completo': label,
                'urn_lexml': urn
            }
            
            # Extrair outros campos relevantes se disponíveis
            ementa_fields = record.xpath('.//marc:datafield[@tag="520"]/marc:subfield[@code="a"]/text()', 
                                       namespaces=namespaces)
            if ementa_fields:
                metadados['ementa'] = ementa_fields[0]
            
            result = {
                'urn': urn,
                'label': label,
                'status': status,
                'metadados': metadados,
                'verified': bool(urn),
                'cached': False
            }
        
        # Salvar no cache com o modelo existente
        if cache_entry:
            # Atualizar entrada existente
            cache_entry.norm_urn = result['urn'] or ""
            cache_entry.norm_label = result['label']
            cache_entry.status = result['status']
            cache_entry.set_source_data(result['metadados'])
            cache_entry.last_verified_at = datetime.utcnow()
        else:
            # Criar nova entrada
            cache_entry = LegalNormCache(
                norm_urn=result['urn'] or f"norma:{tipo}:{numero}:{ano}",
                norm_label=result['label'],
                sphere="federal",
                status=result['status'],
                last_verified_at=datetime.utcnow()
            )
            cache_entry.set_source_data(result['metadados'])
            db.session.add(cache_entry)
        
        db.session.commit()
        logger.info(f"Cached result for {tipo} {numero}/{ano}")
        
        return result
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error querying LexML for {tipo} {numero}/{ano}: {str(e)}")
        
        # Fallback para falha de rede
        result = {
            'urn': None,
            'label': f"{tipo} {numero}/{ano}",
            'status': 'status desconhecido',
            'metadados': {'erro': 'Falha de rede na consulta ao LexML'},
            'verified': False,
            'cached': False
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing LexML response for {tipo} {numero}/{ano}: {str(e)}")
        
        # Fallback para outros erros
        result = {
            'urn': None,
            'label': f"{tipo} {numero}/{ano}",
            'status': 'status desconhecido',
            'metadados': {'erro': f'Erro no processamento: {str(e)}'},
            'verified': False,
            'cached': False
        }
        
        return result


def summarize_for_user(entry: Dict[str, Any], openai_client=None) -> str:
    """
    Gera um resumo curto do status da norma legal usando OpenAI.
    
    Args:
        entry: Resultado da consulta resolve_lexml
        openai_client: Cliente OpenAI configurado
        
    Returns:
        String com resumo do status explicitando "fonte: LexML"
    """
    
    if not openai_client:
        # Fallback sem IA
        if entry['verified']:
            return f"Norma {entry['label']} encontrada no LexML com status '{entry['status']}'. Fonte: LexML"
        else:
            return f"Norma {entry['label']} não verificada. {entry['status']}. Fonte: LexML"
    
    try:
        # Verificar se já há resumo no cache
        if 'cached' in entry and entry['cached']:
            cache_entry = LegalNormCache.query.filter(
                LegalNormCache.norm_label.contains(f"{entry.get('tipo', '')} {entry.get('numero', '')}/{entry.get('ano', 0)}"),
                LegalNormCache.sphere == "federal"
            ).first()
            if cache_entry:
                # Como o modelo existente não tem campo ai_summary, vamos usar o source_data
                source_data = cache_entry.get_source_data()
                if source_data.get('ai_summary'):
                    return source_data['ai_summary']
        
        # Construir prompt para o OpenAI
        status_info = entry['status']
        urn_info = f"URN LexML: {entry['urn']}" if entry['urn'] else "URN não encontrada"
        metadados = entry.get('metadados', {})
        
        prompt = f"""
        Baseado nas informações abaixo sobre uma norma legal brasileira, escreva um resumo curto (máximo 2 frases) do status da norma para um usuário leigo.

        Norma: {entry['label']}
        Status: {status_info}
        {urn_info}
        Verificada: {'Sim' if entry['verified'] else 'Não'}
        
        IMPORTANTE: 
        - Termine sempre com "Fonte: LexML"
        - Use linguagem clara e direta
        - Se a norma não foi encontrada ou verificada, explique isso de forma simples
        - Máximo 2 frases
        """
        
        # Chamar OpenAI
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Você é um assistente especializado em explicar informações legais de forma simples e clara."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.3
        )
        
        summary = response.choices[0].message.content.strip()
        
        # Salvar resumo no cache se possível
        try:
            cache_entry = LegalNormCache.query.filter(
                LegalNormCache.norm_label.contains(f"{entry.get('tipo', '')} {entry.get('numero', '')}/{entry.get('ano', 0)}"),
                LegalNormCache.sphere == "federal"
            ).first()
            if cache_entry:
                # Salvar AI summary no source_data JSON
                source_data = cache_entry.get_source_data()
                source_data['ai_summary'] = summary
                cache_entry.set_source_data(source_data)
                db.session.commit()
        except Exception as cache_error:
            logger.warning(f"Could not save AI summary to cache: {str(cache_error)}")
        
        return summary
        
    except Exception as e:
        logger.error(f"Error generating AI summary: {str(e)}")
        
        # Fallback em caso de erro na IA
        if entry['verified']:
            return f"Norma {entry['label']} encontrada e verificada no LexML. Status: {entry['status']}. Fonte: LexML"
        else:
            return f"Norma {entry['label']} não pôde ser verificada. {entry['status']}. Fonte: LexML"


def parse_legal_norm_string(norm_string: str) -> Optional[Dict[str, Any]]:
    """
    Parseia uma string de norma legal para extrair tipo, número e ano.
    
    Exemplos:
    - "Lei 14.133/2021" -> {"tipo": "Lei", "numero": "14.133", "ano": 2021}
    - "Decreto 10.024/2019" -> {"tipo": "Decreto", "numero": "10.024", "ano": 2019}
    
    Args:
        norm_string: String da norma legal
        
    Returns:
        Dict com tipo, numero e ano ou None se não conseguir parsear
    """
    
    import re
    
    # Padrão para capturar: Tipo Número/Ano
    pattern = r'^([A-Za-z\s]+)\s+([0-9.]+)\/([0-9]{4})$'
    
    match = re.match(pattern, norm_string.strip())
    if match:
        tipo = match.group(1).strip()
        numero = match.group(2).strip()
        ano = int(match.group(3))
        
        return {
            'tipo': tipo,
            'numero': numero,
            'ano': ano
        }
    
    return None