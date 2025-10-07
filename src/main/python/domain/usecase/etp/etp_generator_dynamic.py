import os
import json
import logging
from typing import Dict, List, Optional
import openai
from datetime import datetime
from .dynamic_prompt_generator import DynamicPromptGenerator
from rag.retrieval import search_requirements
from domain.usecase.utils.legal_norms import suggest_federal
from domain.usecase.etp.verify_federal import resolve_lexml, summarize_for_user

class DynamicEtpGenerator:
    """Gerador de ETP com prompts dinâmicos baseados em documentos existentes"""
    
    def __init__(self, openai_api_key: str):
        self.client = openai.OpenAI(api_key=openai_api_key)
        self.prompt_generator = DynamicPromptGenerator(openai_api_key)
        self.etp_template = self._load_etp_template()
        self.logger = logging.getLogger(__name__)
        
        # Estrutura obrigatória conforme Lei 14.133/21
        self.etp_structure = [
            {
                "section": "1. INTRODUÇÃO",
                "subsections": [],
                "description": "Apresentação geral do documento e contexto da contratação",
                "min_paragraphs": 8
            },
            {
                "section": "2. OBJETO DO ESTUDO E ESPECIFICAÇÕES GERAIS",
                "subsections": [
                    "2.1 Localização da execução do objeto contratual",
                    "2.2 Natureza e finalidade do objeto",
                    "2.3 Classificação quanto ao sigilo",
                    "2.4 Descrição da necessidade da contratação",
                    "2.5 Demonstração da previsão no plano de contratações anual"
                ],
                "description": "Definição detalhada do objeto e especificações",
                "min_paragraphs": 10
            },
            {
                "section": "3. DESCRIÇÃO DOS REQUISITOS DA CONTRATAÇÃO",
                "subsections": [
                    "3.1 Requisitos técnicos",
                    "3.2 Requisitos de sustentabilidade",
                    "3.3 Requisitos normativos e legais"
                ],
                "description": "Especificação de todos os requisitos aplicáveis",
                "min_paragraphs": 9
            },
            {
                "section": "4. ESTIMATIVA DAS QUANTIDADES E VALORES",
                "subsections": [],
                "description": "Quantificação e valoração dos itens da contratação",
                "min_paragraphs": 8,
                "requires_table": True
            },
            {
                "section": "5. LEVANTAMENTO DE MERCADO E JUSTIFICATIVA DA ESCOLHA DA SOLUÇÃO",
                "subsections": [
                    "5.1 Justificativa para a escolha da solução",
                    "5.2 Pesquisa de mercado"
                ],
                "description": "Análise de mercado e justificativa técnica",
                "min_paragraphs": 10
            },
            {
                "section": "6. ESTIMATIVA DO VALOR DA CONTRATAÇÃO",
                "subsections": [],
                "description": "Consolidação dos valores estimados",
                "min_paragraphs": 8,
                "requires_table": True
            },
            {
                "section": "7. DESCRIÇÃO DA SOLUÇÃO COMO UM TODO",
                "subsections": [],
                "description": "Visão integrada da solução proposta",
                "min_paragraphs": 10
            },
            {
                "section": "8. JUSTIFICATIVA PARA O PARCELAMENTO OU NÃO DA CONTRATAÇÃO",
                "subsections": [],
                "description": "Análise sobre divisão ou não da contratação",
                "min_paragraphs": 8
            },
            {
                "section": "9. DEMONSTRATIVO DOS RESULTADOS PRETENDIDOS",
                "subsections": [],
                "description": "Resultados esperados com a contratação",
                "min_paragraphs": 9
            },
            {
                "section": "10. PROVIDÊNCIAS ADOTADAS ANTERIORMENTE PELA ADMINISTRAÇÃO",
                "subsections": [],
                "description": "Histórico de ações relacionadas",
                "min_paragraphs": 8
            },
            {
                "section": "11. CONTRATAÇÕES CORRELATAS OU INTERDEPENDENTES",
                "subsections": [],
                "description": "Análise de contratos relacionados",
                "min_paragraphs": 8
            },
            {
                "section": "12. AVALIAÇÃO DOS IMPACTOS AMBIENTAIS",
                "subsections": [],
                "description": "Análise de impactos ambientais ou justificativa de não aplicabilidade",
                "min_paragraphs": 8
            },
            {
                "section": "13. ANÁLISE DE RISCOS",
                "subsections": [],
                "description": "Identificação e análise de riscos",
                "min_paragraphs": 9,
                "requires_table": True
            },
            {
                "section": "14. CONCLUSÃO E POSICIONAMENTO FINAL",
                "subsections": [],
                "description": "Posicionamento técnico conclusivo sobre a viabilidade",
                "min_paragraphs": 8
            }
        ]
    
    def _load_etp_template(self) -> Dict:
        """Carrega o template fixo do ETP do arquivo JSON"""
        try:
            # Caminho para o arquivo de template (relativo ao diretório do projeto)
            current_dir = os.path.dirname(__file__)
            # Navegar para src/main/resources a partir de src/main/python/domain/usecase/etp
            template_path = os.path.join(
                current_dir, 
                '..', '..', '..', '..', 'resources', 'etp_template.json'
            )
            template_path = os.path.abspath(template_path)
            
            # Carregar o template
            with open(template_path, 'r', encoding='utf-8') as f:
                template_data = json.load(f)
            
            return template_data['etp_template']
        except Exception as e:
            self.logger.error("Erro ao carregar template ETP: %s", e, exc_info=True)
            # Retorna estrutura básica em caso de erro
            return {str(i): {"titulo": f"Seção {i}", "conteudo": ""} for i in range(1, 15)}
    
    def generate_complete_etp(self, session_data: Dict, context_data: Dict = None, is_preview: bool = False) -> str:
        """Gera ETP completo usando o template fixo e prompts dinâmicos"""
        try:
            # Criar uma cópia do template para preenchimento
            etp_document = {}
            for section_id, section_data in self.etp_template.items():
                etp_document[section_id] = {
                    "titulo": section_data["titulo"],
                    "conteudo": ""  # Será preenchido dinamicamente
                }
            
            # Gerar conteúdo para cada seção usando prompts dinâmicos
            for section_id in range(1, 15):
                section_key = str(section_id)
                if section_key in etp_document:
                    # Encontrar a seção correspondente na estrutura antiga para compatibilidade
                    section_info = next(
                        (s for s in self.etp_structure if s["section"].startswith(f"{section_id}.")), 
                        None
                    )
                    
                    if section_info:
                        section_content = self._generate_section_dynamic(
                            section_info, 
                            session_data, 
                            context_data,
                            is_preview
                        )
                        # Extrair apenas o conteúdo, removendo o título se presente
                        if section_content.startswith(section_info["section"]):
                            section_content = section_content[len(section_info["section"]):].strip()
                        
                        etp_document[section_key]["conteudo"] = section_content
            
            # Formatar documento final
            formatted_sections = []
            for section_id in range(1, 15):
                section_key = str(section_id)
                if section_key in etp_document:
                    section = etp_document[section_key]
                    formatted_sections.append(f"{section_id}. {section['titulo']}\n\n{section['conteudo']}")
            
            full_etp = "\n\n".join(formatted_sections)
            
            # Adicionar cabeçalho se não for preview
            if not is_preview:
                header = self._generate_document_header()
                full_etp = header + "\n\n" + full_etp
            
            return full_etp
            
        except Exception as e:
            raise Exception(f"Erro na geração do ETP: {str(e)}")
    
    def _generate_section_dynamic(self, section_info: Dict, session_data: Dict, 
                                context_data: Dict = None, is_preview: bool = False) -> str:
        """Gera uma seção específica usando prompt dinâmico"""
        try:
            # Gerar prompt dinâmico baseado na base de conhecimento
            dynamic_prompt = self.prompt_generator.generate_dynamic_prompt(
                session_data, 
                section_info
            )
            
            # Integração do fluxo de consulta interna para seções específicas
            section_title = section_info.get('section', '').upper()
            
            # Para seção "REQUISITO" - buscar contexto interno
            if "REQUISITO" in section_title:
                objective_slug = self._extract_objective_slug(session_data)
                if objective_slug:
                    # Extrair pergunta do usuário das respostas da sessão
                    user_query = self._extract_user_query_for_requirements(session_data)
                    if user_query:
                        try:
                            # Buscar contexto recuperado
                            ctx = search_requirements(objective_slug, user_query, k=5)
                            if ctx:
                                self.logger.info("consulta interna encontrada")
                                # Montar contexto recuperado (máximo 1200 palavras)
                                context_text = self._build_context_text(ctx, max_words=1200)
                                dynamic_prompt += f"\n\nCONTEXTO RECUPERADO:\n{context_text}"
                        except Exception as e:
                            self.logger.warning(f"Erro na busca de requisitos: {str(e)}")
            
            # Para seção "NORMA LEGAL" - sugerir normas federais
            elif "NORMA" in section_title and "LEGAL" in section_title:
                objective_slug = self._extract_objective_slug(session_data)
                if objective_slug:
                    try:
                        # Sugerir normas federais
                        cands = suggest_federal(objective_slug, k=6)
                        if cands:
                            self.logger.info("consulta interna encontrada")
                            # Verificar normas via LexML e preparar cards
                            verified = [resolve_lexml(c) for c in cands]
                            cards = [summarize_for_user(v) for v in verified if v]
                            
                            # Adicionar cards ao contexto para apresentação ao usuário
                            if cards:
                                cards_text = self._build_legal_cards_text(cards)
                                dynamic_prompt += f"\n\nNORMAS LEGAIS SUGERIDAS (fonte: LexML):\n{cards_text}"
                    except Exception as e:
                        self.logger.warning(f"Erro na busca de normas legais: {str(e)}")
            
            # Adicionar informações específicas da seção
            if section_info.get('subsections'):
                dynamic_prompt += f"\n\nSUBSEÇÕES OBRIGATÓRIAS:\n"
                for subsection in section_info['subsections']:
                    dynamic_prompt += f"- {subsection}\n"
            
            if section_info.get('requires_table'):
                dynamic_prompt += "\n\nIMPORTANTE: Esta seção deve incluir uma tabela formatada quando apropriado."
            
            # Fazer chamada à API
            response = self.client.chat.completions.create(
                model="ft:gpt-4.1-mini-2025-04-14:az-tecnologia-ltda:etp-treino:CBXrnlhG",
                messages=[
                    {
                        "role": "system",
                        "content": """Você é um especialista em elaboração de Estudos Técnicos Preliminares conforme a Lei 14.133/21. 
                        Gere conteúdo técnico, detalhado, formal e em total conformidade com a legislação de licitações e contratos públicos.
                        
                        DIRETRIZES PARA CONTEÚDO EXTENSO E ESTILIZADO:
                        - Produza texto substancial com parágrafos bem desenvolvidos de 4-7 linhas cada
                        - Inclua análises técnicas aprofundadas com fundamentação jurídica específica
                        - Desenvolva argumentações completas com contextualização adequada
                        - Use linguagem técnica formal própria de documentos administrativos oficiais
                        - Apresente detalhamentos metodológicos e critérios técnicos específicos
                        - Incorpore aspectos legais, administrativos, técnicos e operacionais relevantes
                        - Estruture o conteúdo com progressão lógica e coerência argumentativa
                        
                        Use os exemplos fornecidos como referência, mas adapte ao contexto específico da contratação atual.
                        Mantenha sempre linguagem administrativa apropriada e estrutura técnica detalhada."""
                    },
                    {
                        "role": "user",
                        "content": dynamic_prompt
                    }
                ],
                max_tokens=4000,
                temperature=0.2
            )
            
            section_content = response.choices[0].message.content
            
            # Pós-processamento
            section_content = self._post_process_section_content(section_content, section_info)
            
            return section_content
            
        except Exception as e:
            # Fallback em caso de erro com mensagem amigável
            error_msg = "Erro ao gerar esta seção. Tente novamente ou verifique o modelo configurado."
            if "rate limit" in str(e).lower():
                error_msg = "Limite de requisições atingido. Aguarde alguns minutos e tente novamente."
            elif "api key" in str(e).lower():
                error_msg = "Problema com a chave da API. Verifique a configuração do modelo."
            elif "model" in str(e).lower():
                error_msg = "Modelo não encontrado. Verifique se o modelo fine-tuned está disponível."
            
            return f"{section_info['section']}\n\n[{error_msg}]\n\nEsta seção deve ser desenvolvida manualmente conforme a Lei 14.133/21."
    
    def _post_process_section_content(self, content: str, section_info: Dict) -> str:
        """Pós-processa o conteúdo da seção"""
        # Garantir que o título esteja em maiúsculas
        lines = content.split('\n')
        if lines and lines[0].strip():
            title = section_info['section']
            if not lines[0].strip().upper().startswith(title.split('.')[0]):
                lines[0] = title
        
        # Remover linhas vazias excessivas
        processed_lines = []
        empty_count = 0
        
        for line in lines:
            if line.strip():
                processed_lines.append(line)
                empty_count = 0
            else:
                empty_count += 1
                if empty_count <= 1:  # Permitir no máximo uma linha vazia consecutiva
                    processed_lines.append(line)
        
        return '\n'.join(processed_lines)
    
    def _extract_objective_slug(self, session_data: Dict) -> str:
        """Extrai o objective_slug da sessão de dados"""
        # Tentar extrair das respostas do usuário baseado no contexto da necessidade
        answers = session_data.get('answers', {})
        
        # Procurar por palavras-chave nas respostas para determinar o objetivo
        all_answers_text = ' '.join([str(v) for v in answers.values() if v]).lower()
        
        # Mapear palavras-chave para objective_slugs conhecidos
        keyword_mapping = {
            'computador': 'manutencao_computadores',
            'manutenção': 'manutencao_computadores', 
            'limpeza': 'servicos_limpeza',
            'software': 'software',
            'tecnologia': 'tecnologia',
            'sistema': 'software',
            'obra': 'obra',
            'construção': 'obra',
            'serviço': 'servico'
        }
        
        for keyword, slug in keyword_mapping.items():
            if keyword in all_answers_text:
                return slug
        
        # Fallback padrão
        return 'contratacao_geral'
    
    def _extract_user_query_for_requirements(self, session_data: Dict) -> str:
        """Extrai a pergunta do usuário relacionada a requisitos"""
        answers = session_data.get('answers', {})
        
        # Procurar por respostas relacionadas a requisitos (pergunta id 2)
        if '2' in answers:
            return str(answers['2'])
        
        # Fallback: usar resposta sobre necessidade (pergunta id 1)
        if '1' in answers:
            return str(answers['1'])
        
        return "requisitos da contratação"
    
    def _build_context_text(self, context_results: List[Dict], max_words: int = 1200) -> str:
        """Constrói texto de contexto limitado por número de palavras"""
        context_parts = []
        word_count = 0
        
        for result in context_results:
            content = result.get('content', '')
            section_title = result.get('section_title', '')
            
            # Adicionar título da seção se disponível
            if section_title:
                part = f"[{section_title}]: {content}"
            else:
                part = content
            
            # Contar palavras
            part_words = len(part.split())
            if word_count + part_words <= max_words:
                context_parts.append(part)
                word_count += part_words
            else:
                # Adicionar parte truncada para não exceder limite
                remaining_words = max_words - word_count
                if remaining_words > 10:  # Só adicionar se houver espaço suficiente
                    truncated = ' '.join(part.split()[:remaining_words])
                    context_parts.append(truncated + "...")
                break
        
        return '\n\n'.join(context_parts)
    
    def _build_legal_cards_text(self, cards: List[Dict]) -> str:
        """Constrói texto formatado dos cards de normas legais"""
        cards_parts = []
        
        for i, card in enumerate(cards, 1):
            card_text = f"CARD {i}:\n"
            card_text += f"Tipo: {card.get('tipo', 'N/A')}\n"
            card_text += f"Número: {card.get('numero', 'N/A')}\n"
            card_text += f"Ano: {card.get('ano', 'N/A')}\n"
            card_text += f"Descrição: {card.get('descricao', 'N/A')}\n"
            card_text += f"Fonte: LexML\n"
            
            # Adicionar informações adicionais se disponíveis
            if 'ementa' in card:
                card_text += f"Ementa: {card['ementa'][:200]}{'...' if len(card.get('ementa', '')) > 200 else ''}\n"
            
            if 'url_lexml' in card:
                card_text += f"URL LexML: {card['url_lexml']}\n"
            
            cards_parts.append(card_text)
        
        return '\n\n'.join(cards_parts)
    
    def _generate_document_header(self) -> str:
        """Gera cabeçalho do documento"""
        current_date = datetime.now().strftime("%d/%m/%Y")
        
        header = f"""GOVERNO DO ESTADO
SECRETARIA DE ADMINISTRAÇÃO
ESTUDO TÉCNICO PRELIMINAR (ETP)

Data: {current_date}

O presente documento caracteriza a primeira etapa da fase de planejamento e apresenta os devidos estudos para a contratação de solução que melhor atenderá à necessidade descrita abaixo.

O objetivo principal é identificar a necessidade e identificar a melhor solução para supri-la, em observância às normas vigentes e aos princípios que regem a Administração Pública, especialmente a Lei nº 14.133/2021."""
        
        return header
    
    def generate_section_adjustment(self, section_content: str, feedback: str, section_info: Dict) -> str:
        """Ajusta uma seção específica com base no feedback usando contexto dinâmico"""
        try:
            # Buscar exemplos relevantes para a seção
            session_data = {'answers': {}}  # Dados básicos para busca de exemplos
            relevant_examples = self.prompt_generator._find_relevant_examples(
                section_info['section'], 
                session_data
            )
            
            # Construir contexto para ajuste
            examples_context = ""
            if relevant_examples:
                examples_context = "EXEMPLOS DE REFERÊNCIA:\n"
                for example in relevant_examples[:2]:
                    examples_context += f"- {example['content'][:300]}...\n"
            
            prompt = f"""
            Ajuste a seguinte seção de ETP com base no feedback fornecido:

            SEÇÃO ATUAL:
            {section_content}

            FEEDBACK DO USUÁRIO:
            {feedback}

            {examples_context}

            INFORMAÇÕES DA SEÇÃO:
            - Título: {section_info['section']}
            - Descrição: {section_info['description']}
            - Parágrafos mínimos: {section_info.get('min_paragraphs', 8)}

            INSTRUÇÕES:
            1. Mantenha a estrutura e formatação original
            2. Aplique os ajustes solicitados no feedback
            3. Preserve a conformidade com a Lei 14.133/21
            4. Mantenha linguagem técnica e formal
            5. Use os exemplos como referência para estilo e conteúdo
            6. Garanta coerência com o restante do documento

            Retorne a seção ajustada:
            """
            
            response = self.client.chat.completions.create(
                model="ft:gpt-4.1-mini-2025-04-14:az-tecnologia-ltda:etp-treino:CBXrnlhG",
                messages=[
                    {
                        "role": "system",
                        "content": "Você é um especialista em revisão de documentos de ETP. Faça ajustes precisos mantendo qualidade técnica e conformidade legal."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=2000,
                temperature=0.2
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return section_content  # Retornar original em caso de erro
    
    def get_knowledge_base_info(self) -> Dict:
        """Retorna informações sobre a base de conhecimento carregada"""
        return self.prompt_generator.get_knowledge_base_summary()
    
    def refresh_knowledge_base(self):
        """Recarrega a base de conhecimento"""
        return self.prompt_generator.refresh_knowledge_base()
    
    def validate_etp_completeness(self, etp_content: str) -> Dict:
        """Valida se o ETP está completo conforme a estrutura obrigatória"""
        validation_result = {
            'is_complete': True,
            'missing_sections': [],
            'section_analysis': {},
            'total_sections': len(self.etp_structure),
            'found_sections': 0
        }
        
        for section_info in self.etp_structure:
            section_title = section_info['section']
            section_number = section_title.split('.')[0]
            
            # Verificar se a seção existe no conteúdo
            if section_number in etp_content:
                validation_result['found_sections'] += 1
                validation_result['section_analysis'][section_title] = {
                    'found': True,
                    'estimated_length': len(etp_content.split(section_number)[1].split('\n')[0]) if section_number in etp_content else 0
                }
            else:
                validation_result['is_complete'] = False
                validation_result['missing_sections'].append(section_title)
                validation_result['section_analysis'][section_title] = {
                    'found': False,
                    'estimated_length': 0
                }
        
        # Calcular completude percentual
        validation_result['completeness_percentage'] = (
            validation_result['found_sections'] / validation_result['total_sections']
        ) * 100
        
        return validation_result

