import os
import json
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
import openai
import logging

# Configure logging
logger = logging.getLogger(__name__)

class DynamicPromptGenerator:
    """Gerador dinâmico de prompts para ETPs com integração RAG"""
    
    def __init__(self, openai_api_key: str):
        self.client = openai.OpenAI(api_key=openai_api_key)
        self.rag_retrieval = None
        
    def set_rag_retrieval(self, rag_retrieval):
        """Define o sistema de recuperação RAG"""
        self.rag_retrieval = rag_retrieval
        
    def _clean_json_response(self, response_text: str) -> str:
        """
        Remove delimitadores markdown de respostas JSON da OpenAI
        
        Args:
            response_text: Texto da resposta que pode conter ```json ... ```
            
        Returns:
            str: JSON limpo para parsing
        """
        # Remover delimitadores markdown comuns
        cleaned = response_text.strip()
        
        # Remover ```json no início e ``` no final
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:].strip()
        elif cleaned.startswith('```'):
            cleaned = cleaned[3:].strip()
            
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3].strip()
            
        # Tentar encontrar JSON válido usando regex se ainda houver problemas
        json_pattern = r'\{.*\}'
        match = re.search(json_pattern, cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)
            
        return cleaned
    
    def generate_dynamic_prompt(self, session_data: Dict, section_info: Dict) -> str:
        """Gera prompt dinâmico para o modelo fine-tunado"""
        try:
            # Extrair informações da sessão
            answers = session_data.get('answers', {})
            
            # Construir prompt baseado nas respostas do usuário
            prompt_parts = []
            
            # Adicionar contexto da seção
            prompt_parts.append(f"Gere a seguinte seção do ETP: {section_info['section']}")
            prompt_parts.append(f"Descrição da seção: {section_info['description']}")
            
            # Adicionar instruções detalhadas para conteúdo mais longo e estilizado
            prompt_parts.append("\nINSTRUÇÕES PARA GERAÇÃO DE CONTEÚDO:")
            prompt_parts.append("- Cada parágrafo deve ter entre 4 a 7 linhas de texto detalhado")
            prompt_parts.append("- Desenvolva explicações técnicas aprofundadas com fundamentação legal")
            prompt_parts.append("- Inclua análises contextuais e justificativas técnicas detalhadas")
            prompt_parts.append("- Use linguagem formal e técnica apropriada para documentos oficiais")
            prompt_parts.append("- Apresente argumentações sólidas com base na legislação vigente")
            prompt_parts.append("- Detalhe processos, metodologias e critérios técnicos específicos")
            prompt_parts.append("- Inclua considerações sobre aspectos administrativos, operacionais e estratégicos")
            
            # Adicionar informações das respostas
            if answers:
                prompt_parts.append("\nInformações fornecidas pelo usuário:")
                for question_id, answer in answers.items():
                    if answer:
                        prompt_parts.append(f"- {answer}")
            
            # Adicionar requisitos específicos da seção
            if section_info.get('min_paragraphs'):
                prompt_parts.append(f"\nA seção deve ter EXATAMENTE {section_info['min_paragraphs']} parágrafos substanciais e bem desenvolvidos.")
                prompt_parts.append("Cada parágrafo deve abordar aspectos específicos e complementares do tema.")
            
            if section_info.get('requires_table'):
                prompt_parts.append("\nIncluir tabela formatada com dados específicos quando apropriado.")
                
            if section_info.get('subsections'):
                prompt_parts.append("\nSubseções obrigatórias (desenvolva cada uma detalhadamente):")
                for subsection in section_info['subsections']:
                    prompt_parts.append(f"- {subsection}")
            
            # Adicionar requisitos de qualidade do conteúdo
            prompt_parts.append("\nREQUISITOS DE QUALIDADE:")
            prompt_parts.append("- Conteúdo técnico aprofundado com embasamento teórico")
            prompt_parts.append("- Análises críticas e avaliações técnicas detalhadas")
            prompt_parts.append("- Fundamentação legal específica e referências normativas")
            prompt_parts.append("- Estrutura lógica com progressão argumentativa coerente")
            
            return "\n".join(prompt_parts)
            
        except Exception as e:
            # Fallback simples
            return f"Gere a seção '{section_info['section']}' de um Estudo Técnico Preliminar conforme a Lei 14.133/21."
    
    def get_knowledge_base_info(self) -> Dict:
        """Retorna informações sobre a base de conhecimento (compatibilidade)"""
        return {
            'total_documents': 0,
            'common_sections': [],
            'note': 'Usando modelo fine-tunado - base de conhecimento não necessária'
        }
    
    def refresh_knowledge_base(self) -> Dict:
        """Método de compatibilidade - não faz nada pois não usa PDFs"""
        return self.get_knowledge_base_info()
    
    def generate_requirements_with_rag(self, contracting_need: str, contract_type: str, objective_slug: str = "generic") -> Dict:
        """
        Gera requisitos priorizando consulta RAG, com fallback consultivo
        
        Args:
            contracting_need: Descrição da necessidade de contratação
            contract_type: Tipo de contrato ('produto' ou 'serviço')
            objective_slug: Slug do objetivo para filtrar resultados RAG
            
        Returns:
            Dict com requirements e source_info
        """
        requirements = []
        consultative_message = ""
        source_citations = []
        is_rag_based = False
        
        try:
            # Fase 1: Tentar consulta RAG
            if self.rag_retrieval:
                logger.info(f"[RAG] Iniciando consulta RAG para: {contracting_need}")
                rag_results = self.rag_retrieval.search_requirements(objective_slug, contracting_need, k=5)
                
                if rag_results and len(rag_results) > 0:
                    logger.info(f"[RAG] Encontrados {len(rag_results)} resultados relevantes")
                    
                    # Extrair e processar requisitos dos PDFs
                    rag_requirements = []
                    citations = []
                    
                    for i, result in enumerate(rag_results[:5], 1):
                        content = result.get('content', '').strip()
                        section_title = result.get('section_title', 'Documento')
                        score = result.get('hybrid_score', 0)
                        
                        if content and len(content) > 20:  # Evitar fragmentos muito pequenos
                            # Limpar e formatar conteúdo
                            clean_content = self._clean_and_format_rag_content(content)
                            if clean_content:
                                rag_requirements.append(clean_content)
                                citations.append(f"Trecho {i}: \"{content[:100]}...\" (Fonte: {section_title}, Relevância: {score:.2f})")
                    
                    if rag_requirements:
                        # Formatar requisitos com R# — prefixo
                        formatted_requirements = []
                        for idx, req in enumerate(rag_requirements, 1):
                            formatted_requirements.append(f"R{idx} — {req}")
                        
                        requirements = formatted_requirements
                        source_citations = citations
                        is_rag_based = True
                        consultative_message = "Com base nos documentos da nossa base de conhecimento, identifiquei os seguintes requisitos específicos para esta contratação:"
                        
                        logger.info(f"[RAG] Requisitos extraídos com sucesso: {len(requirements)} requisitos")
                    else:
                        logger.warning("[RAG] Resultados encontrados mas nenhum requisito válido extraído")
                else:
                    logger.info("[RAG] Nenhum resultado relevante encontrado na base de conhecimento")
                        
        except Exception as e:
            logger.error(f"Erro ao consultar RAG: {str(e)}")
        
        # Fase 2: Fallback consultivo se RAG não trouxe resultados
        if not requirements:
            logger.info("[RAG] Fallback: Gerando sugestões consultivas contextualizadas")
            requirements, consultative_message = self._generate_contextual_suggestions(contracting_need, contract_type)
            is_rag_based = False
            logger.info(f"[RAG] Sugestões consultivas geradas: {len(requirements)} requisitos")
        
        return {
            'requirements': requirements,
            'consultative_message': consultative_message,
            'source_citations': source_citations,
            'is_rag_based': is_rag_based,
            'total_rag_results': len(rag_results) if 'rag_results' in locals() and rag_results else 0
        }
    
    def _clean_and_format_rag_content(self, content: str) -> str:
        """Limpa e formata conteúdo extraído do RAG para formato de requisito"""
        # Remover quebras de linha excessivas e espaços
        clean_content = ' '.join(content.split())
        
        # Usar OpenAI para reescrever de forma clara e específica
        try:
            rewrite_prompt = f"""
            Reescreva o seguinte trecho de documento de forma clara e objetiva para ser usado como requisito de contratação:
            
            Trecho original: "{clean_content}"
            
            Instruções:
            - Mantenha o significado e especificações técnicas originais
            - Use linguagem clara e direta
            - Formate como requisito específico em uma única linha
            - NÃO inclua justificativas ou explicações
            - Não invente informações que não estão no trecho
            - Retorne APENAS a descrição do requisito, sem prefixos (R#) ou qualquer outro texto
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": rewrite_prompt}],
                max_tokens=200,
                temperature=0.1
            )
            
            reformulated = response.choices[0].message.content.strip()
            # Remove any potential justification that might have been added
            if '(' in reformulated and 'Justificativa' in reformulated:
                reformulated = reformulated.split('(')[0].strip()
            
            return reformulated if reformulated else clean_content
            
        except Exception as e:
            logger.warning(f"Erro ao reformular conteúdo RAG: {e}")
            return clean_content
    
    def _generate_contextual_suggestions(self, contracting_need: str, contract_type: str) -> tuple:
        """Gera sugestões contextualizadas quando RAG não retorna resultados"""
        try:
            # Prompt consultivo contextualizado seguindo o formato R# — descrição
            consultive_prompt = f"""
            Como consultor especializado em contratações públicas, analise a seguinte necessidade e sugira requisitos específicos:
            
            Necessidade: "{contracting_need}"
            Tipo: {contract_type}
            
            FORMATO OBRIGATÓRIO:
            Retorne APENAS uma lista de requisitos no formato:
            R1 — <descrição do requisito em uma única linha>
            R2 — <descrição do requisito em uma única linha>
            R3 — <descrição do requisito em uma única linha>
            
            REGRAS ESTRITAS:
            - Sugira 4-6 requisitos específicos e pertinentes ao objeto descrito
            - Evite requisitos genéricos que se aplicam a qualquer contratação
            - NÃO inclua justificativas, explicações ou qualquer texto adicional
            - Cada linha deve começar com R seguido de número, espaço, travessão — e espaço
            - Cada requisito em uma única linha
            - Sem bullets, asteriscos, numeração dupla ou tabelas
            - Varie as sugestões conforme o contexto específico
            - Não use sempre os mesmos padrões (anos de experiência, ISO, etc.)
            
            Retorne SOMENTE as linhas no formato R# — descrição, nada mais.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": consultive_prompt}],
                max_tokens=800,
                temperature=0.4  # Mais criatividade para evitar respostas padronizadas
            )
            
            result_raw = response.choices[0].message.content.strip()
            
            # Parse requirements in R# — format
            requirements = []
            for line in result_raw.split('\n'):
                line = line.strip()
                if line and (line.startswith('R') or line[0].isdigit()):
                    requirements.append(line)
            
            # Fallback se parsing falhar
            if not requirements:
                logger.warning(f"[RAG] Não foi possível parsear requisitos no formato correto")
                requirements = [
                    f"R1 — Requisitos técnicos específicos para {contracting_need.lower()}",
                    "R2 — Especificações técnicas adequadas ao objeto da contratação",
                    "R3 — Comprovação de capacidade técnica e operacional",
                    "R4 — Garantias adequadas à natureza e valor da contratação"
                ]
            
            consultative_message = "Como não encontrei informações específicas na base de conhecimento, seguem sugestões contextualizadas baseadas nas melhores práticas:"
                
            return requirements, consultative_message
            
        except Exception as e:
            logger.error(f"Erro ao gerar sugestões consultivas: {e}")
            # Fallback ultra-simples no formato correto
            return [
                f"R1 — Requisitos técnicos específicos para {contracting_need.lower()}",
                "R2 — Comprovação de capacidade técnica adequada ao objeto",
                "R3 — Garantia compatível com a natureza do objeto",
                "R4 — Prazo de entrega/execução adequado às necessidades"
            ], "Não foi possível consultar a base de conhecimento. Seguem sugestões básicas que devem ser ajustadas conforme suas necessidades específicas:"