import os
import re
import json
from typing import Dict, List, Tuple, Optional, Any
import openai

class AdvancedDocumentAnalyzer:
    """Analisador avançado de documentos para extração de informações de ETP"""
    
    def __init__(self, openai_api_key: str):
        # Configurar cliente OpenAI de forma robusta
        try:
            # Tentar inicialização moderna
            self.client = openai.OpenAI(api_key=openai_api_key)
        except Exception as e:
            try:
                # Fallback para configuração legacy
                openai.api_key = openai_api_key
                self.client = None  # Usar API legacy
            except Exception as e2:
                raise Exception(f"Erro ao configurar OpenAI: {e}. Fallback: {e2}")
        
        # Padrões de regex para identificar seções específicas
        self.section_patterns = {
            'necessidade': [
                r'necessidade\s+da?\s+contrata[çc][ãa]o',
                r'justificativa\s+da?\s+contrata[çc][ãa]o',
                r'objeto\s+da?\s+contrata[çc][ãa]o',
                r'descri[çc][ãa]o\s+da?\s+necessidade'
            ],
            'pca': [
                r'plano\s+de\s+contrata[çc][õo]es?\s+anual',
                r'pca',
                r'previs[ãa]o\s+no\s+plano',
                r'demonstrativo\s+de\s+previs[ãa]o'
            ],
            'normas': [
                r'normas?\s+legais?',
                r'legisla[çc][ãa]o\s+aplic[áa]vel',
                r'base\s+legal',
                r'fundamento\s+legal',
                r'lei\s+\d+\.\d+',
                r'decreto\s+\d+'
            ],
            'valores': [
                r'valor\s+estimado',
                r'or[çc]amento',
                r'quantitativo',
                r'custo\s+estimado',
                r'r\$\s*[\d\.,]+',
                r'reais?'
            ],
            'parcelamento': [
                r'parcelamento',
                r'divis[ãa]o\s+da?\s+contrata[çc][ãa]o',
                r'lotes?',
                r'etapas?'
            ]
        }
        
        # Mapeamento das perguntas do ETP
        self.etp_questions = {
            1: {
                'question': 'Qual a descrição da necessidade da contratação?',
                'keywords': ['necessidade', 'justificativa', 'objeto', 'finalidade'],
                'sections': ['necessidade']
            },
            2: {
                'question': 'Possui demonstrativo de previsão no PCA?',
                'keywords': ['pca', 'plano', 'previsão', 'anual'],
                'sections': ['pca']
            },
            3: {
                'question': 'Quais normas legais pretende utilizar?',
                'keywords': ['normas', 'lei', 'decreto', 'legal', 'legislação'],
                'sections': ['normas']
            },
            4: {
                'question': 'Qual o quantitativo e valor estimado?',
                'keywords': ['valor', 'quantitativo', 'orçamento', 'custo', 'estimado'],
                'sections': ['valores']
            },
            5: {
                'question': 'Haverá parcelamento da contratação?',
                'keywords': ['parcelamento', 'lotes', 'divisão', 'etapas'],
                'sections': ['parcelamento']
            }
        }
    
    def extract_text_from_file(self, file_content: bytes, file_extension: str) -> str:
        """Extrai texto de diferentes tipos de arquivo (somente texto simples)"""
        try:
            # Com o modelo fine-tunado, não precisamos mais processar arquivos
            # Esta funcionalidade foi mantida para compatibilidade mas retorna erro
            raise ValueError("Processamento de arquivos desabilitado. Use apenas instruções de texto com o modelo fine-tunado.")
        except Exception as e:
            raise Exception(f"Erro ao extrair texto do arquivo: {str(e)}")
    
    def _extract_from_pdf(self, file_content: bytes) -> str:
        """Extrai texto de arquivo PDF"""
        pdf_file = io.BytesIO(file_content)
        pdf_reader = PdfReader(pdf_file)
        text = ""
        
        for page_num, page in enumerate(pdf_reader.pages):
            try:
                page_text = page.extract_text()
                if page_text:
                    text += f"\n--- Página {page_num + 1} ---\n"
                    text += page_text + "\n"
            except Exception as e:
                text += f"\n--- Erro na página {page_num + 1}: {str(e)} ---\n"
        
        return text
    
    def _extract_from_docx(self, file_content: bytes) -> str:
        """Extrai texto de arquivo DOCX"""
        doc_file = io.BytesIO(file_content)
        doc = Document(doc_file)
        text = ""
        
        # Extrair texto dos parágrafos
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text += paragraph.text + "\n"
        
        # Extrair texto das tabelas
        for table in doc.tables:
            text += "\n--- Tabela ---\n"
            for row in table.rows:
                row_text = []
                for cell in row.cells:
                    if cell.text.strip():
                        row_text.append(cell.text.strip())
                if row_text:
                    text += " | ".join(row_text) + "\n"
        
        return text
    
    def analyze_document(self, document_text: str) -> Dict:
        """Analisa documento completo e extrai informações relevantes"""
        try:
            # Pré-processamento do texto
            processed_text = self._preprocess_text(document_text)
            
            # Identificar seções relevantes
            sections = self._identify_sections(processed_text)
            
            # Extrair respostas usando análise de padrões
            pattern_answers = self._extract_answers_by_patterns(processed_text, sections)
            
            # Extrair respostas usando IA
            ai_answers = self._extract_answers_with_ai(processed_text)
            
            # Combinar resultados
            combined_answers = self._combine_extraction_results(pattern_answers, ai_answers)
            
            # Identificar informações faltantes
            missing_info = self._identify_missing_information(combined_answers)
            
            # Calcular confiança
            confidence_scores = self._calculate_confidence_scores(combined_answers, sections)
            
            return {
                'extracted_answers': combined_answers,
                'missing_info': missing_info,
                'confidence': confidence_scores,
                'sections_found': sections,
                'analysis_method': 'advanced_hybrid',
                'document_length': len(document_text),
                'processed_length': len(processed_text)
            }
            
        except Exception as e:
            return {
                'extracted_answers': {},
                'missing_info': list(range(1, 6)),
                'confidence': {},
                'error': str(e),
                'analysis_method': 'error'
            }
    
    def _preprocess_text(self, text: str) -> str:
        """Pré-processa o texto para melhor análise"""
        # Normalizar espaços e quebras de linha
        text = re.sub(r'\s+', ' ', text)
        
        # Remover caracteres especiais desnecessários
        text = re.sub(r'[^\w\s\.,;:!?\-\(\)\[\]\/\$\%\+\=]', ' ', text)
        
        # Normalizar acentos para busca
        text = text.lower()
        
        return text
    
    def _identify_sections(self, text: str) -> Dict[str, List[str]]:
        """Identifica seções relevantes no documento"""
        sections = {}
        
        for section_name, patterns in self.section_patterns.items():
            sections[section_name] = []
            
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    # Extrair contexto ao redor da correspondência
                    start = max(0, match.start() - 200)
                    end = min(len(text), match.end() + 500)
                    context = text[start:end]
                    sections[section_name].append(context)
        
        return sections
    
    def _extract_answers_by_patterns(self, text: str, sections: Dict) -> Dict[int, str]:
        """Extrai respostas usando análise de padrões"""
        answers = {}
        
        for question_id, question_info in self.etp_questions.items():
            relevant_sections = []
            
            # Coletar seções relevantes para esta pergunta
            for section_name in question_info['sections']:
                if section_name in sections:
                    relevant_sections.extend(sections[section_name])
            
            # Buscar por palavras-chave no texto completo
            for keyword in question_info['keywords']:
                pattern = rf'.{{0,100}}{keyword}.{{0,300}}'
                matches = re.findall(pattern, text, re.IGNORECASE)
                relevant_sections.extend(matches)
            
            # Processar seções relevantes
            if relevant_sections:
                # Combinar e limpar texto
                combined_text = ' '.join(relevant_sections)
                combined_text = re.sub(r'\s+', ' ', combined_text).strip()
                
                # Limitar tamanho
                if len(combined_text) > 500:
                    combined_text = combined_text[:500] + "..."
                
                if combined_text:
                    answers[question_id] = combined_text
        
        return answers
    
    def _extract_answers_with_ai(self, text: str) -> Dict[int, str]:
        """Extrai respostas usando IA"""
        try:
            # Limitar texto para não exceder tokens
            if len(text) > 8000:
                text = text[:8000] + "..."
            
            prompt = f"""
            Analise o documento fornecido e extraia informações específicas para responder às seguintes perguntas de um Estudo Técnico Preliminar (ETP):

            1. Qual a descrição da necessidade da contratação?
            2. Possui demonstrativo de previsão no PCA?
            3. Quais normas legais pretende utilizar?
            4. Qual o quantitativo e valor estimado?
            5. Haverá parcelamento da contratação?

            DOCUMENTO:
            {text}

            INSTRUÇÕES:
            - Para cada pergunta, extraia a informação mais relevante encontrada no documento
            - Se não encontrar informação para uma pergunta, não inclua no resultado
            - Seja preciso e cite trechos específicos quando possível
            - Mantenha as respostas concisas mas informativas

            Retorne um JSON no formato:
            {{
                "1": "resposta para pergunta 1",
                "2": "resposta para pergunta 2",
                ...
            }}
            """
            
            # Fazer chamada à API de forma compatível
            try:
                if self.client:
                    # Usar cliente moderno
                    response = self.client.chat.completions.create(
                        model="gpt-4-turbo",  # Modelo mais poderoso para análise de documentos
                        messages=[
                            {
                                "role": "system",
                                "content": "Você é um especialista em análise de documentos de licitação e ETP. Extraia informações específicas de forma precisa e estruturada."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        max_tokens=1500,
                        temperature=0.1
                    )
                else:
                    # Usar API legacy
                    response = openai.ChatCompletion.create(
                        model="gpt-4-turbo",
                        messages=[
                            {
                                "role": "system",
                                "content": "Você é um especialista em análise de documentos de licitação e ETP. Extraia informações específicas de forma precisa e estruturada."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        max_tokens=1500,
                        temperature=0.1
                    )
            except Exception as e:
                return {}
            
            # Tentar parsear resposta como JSON
            try:
                result = json.loads(response.choices[0].message.content)
                # Converter chaves para int
                return {int(k): v for k, v in result.items() if k.isdigit()}
            except json.JSONDecodeError:
                # Se não conseguir parsear, tentar extrair informações da resposta
                return self._parse_ai_response_fallback(response.choices[0].message.content)
                
        except Exception as e:
            return {}
    
    def _parse_ai_response_fallback(self, response_text: str) -> Dict[int, str]:
        """Fallback para parsear resposta da IA quando JSON falha"""
        answers = {}
        
        # Tentar encontrar padrões como "1:" ou "1."
        for i in range(1, 6):
            patterns = [
                rf'{i}[:\.]?\s*(.+?)(?={i+1}[:\.]|\n\n|\Z)',
                rf'pergunta\s+{i}[:\.]?\s*(.+?)(?=pergunta\s+{i+1}|\n\n|\Z)',
                rf'resposta\s+{i}[:\.]?\s*(.+?)(?=resposta\s+{i+1}|\n\n|\Z)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, response_text, re.IGNORECASE | re.DOTALL)
                if match:
                    answer = match.group(1).strip()
                    if answer and len(answer) > 10:  # Filtrar respostas muito curtas
                        answers[i] = answer
                        break
        
        return answers
    
    def _combine_extraction_results(self, pattern_answers: Dict, ai_answers: Dict) -> Dict[int, str]:
        """Combina resultados da análise de padrões e IA"""
        combined = {}
        
        for question_id in range(1, 6):
            pattern_answer = pattern_answers.get(question_id, '')
            ai_answer = ai_answers.get(question_id, '')
            
            # Priorizar resposta da IA se for mais completa
            if ai_answer and len(ai_answer) > len(pattern_answer):
                combined[question_id] = ai_answer
            elif pattern_answer:
                combined[question_id] = pattern_answer
            elif ai_answer:
                combined[question_id] = ai_answer
        
        return combined
    
    def _identify_missing_information(self, answers: Dict[int, str]) -> List[int]:
        """Identifica quais informações não foram encontradas"""
        missing = []
        
        for question_id in range(1, 6):
            if question_id not in answers or not answers[question_id].strip():
                missing.append(question_id)
        
        return missing
    
    def _calculate_confidence_scores(self, answers: Dict, sections: Dict) -> Dict[int, float]:
        """Calcula scores de confiança para cada resposta"""
        confidence = {}
        
        for question_id, answer in answers.items():
            score = 0.0
            
            # Pontuação base por ter resposta
            if answer and answer.strip():
                score += 0.3
            
            # Pontuação por tamanho da resposta
            if len(answer) > 50:
                score += 0.2
            elif len(answer) > 20:
                score += 0.1
            
            # Pontuação por palavras-chave relevantes
            question_info = self.etp_questions.get(question_id, {})
            keywords = question_info.get('keywords', [])
            
            for keyword in keywords:
                if keyword.lower() in answer.lower():
                    score += 0.1
            
            # Pontuação por seções encontradas
            relevant_sections = question_info.get('sections', [])
            for section_name in relevant_sections:
                if section_name in sections and sections[section_name]:
                    score += 0.1
            
            # Limitar score entre 0 e 1
            confidence[question_id] = min(1.0, score)
        
        return confidence
    
    def generate_feedback_message(self, analysis_result: Dict) -> str:
        """Gera mensagem de feedback para o usuário"""
        extracted_answers = analysis_result.get('extracted_answers', {})
        missing_info = analysis_result.get('missing_info', [])
        confidence = analysis_result.get('confidence', {})
        
        if not extracted_answers:
            return "Não foi possível extrair informações relevantes do documento. Você precisará responder todas as perguntas manualmente."
        
        feedback = "Análise do documento concluída!\n\n"
        
        # Informações encontradas
        if extracted_answers:
            feedback += "✅ Informações encontradas:\n"
            for question_id, answer in extracted_answers.items():
                question = self.etp_questions[question_id]['question']
                conf_score = confidence.get(question_id, 0)
                conf_text = "Alta" if conf_score > 0.7 else "Média" if conf_score > 0.4 else "Baixa"
                
                feedback += f"• Pergunta {question_id}: {question}\n"
                feedback += f"  Confiança: {conf_text}\n"
                feedback += f"  Resposta: {answer[:100]}{'...' if len(answer) > 100 else ''}\n\n"
        
        # Informações faltantes
        if missing_info:
            feedback += "❌ Informações não localizadas:\n"
            for question_id in missing_info:
                question = self.etp_questions[question_id]['question']
                feedback += f"• Pergunta {question_id}: {question}\n"
            
            feedback += "\nVocê precisará fornecer essas informações manualmente.\n"
        
        return feedback


    def extract_etp_answers(self, analysis_result: Dict[str, Any]) -> Dict[str, str]:
        """Extrai respostas específicas para as perguntas do ETP"""
        try:
            if not analysis_result or not analysis_result.get('success'):
                return {}
            
            content = analysis_result.get('content', '')
            if not content:
                return {}
            
            # Prompt para extrair respostas específicas das 5 perguntas ETP
            prompt = f"""
            Analise o seguinte documento e extraia respostas específicas para as 5 perguntas obrigatórias do ETP conforme Lei 14.133/21:

            DOCUMENTO:
            {content[:3000]}

            PERGUNTAS:
            1. Qual a descrição da necessidade da contratação?
            2. Possui demonstrativo de previsão no PCA? (responda apenas "sim" ou "não")
            3. Quais normas legais pretende utilizar?
            4. Qual o quantitativo e valor estimado?
            5. Haverá parcelamento da contratação? (responda apenas "sim" ou "não")

            Retorne APENAS um JSON válido no formato:
            {{
                "1": "resposta detalhada para pergunta 1",
                "2": "sim" ou "não",
                "3": "resposta detalhada para pergunta 3",
                "4": "resposta detalhada para pergunta 4",
                "5": "sim" ou "não"
            }}

            Se não encontrar informação para alguma pergunta, use "Informação não encontrada no documento".
            """
            
            # Fazer chamada à API
            try:
                if self.client:
                    response = self.client.chat.completions.create(
                        model="gpt-4-turbo",
                        messages=[
                            {
                                "role": "system",
                                "content": "Você é um especialista em análise de documentos de licitação. Extraia informações precisas e retorne apenas JSON válido."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        max_tokens=1000,
                        temperature=0.1
                    )
                else:
                    response = openai.ChatCompletion.create(
                        model="gpt-4-turbo",
                        messages=[
                            {
                                "role": "system",
                                "content": "Você é um especialista em análise de documentos de licitação. Extraia informações precisas e retorne apenas JSON válido."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        max_tokens=1000,
                        temperature=0.1
                    )
                
                # Extrair resposta
                response_text = response.choices[0].message.content.strip()
                
                # Tentar parsear como JSON
                try:
                    # Limpar resposta se necessário
                    if response_text.startswith('```json'):
                        response_text = response_text.replace('```json', '').replace('```', '').strip()
                    
                    answers = json.loads(response_text)
                    
                    # Validar que temos as 5 respostas
                    expected_keys = ['1', '2', '3', '4', '5']
                    for key in expected_keys:
                        if key not in answers:
                            answers[key] = "Informação não encontrada no documento"
                    
                    return answers
                    
                except json.JSONDecodeError:
                    # Se não conseguir parsear, retornar vazio
                    return {}
                    
            except Exception as e:
                print(f"Erro na API OpenAI: {e}")
                return {}
                
        except Exception as e:
            print(f"Erro geral em extract_etp_answers: {e}")
            return {}

