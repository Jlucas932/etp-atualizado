import os
import json
import re
from typing import Dict, List, Optional, Any, Tuple
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
    
    def generate_requirements_with_rag(
        self,
        contracting_need: str,
        contract_type: str,
        objective_slug: str = "generic",
        *,
        top_k: int = 12,
        similarity_threshold: float = 0.78,
    ) -> Dict[str, Any]:
        """Garante estratégia *RAG-first* para geração de requisitos."""

        normalized_need = (contracting_need or "").strip()
        rag_error_notice: Optional[str] = None
        rag_requirements: List[str] = []

        if self.rag_retrieval and normalized_need:
            try:
                rag_results = self.rag_retrieval.search_requirements(
                    objective_slug or "generic",
                    normalized_need,
                    k=top_k,
                )

                for result in rag_results:
                    score = result.get("hybrid_score") or result.get("score") or 0.0
                    if similarity_threshold and score < similarity_threshold:
                        continue

                    content = result.get("content", "")
                    cleaned = self._clean_and_format_rag_content(content)
                    if cleaned:
                        rag_requirements.append(cleaned)

                rag_requirements = self._deduplicate_requirements(rag_requirements)
                if rag_requirements:
                    logger.info(
                        "[RAG] %s requisito(s) reutilizados da base de conhecimento.",
                        len(rag_requirements),
                    )
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Erro ao consultar base RAG", exc_info=exc)
                rag_error_notice = "Não consegui recuperar um anexo agora. Vou continuar com as informações já coletadas."

        if rag_requirements:
            requirements = self._build_requirement_dicts(rag_requirements)
            return {
                "requirements": requirements,
                "formatted": [f"{req['id']} — {req['text']}" for req in requirements],
                "source": "rag",
                "error_notice": rag_error_notice,
            }

        generated_lines, raw_text = self._generate_requirements_with_llm(
            normalized_need,
            contract_type or "serviço",
        )
        requirements = self._build_requirement_dicts(generated_lines)
        return {
            "requirements": requirements,
            "formatted": [f"{req['id']} — {req['text']}" for req in requirements],
            "source": "llm",
            "error_notice": rag_error_notice,
            "raw_output": raw_text,
        }
    
    def _generate_requirements_with_llm(self, contracting_need: str, contract_type: str) -> Tuple[List[str], str]:
        """Gera requisitos via LLM já no formato obrigatório."""

        instruction = (
            "Você é um consultor público especializado em ETP. \n"
            "Considere a necessidade: \"{need}\". \n"
            "Tipo de contratação: {ctype}. \n"
            "Liste de 5 a 8 requisitos objetivos e testáveis.\n"
            "Formato obrigatório (uma linha por requisito):\n"
            "R1 — <requisito>\nR2 — <requisito>\n...\n"
            "Não inclua justificativas, notas, títulos ou rodapés."
        ).format(need=contracting_need or "necessidade informada", ctype=contract_type)

        if not self.client:
            fallback = self._fallback_requirements(contracting_need)
            return fallback, ""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Você apoia servidores públicos na redação de requisitos objetivos para ETP.",
                },
                {"role": "user", "content": instruction},
            ],
            temperature=0.2,
            max_tokens=600,
        )

        raw_text = response.choices[0].message.content.strip()
        parsed = self._parse_requirement_lines(raw_text)

        if not parsed:
            parsed = self._fallback_requirements(contracting_need)

        return parsed, raw_text

    def _parse_requirement_lines(self, raw_text: str) -> List[str]:
        lines = []
        for raw_line in raw_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            match = re.match(r"^R(\d+)\s*[—-]\s*(.+)$", line)
            if match:
                lines.append(match.group(2).strip())
        return lines[:8]

    def _build_requirement_dicts(self, requirements: List[str]) -> List[Dict[str, str]]:
        sanitized = []
        for idx, text in enumerate(requirements, start=1):
            sanitized.append({"id": f"R{idx}", "text": text.strip()})
        return sanitized

    def _deduplicate_requirements(self, requirements: List[str]) -> List[str]:
        seen = set()
        unique = []
        for item in requirements:
            normalized = item.strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(normalized)
            if len(unique) >= 8:
                break
        return unique

    def _fallback_requirements(self, contracting_need: str) -> List[str]:
        base = contracting_need or "a solução proposta"
        return [
            f"Definir critérios funcionais mínimos para {base}.",
            f"Garantir métricas de desempenho mensuráveis para {base}.",
            f"Estabelecer controles de segurança e rastreabilidade para {base}.",
            f"Prever plano de capacitação dos usuários envolvidos em {base}.",
            f"Monitorar indicadores de qualidade e disponibilidade da solução de {base}.",
        ]

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