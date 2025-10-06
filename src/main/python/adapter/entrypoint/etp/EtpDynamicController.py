import os
import json
import uuid
import tempfile
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file
from flask_cors import cross_origin

from domain.interfaces.dataprovider.DatabaseConfig import db
from domain.dto.EtpDto import EtpSession, DocumentAnalysis, KnowledgeBase, ChatSession, EtpTemplate
from domain.usecase.etp.verify_federal import resolve_lexml, summarize_for_user, parse_legal_norm_string
from application.config.LimiterConfig import limiter
from rag.retrieval import search_requirements
from domain.services.etp_dynamic import init_etp_dynamic

etp_dynamic_bp = Blueprint('etp_dynamic', __name__)

# Module-level variables for lazy initialization
_etp_generator = None
_prompt_generator = None  
_rag_system = None
_initialized = False

def parse_update_command(user_message, current_requirements):
    """
    Parse user commands for requirement updates
    Returns dict with:
    - action: 'remove', 'edit', 'keep_only', 'add', 'unclear'
    - items: list of requirement IDs or content
    - message: explanation of what was done
    """
    import re
    
    message_lower = user_message.lower()
    
    # Check for explicit necessity restart keywords
    restart_keywords = [
        "nova necessidade", "trocar a necessidade", "na verdade a necessidade é",
        "mudou a necessidade", "preciso trocar a necessidade"
    ]
    
    for keyword in restart_keywords:
        if keyword in message_lower:
            return {
                'action': 'restart_necessity',
                'items': [],
                'message': 'Detectada solicitação para reiniciar necessidade'
            }
    
    # Extract requirement numbers (R1, R2, etc. or just numbers)
    req_numbers = []
    
    # Look for patterns like "R1", "R2", "requisito 1", "primeiro", "último", etc.
    r_patterns = re.findall(r'[rR](\d+)', user_message)
    req_numbers.extend([f"R{n}" for n in r_patterns])
    
    # Look for standalone numbers that might refer to requirements
    number_patterns = re.findall(r'\b(\d+)\b', user_message)
    for n in number_patterns:
        if int(n) <= len(current_requirements):
            req_id = f"R{n}"
            if req_id not in req_numbers:
                req_numbers.append(req_id)
    
    # Handle positional references
    if 'último' in message_lower or 'ultima' in message_lower:
        if current_requirements:
            req_numbers.append(current_requirements[-1].get('id', f"R{len(current_requirements)}"))
    
    if 'primeiro' in message_lower or 'primeira' in message_lower:
        if current_requirements:
            req_numbers.append(current_requirements[0].get('id', 'R1'))
    
    if 'penúltimo' in message_lower or 'penultima' in message_lower:
        if len(current_requirements) > 1:
            req_numbers.append(current_requirements[-2].get('id', f"R{len(current_requirements)-1}"))
    
    # Determine action type
    if any(word in message_lower for word in ['remover', 'tirar', 'excluir', 'deletar', 'retirar']):
        if req_numbers:
            return {
                'action': 'remove',
                'items': req_numbers,
                'message': f'Removidos requisitos: {", ".join(req_numbers)}'
            }
        else:
            return {'action': 'unclear', 'items': [], 'message': 'Não foi possível identificar quais requisitos remover'}
    
    if any(word in message_lower for word in ['manter apenas', 'só manter', 'manter só', 'manter somente']):
        if req_numbers:
            return {
                'action': 'keep_only',
                'items': req_numbers,
                'message': f'Mantidos apenas requisitos: {", ".join(req_numbers)}'
            }
        else:
            return {'action': 'unclear', 'items': [], 'message': 'Não foi possível identificar quais requisitos manter'}
    
    if any(word in message_lower for word in ['alterar', 'modificar', 'trocar', 'mudar', 'editar']):
        if req_numbers:
            return {
                'action': 'edit',
                'items': req_numbers,
                'message': f'Requisitos para edição: {", ".join(req_numbers)}'
            }
        else:
            return {'action': 'unclear', 'items': [], 'message': 'Não foi possível identificar quais requisitos alterar'}
    
    if any(word in message_lower for word in ['adicionar', 'incluir', 'acrescentar', 'novo requisito']):
        # Extract the content after the add command
        add_content = user_message
        for word in ['adicionar', 'incluir', 'acrescentar']:
            if word in message_lower:
                parts = user_message.lower().split(word, 1)
                if len(parts) > 1:
                    add_content = parts[1].strip()
                break
        
        return {
            'action': 'add',
            'items': [add_content],
            'message': f'Novo requisito adicionado: {add_content}'
        }
    
    # Check for confirmation words
    confirm_words = [
        'confirmar', 'confirmo', 'manter', 'ok', 'está bom', 'perfeito',
        'concordo', 'aceito', 'pode ser', 'sim'
    ]
    
    if any(word in message_lower for word in confirm_words):
        return {
            'action': 'confirm',
            'items': [],
            'message': 'Requisitos confirmados'
        }
    
    # If nothing clear was detected
    return {
        'action': 'unclear',
        'items': [],
        'message': 'Comando não reconhecido'
    }

def _get_etp_components():
    """Lazy initialization of ETP components to avoid circular imports"""
    global _etp_generator, _prompt_generator, _rag_system, _initialized
    
    if not _initialized:
        _etp_generator, _prompt_generator, _rag_system = init_etp_dynamic()
        _initialized = True
    
    return _etp_generator, _prompt_generator, _rag_system

# Initialize components for backward compatibility
def _ensure_initialized():
    """Ensure components are initialized"""
    global etp_generator, prompt_generator, rag_system
    etp_generator, prompt_generator, rag_system = _get_etp_components()

# Configure logging
logger = logging.getLogger(__name__)

# Perguntas do ETP conforme especificado
ETP_QUESTIONS = [
    {
        "id": 1,
        "question": "Qual a descrição da necessidade da contratação?",
        "type": "text",
        "required": True,
        "section": "OBJETO DO ESTUDO E ESPECIFICAÇÕES GERAIS"
    },
    {
        "id": 2,
        "question": "Você gostaria de manter esses requisitos, ajustar algum deles ou incluir outros?",
        "type": "text",
        "required": True,
        "section": "DESCRIÇÃO DOS REQUISITOS DA CONTRATAÇÃO"
    },
    {
        "id": 3,
        "question": "Possui demonstrativo de previsão no PCA?",
        "type": "boolean",
        "required": True,
        "section": "OBJETO DO ESTUDO E ESPECIFICAÇÕES GERAIS"
    },
    {
        "id": 4,
        "question": "Quais normas legais pretende utilizar?",
        "type": "text",
        "required": True,
        "section": "DESCRIÇÃO DOS REQUISITOS DA CONTRATAÇÃO"
    },
    {
        "id": 5,
        "question": "Qual o quantitativo e valor estimado?",
        "type": "text",
        "required": True,
        "section": "ESTIMATIVA DAS QUANTIDADES E VALORES"
    },
    {
        "id": 6,
        "question": "Haverá parcelamento da contratação?",
        "type": "boolean",
        "required": True,
        "section": "JUSTIFICATIVA PARA O PARCELAMENTO"
    }
]

@etp_dynamic_bp.route('/health', methods=['GET'])
@cross_origin()
def health_check():
    """Verificação de saúde da API dinâmica"""
    try:
        _ensure_initialized()
        # Verificar se os geradores estão funcionando
        kb_info = etp_generator.get_knowledge_base_info() if etp_generator else {}

        return jsonify({
            'status': 'healthy',
            'version': '3.0.0-dynamic',
            'openai_configured': bool(os.getenv('OPENAI_API_KEY')),
            'etp_generator_ready': etp_generator is not None,
            'knowledge_base': {
                'documents_loaded': kb_info.get('total_documents', 0),
                'common_sections': len(kb_info.get('common_sections', []))
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@etp_dynamic_bp.route('/knowledge-base/info', methods=['GET'])
@cross_origin()
def get_knowledge_base_info():
    """Retorna informações sobre a base de conhecimento"""
    try:
        _ensure_initialized()
        if not etp_generator:
            return jsonify({'error': 'Gerador ETP não configurado'}), 500

        kb_info = etp_generator.get_knowledge_base_info()
        return jsonify({
            'success': True,
            'knowledge_base': kb_info,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@etp_dynamic_bp.route('/knowledge-base/refresh', methods=['POST'])
@cross_origin()
def refresh_knowledge_base():
    """Recarrega a base de conhecimento"""
    try:
        _ensure_initialized()
        if not etp_generator:
            return jsonify({'error': 'Gerador ETP não configurado'}), 500

        kb_info = etp_generator.refresh_knowledge_base()
        return jsonify({
            'success': True,
            'message': 'Base de conhecimento recarregada com sucesso',
            'knowledge_base': kb_info,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@etp_dynamic_bp.route('/questions', methods=['GET'])
@cross_origin()
def get_questions():
    """Retorna as perguntas do ETP"""
    _ensure_initialized()
    return jsonify({
        'success': True,
        'questions': ETP_QUESTIONS,
        'total': len(ETP_QUESTIONS)
    })

@etp_dynamic_bp.route('/session/start', methods=['POST'])
@cross_origin()
def start_session():
    """Inicia uma nova sessão de ETP"""
    try:
        _ensure_initialized()
        data = request.get_json()
        user_id = data.get('user_id', 1)  # Default user_id se não fornecido

        # Criar nova sessão
        session = EtpSession(
            user_id=user_id,
            session_id=str(uuid.uuid4()),
            status='active',
            answers=json.dumps({}),
            created_at=datetime.utcnow()
        )

        db.session.add(session)
        db.session.commit()

        return jsonify({
            'success': True,
            'session_id': session.session_id,
            'questions': ETP_QUESTIONS,
            'message': 'Sessão iniciada com sucesso'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@etp_dynamic_bp.route('/session/<session_id>/answer', methods=['POST'])
@cross_origin()
def save_answer(session_id):
    """Salva resposta de uma pergunta"""
    try:
        _ensure_initialized()
        data = request.get_json()
        question_id = data.get('question_id')
        answer = data.get('answer')

        if not question_id or answer is None:
            return jsonify({'error': 'question_id e answer são obrigatórios'}), 400

        # Buscar sessão
        session = EtpSession.query.filter_by(session_id=session_id).first()
        if not session:
            return jsonify({'error': 'Sessão não encontrada'}), 404

        # Atualizar resposta
        answers = session.get_answers()
        answers[str(question_id)] = answer
        session.set_answers(answers)
        session.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Resposta salva com sucesso',
            'answers_count': len(answers)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@etp_dynamic_bp.route('/session/<session_id>/generate', methods=['POST'])
@limiter.limit("10 per minute")
@cross_origin()
def generate_etp(session_id):
    """Gera ETP completo usando prompts dinâmicos"""
    try:
        _ensure_initialized()
        if not etp_generator:
            return jsonify({'error': 'Gerador ETP não configurado'}), 500

        # Buscar sessão
        session = EtpSession.query.filter_by(session_id=session_id).first()
        if not session:
            return jsonify({'error': 'Sessão não encontrada'}), 404

        # Verificar se há respostas suficientes
        answers = session.get_answers()
        if not answers or len(answers) < 3:
            return jsonify({'error': 'Respostas insuficientes. Mínimo 3 respostas necessárias.'}), 400

        # Preparar dados da sessão
        session_data = {
            'session_id': session_id,
            'answers': answers,
            'user_id': session.user_id
        }

        # Gerar ETP usando sistema dinâmico
        etp_content = etp_generator.generate_complete_etp(
            session_data=session_data,
            context_data=None,
            is_preview=False
        )

        # Salvar ETP gerado
        session.generated_etp = etp_content
        session.status = 'completed'
        session.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            'success': True,
            'etp_content': etp_content,
            'message': 'ETP gerado com sucesso usando sistema dinâmico',
            'generation_method': 'dynamic_prompts',
            'knowledge_base_used': True
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'generation_method': 'dynamic_prompts'
        }), 500

@etp_dynamic_bp.route('/session/<session_id>/preview', methods=['POST'])
@cross_origin()
def generate_preview(session_id):
    """Gera preview do ETP usando prompts dinâmicos"""
    try:
        _ensure_initialized()
        if not etp_generator:
            return jsonify({'error': 'Gerador ETP não configurado'}), 500

        # Buscar sessão
        session = EtpSession.query.filter_by(session_id=session_id).first()
        if not session:
            return jsonify({'error': 'Sessão não encontrada'}), 404

        # Preparar dados da sessão
        session_data = {
            'session_id': session_id,
            'answers': session.get_answers(),
            'user_id': session.user_id
        }

        # Gerar preview usando sistema dinâmico
        preview_content = etp_generator.generate_complete_etp(
            session_data=session_data,
            context_data=None,
            is_preview=True
        )

        return jsonify({
            'success': True,
            'preview_content': preview_content,
            'message': 'Preview gerado com sucesso usando sistema dinâmico',
            'generation_method': 'dynamic_prompts',
            'is_preview': True
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'generation_method': 'dynamic_prompts'
        }), 500

@etp_dynamic_bp.route('/session/<session_id>', methods=['GET'])
@cross_origin()
def get_session(session_id):
    """Retorna dados da sessão"""
    try:
        _ensure_initialized()
        session = EtpSession.query.filter_by(session_id=session_id).first()
        if not session:
            return jsonify({'error': 'Sessão não encontrada'}), 404

        return jsonify({
            'success': True,
            'session': session.to_dict()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@etp_dynamic_bp.route('/consultative-options', methods=['POST'])
@cross_origin()
def generate_consultative_options():
    """Gera opções consultivas baseadas nas respostas coletadas"""
    try:
        _ensure_initialized()
        if not etp_generator:
            return jsonify({'error': 'Gerador ETP não configurado'}), 500

        # PASSO 9: Reutilizar session_id
        data = request.get_json(force=True)
        sid = (data.get("session_id") or "").strip() or None
        session = EtpSession.query.filter_by(session_id=sid).first() if sid else None
        
        # PASSO 9: Base de resposta com session_id
        resp_base = {"success": True, "session_id": sid} if sid else {"success": True}
        
        extracted_answers = data.get('extracted_answers', {})

        if not extracted_answers or not extracted_answers.get('1'):
            return jsonify({'error': 'Informações insuficientes para gerar opções'}), 400

        # Prompt para gerar opções consultivas
        consultative_prompt = f"""
        Baseado na necessidade de contratação informada: "{extracted_answers.get('1', 'Não informado')}"

        Gere pelo menos 2 opções plausíveis de atendimento à necessidade, considerando:
        - Normas legais pretendidas: {extracted_answers.get('3', 'Não informado')}
        - Quantitativo/valor estimado: {extracted_answers.get('4', 'Não informado')}
        - Previsão no PCA: {extracted_answers.get('2', 'Não informado')}
        - Parcelamento: {extracted_answers.get('5', 'Não informado')}

        Para cada opção, forneça:
        1. Nome da opção
        2. Resumo narrado da solução
        3. Vantagens (prós)
        4. Desvantagens/pontos de atenção (contras)

        Use tom consultivo e natural, como um especialista oferecendo alternativas.

        Retorne no formato JSON:
        {{
            "options": [
                {{
                    "name": "Nome da Opção 1",
                    "summary": "Resumo da solução...",
                    "pros": ["Vantagem 1", "Vantagem 2"],
                    "cons": ["Desvantagem 1", "Ponto de atenção 1"]
                }}
            ],
            "consultative_message": "Mensagem introdutória sobre as opções..."
        }}
        """

        response = etp_generator.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": open('/home/ubuntu/autodoc-ia-projeto/prompts/system_consultor.txt').read()},
                {"role": "user", "content": consultative_prompt}
            ],
            max_tokens=1500,
            temperature=0.7
        )

        result = json.loads(response.choices[0].message.content.strip())

        return jsonify({
            **resp_base,
            'kind': 'consultative_options',
            'options': result.get('options', []),
            'consultative_message': result.get('consultative_message', ''),
            'message': result.get('consultative_message', ''),
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@etp_dynamic_bp.route('/option-conversation', methods=['POST'])
@cross_origin()
def handle_option_conversation():
    """Gerencia conversa sobre as opções apresentadas"""
    try:
        _ensure_initialized()
        if not etp_generator:
            return jsonify({'error': 'Gerador ETP não configurado'}), 500

        # PASSO 10: Reutilizar session_id
        data = request.get_json(force=True)
        sid = (data.get("session_id") or "").strip() or None
        session = EtpSession.query.filter_by(session_id=sid).first() if sid else None
        
        # PASSO 10: Base de resposta com session_id
        resp_base = {"success": True, "session_id": sid} if sid else {"success": True}
        
        user_message = data.get('message', '').strip()
        options = data.get('options', [])
        conversation_history = data.get('conversation_history', [])

        if not user_message:
            return jsonify({'error': 'Mensagem do usuário é obrigatória'}), 400

        # Analisar se o usuário fez uma escolha final
        choice_analysis_prompt = f"""
        Analise se o usuário fez uma escolha definitiva entre as opções apresentadas.

        Opções disponíveis: {[opt['name'] for opt in options]}
        Mensagem do usuário: "{user_message}"

        Retorne JSON:
        {{
            "made_choice": true/false,
            "chosen_option": "nome da opção escolhida" ou null,
            "needs_clarification": true/false,
            "response_type": "choice|question|clarification"
        }}
        """

        choice_response = etp_generator.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": choice_analysis_prompt}],
            max_tokens=200,
            temperature=0.3
        )

        choice_result = json.loads(choice_response.choices[0].message.content.strip())

        # Gerar resposta contextual
        context_prompt = f"""
        Você é um consultor especialista em contratações públicas conversando sobre opções de atendimento.

        Opções apresentadas: {json.dumps(options, indent=2)}
        Mensagem do usuário: "{user_message}"
        Análise da escolha: {json.dumps(choice_result)}

        Responda de forma natural e consultiva, ajudando o usuário a:
        - Esclarecer dúvidas sobre as opções
        - Tomar uma decisão informada
        - Entender implicações de cada escolha

        Se o usuário fez uma escolha, confirme e oriente próximos passos.
        Se ainda está decidindo, ajude com mais informações.
        """

        ai_response = etp_generator.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Você é um consultor especialista em contratações públicas."},
                {"role": "user", "content": context_prompt}
            ],
            max_tokens=800,
            temperature=0.7
        )

        ai_response_text = ai_response.choices[0].message.content.strip()
        
        return jsonify({
            **resp_base,
            'kind': 'option_conversation',
            'ai_response': ai_response_text,
            'message': ai_response_text,
            'choice_analysis': choice_result,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@etp_dynamic_bp.route('/conversation', methods=['POST'])
@cross_origin()
def etp_conversation():
    """Conduz conversa natural usando o modelo fine-tuned para coleta de informações do ETP"""
    try:
        _ensure_initialized()
        if not etp_generator:
            return jsonify({'error': 'Gerador ETP não configurado'}), 500

        data = request.get_json()
        print("🔹 Recebi do frontend:", data)

        user_message = data.get('message', '').strip()
        session_id = data.get('session_id')
        conversation_history = data.get('conversation_history', [])
        answered_questions = data.get('answered_questions', [])

        if not user_message:
            return jsonify({'error': 'Mensagem é obrigatória'}), 400

        # PASSO 2A: Reuse session if provided, create if needed
        sid = (session_id or "").strip() or None
        session = EtpSession.query.filter_by(session_id=sid).first() if sid else None
        
        if not session:
            # Create new session only if none exists
            session = EtpSession(
                user_id=1,
                session_id=str(uuid.uuid4()),
                status='active',
                answers=json.dumps({}),
                conversation_stage='collect_need',
                created_at=datetime.utcnow()
            )
            db.session.add(session)
            db.session.commit()

        # PASSO 2A: Base de resposta com session_id
        resp_base = {"success": True, "session_id": session.session_id}
        
        print(f"🔹 [ANTES] Sessão: {session.session_id}, estágio: {session.conversation_stage}, necessidade: {bool(session.necessity)}")
        print(f"🔹 [INPUT] Mensagem: '{user_message[:50]}{'...' if len(user_message) > 50 else '}'}")

        # PASSO 3: Interpretador de comandos ANTES do LLM
        if session.conversation_stage in ['suggest_requirements', 'review_requirements']:
            from domain.usecase.etp.requirements_interpreter import parse_update_command, aplicar_comando
            
            current_requirements = session.get_requirements()
            command_result = parse_update_command(user_message, current_requirements)
            
            print(f"🔹 Comando parseado: {command_result}")
            
            if command_result['intent'] == 'restart_necessity':
                # Reset session to collect new necessity
                session.necessity = None
                session.conversation_stage = 'collect_need'
                session.set_requirements([])
                session.updated_at = datetime.utcnow()
                db.session.commit()
                
                return jsonify({
                    **resp_base,
                    'kind': 'text',
                    'ai_response': 'Entendido! Vamos recomeçar. Qual é a nova necessidade da contratação?',
                    'message': 'Entendido! Vamos recomeçar. Qual é a nova necessidade da contratação?',
                    'conversation_stage': 'collect_need'
                })
            
            elif command_result['intent'] != 'unclear':
                # PASSO 3: Apply the command to requirements with stable renumbering
                aplicar_comando(command_result, session, session.necessity)
                session.conversation_stage = 'review_requirements'
                session.updated_at = datetime.utcnow()
                db.session.commit()
                
                # PASSO 6: Return with unified contract
                updated_requirements = session.get_requirements()
                return jsonify({
                    **resp_base,
                    'kind': 'requirements_update',
                    'necessity': session.necessity,
                    'requirements': updated_requirements,
                    'message': command_result['message']
                })
            
            # PASSO 3: If command unclear, ask for clarification
            return jsonify({
                **resp_base,
                'kind': 'text',
                'ai_response': 'Não entendi o comando. Você pode ser mais específico? Por exemplo: "remover o 2", "ajustar o último", "pode manter".',
                'message': 'Não entendi o comando. Você pode ser mais específico? Por exemplo: "remover o 2", "ajustar o último", "pode manter".'
            })

        # PASSO 5: If no session necessity exists, we need to capture it
        if not session.necessity:
            from domain.usecase.etp.utils_parser import analyze_need_safely
            
            # PASSO 5: Use safe analyzer - NO fallback suicida
            contains_need, need_description = analyze_need_safely(user_message, etp_generator.client)
            print(f"🔹 [ANALYZER] contains_need={contains_need}, description='{need_description or 'None'}'")

            if contains_need and need_description:
                print(f"🔹 [LOCK] Necessidade identificada e travada: {need_description}")
                
                # PASSO 2B: LOCK NECESSITY and advance stage
                session.necessity = need_description
                session.conversation_stage = 'suggest_requirements'
                session.updated_at = datetime.utcnow()
                db.session.commit()
                
                print(f"🔹 [DEPOIS] Sessão: {session.session_id}, estágio: {session.conversation_stage}")

                # Generate requirements using existing logic
                try:
                    # Use RAG to find similar requirements
                    rag_results = search_requirements("generic", need_description, k=15)
                    
                    # Generate structured requirements
                    requirements_prompt = f"""
                    Baseado na necessidade: "{need_description}"
                    
                    E nos seguintes exemplos de requisitos similares:
                    {json.dumps(rag_results, indent=2)}
                    
                    Gere uma lista de 3-5 requisitos específicos e objetivos para esta contratação.
                    
                    Retorne APENAS um JSON no formato:
                    {{
                        "requirements": [
                            {{"id": "R1", "text": "Descrição do requisito", "justification": "Justificativa"}},
                            {{"id": "R2", "text": "Descrição do requisito", "justification": "Justificativa"}}
                        ]
                    }}
                    """
                    
                    response = etp_generator.client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "Você é um especialista em licitações que gera requisitos técnicos precisos."},
                            {"role": "user", "content": requirements_prompt}
                        ],
                        max_tokens=1000,
                        temperature=0.7
                    )
                    
                    # PASSO 5: Parse response safely
                    from domain.usecase.etp.utils_parser import parse_requirements_response_safely
                    parsed_response = parse_requirements_response_safely(
                        response.choices[0].message.content.strip()
                    )
                    
                    # Extract requirements list from parsed response
                    structured_requirements = parsed_response.get('suggested_requirements', [])
                    
                    # Store requirements in session
                    session.set_requirements(structured_requirements)
                    session.updated_at = datetime.utcnow()
                    db.session.commit()
                    
                    # Generate AI response - FLUXO CONSULTIVO PROGRESSIVO
                    ai_response = f"Perfeito! Identifiquei sua necessidade: **{need_description}**\n\n"
                    
                    # NOVO: Sugerir apenas o primeiro requisito de forma conversacional
                    if structured_requirements and len(structured_requirements) > 0:
                        first_req = structured_requirements[0]
                        req_text = first_req.get('text', first_req.get('description', 'Requisito sem descrição'))
                        
                        ai_response += f"Com base na sua necessidade, sugiro começarmos com este requisito:\n\n"
                        ai_response += f"**{req_text}**\n\n"
                        ai_response += "O que você acha? Podemos manter assim, você gostaria de ajustar alguma coisa ou prefere uma abordagem diferente?"
                        
                        # Armazenar todos os requisitos na sessão, mas mostrar apenas o primeiro
                        session.set_requirements(structured_requirements)
                        session.current_requirement_index = 0  # Novo campo para controlar progresso
                    else:
                        ai_response += "Vou sugerir alguns requisitos baseados na sua necessidade. Vamos começar?"
                    
                    # PASSO 6: Return with unified contract - FLUXO CONVERSACIONAL
                    return jsonify({
                        **resp_base,
                        "kind": "conversational_requirement", 
                        "necessity": session.necessity,
                        "current_requirement": structured_requirements[0] if structured_requirements else None,
                        "total_requirements": len(structured_requirements),
                        "current_index": 0,
                        "ai_response": ai_response,
                        "message": ai_response,
                        "conversation_stage": "review_requirement_progressive"
                    })
                        
                except Exception as suggest_error:
                    print(f"🔸 Erro ao sugerir requisitos: {suggest_error}")
                    # If requirements generation fails, return error instead of continuing
                    return jsonify({"error": f"Erro ao sugerir requisitos: {str(suggest_error)}"}), 500
            
            # PASSO 5: If necessity not detected, ask for it (NO fallback suicida)
            print(f"🔹 [NO_LOCK] contains_need=False ou parse falhou → mantendo necessidade atual: {session.necessity}")
            return jsonify({
                **resp_base,
                'kind': 'text',
                'ai_response': 'Olá! Para começar o ETP, preciso entender a necessidade. Qual é a descrição da necessidade da contratação?',
                'message': 'Olá! Para começar o ETP, preciso entender a necessidade. Qual é a descrição da necessidade da contratação?',
                'conversation_stage': 'collect_need'
            })

        # If we have a necessity but no clear command was processed, use LLM with updated prompts
        # This handles cases where the command parser returned 'unclear'
        if session.conversation_stage in ['suggest_requirements', 'review_requirements']:
            system_content = f"""Você é um especialista em licitações que está ajudando a revisar requisitos para um Estudo Técnico Preliminar (ETP).

IMPORTANTE: Você está na fase de revisão de requisitos. A necessidade já está definida: {session.necessity}

JAMAIS trate mensagens como "ajuste o último", "remover 2", "trocar 3" como nova necessidade. Apenas atualize a lista existente.

Foque apenas em:
- Confirmar requisitos apresentados
- Processar ajustes específicos solicitados
- Adicionar novos requisitos
- Remover requisitos específicos

A necessidade está TRAVADA e não deve ser alterada."""
        
        # Continue with normal LLM processing for other stages
        system_content = f"""Você é um especialista em licitações que está ajudando a coletar informações para um Estudo Técnico Preliminar (ETP).

Necessidade já capturada: {session.necessity}

Seu objetivo é conduzir uma conversa natural e fluida para coletar as seguintes informações obrigatórias:
1. Descrição da necessidade da contratação ✓ (já coletada)
2. Confirmação dos requisitos sugeridos ✓ (já processada) 
3. Se há previsão no PCA (Plano de Contratações Anual)
4. Quais normas legais pretende utilizar
5. Qual o quantitativo e valor estimado
6. Se haverá parcelamento da contratação

Mantenha o tom conversacional e profissional. Faça uma pergunta por vez.
Não repita informações já coletadas."""

        # Build conversation context
        messages = [{"role": "system", "content": system_content}]
        
        # Add conversation history
        for msg in conversation_history[-5:]:  # Last 5 messages for context
            role = "user" if msg.get('sender') == 'user' else "assistant"
            messages.append({"role": role, "content": msg.get('text', '')})
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})

        # Generate response
        response = etp_generator.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=800,
            temperature=0.7
        )

        ai_response = response.choices[0].message.content.strip()

        # PASSO 6: Return with unified contract
        return jsonify({
            **resp_base,
            'kind': 'text',
            'ai_response': ai_response,
            'message': ai_response,
            'conversation_stage': session.conversation_stage
        })

    except Exception as e:
        print(f"🔸 Erro na conversa: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro na conversa: {str(e)}'
        }), 500

@etp_dynamic_bp.route('/analyze-response', methods=['POST'])
@limiter.limit("15 per minute")
@cross_origin()
def analyze_response():
    """Analisa semanticamente a resposta do usuário usando OpenAI para mapear às perguntas obrigatórias"""
    try:
        _ensure_initialized()
        if not etp_generator:
            return jsonify({'error': 'Gerador ETP não configurado'}), 500

        # PASSO 7: Reutilizar session_id corretamente
        data = request.get_json(force=True)
        sid = (data.get("session_id") or "").strip() or None
        session = EtpSession.query.filter_by(session_id=sid).first() if sid else None
        
        if not session:
            return jsonify({'error': 'Sessão não encontrada'}), 404
            
        # PASSO 7: Base de resposta com session_id
        resp_base = {"success": True, "session_id": session.session_id}

        user_response = data.get('user_response', '').strip()
        answered_questions = data.get('answered_questions', [])

        if not user_response:
            return jsonify({'error': 'Resposta do usuário é obrigatória'}), 400

        # PASSO 7: Não rodar analisador de necessidade em estágios de revisão
        if session.conversation_stage in ['suggest_requirements', 'review_requirements']:
            print(f"🔹 analyze_response: Estágio {session.conversation_stage} - não executando analisador de necessidade")
            return jsonify({
                **resp_base,
                'kind': 'text',
                'message': 'Use o endpoint /conversation para interações neste estágio'
            })

        # Definir perguntas obrigatórias
        mandatory_questions = {
            1: "Qual a descrição da necessidade da contratação?",
            2: "Há previsão no PCA (Plano de Contratações Anual)?",
            3: "Quais normas legais pretende utilizar?",
            4: "Qual o quantitativo e valor estimado?",
            5: "Haverá parcelamento da contratação?"
        }

        # Identificar perguntas ainda não respondidas
        remaining_questions = [q for q in mandatory_questions.keys() if q not in answered_questions]

        if not remaining_questions:
            return jsonify({
                **resp_base,
                'analysis': {
                    'answered_questions': [],
                    'extracted_answers': {},
                    'next_question_number': None,
                    'next_question_text': None,
                    'all_questions_answered': True,
                    'currently_answered_total': answered_questions,
                    'suggestions': [],
                    'needs_suggestion': False
                }
            })

        # Prompt para análise semântica
        analysis_prompt = f"""
        Analise a resposta do usuário e identifique quais das seguintes perguntas obrigatórias foram respondidas:

        Perguntas pendentes:
        {json.dumps({k: v for k, v in mandatory_questions.items() if k in remaining_questions}, indent=2)}

        Resposta do usuário: "{user_response}"

        Retorne um JSON com:
        {{
            "answered_questions": [números das perguntas respondidas],
            "extracted_answers": {{"número": "resposta extraída"}},
            "needs_suggestion": true/false
        }}

        Seja rigoroso: só marque como respondida se a resposta for clara e específica.
        """

        response = etp_generator.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Você é um analisador semântico especializado em extrair informações de respostas sobre licitações."},
                {"role": "user", "content": analysis_prompt}
            ],
            max_tokens=500,
            temperature=0.3
        )

        # PASSO 5: Parse response safely
        from domain.usecase.etp.utils_parser import parse_json_relaxed
        analysis_result = parse_json_relaxed(response.choices[0].message.content.strip())
        
        if not analysis_result:
            analysis_result = {
                "answered_questions": [],
                "extracted_answers": {},
                "needs_suggestion": False
            }

        # Atualizar lista de perguntas respondidas
        newly_answered = analysis_result.get('answered_questions', [])
        currently_answered = set(answered_questions + newly_answered)

        # Determinar próxima pergunta
        remaining_questions = [q for q in mandatory_questions.keys() if q not in currently_answered]
        next_question_text = None
        suggestions = []
        needs_suggestion = analysis_result.get('needs_suggestion', False)

        if remaining_questions:
            next_q_num = remaining_questions[0]
            if next_q_num == 2:
                next_question_text = "👉 **Agora, há previsão no PCA (Plano de Contratações Anual)?**"
            elif next_q_num == 3:
                next_question_text = "👉 **Quais normas legais pretende utilizar para esta contratação?**"
                suggestions = ["Lei 14.133/2021", "Lei 8.666/1993", "Decreto 10.024/2019"]
            elif next_q_num == 4:
                next_question_text = "👉 **Qual o quantitativo e valor estimado para esta contratação?**"
            elif next_q_num == 5:
                next_question_text = "👉 **Haverá parcelamento da contratação?**"
            
            # Fallback for other questions
            if not next_question_text:
                question_texts = {
                    2: "Há previsão no PCA (Plano de Contratações Anual)?",
                    3: "Quais normas legais pretende utilizar?",
                    4: "Qual o quantitativo e valor estimado?",
                    5: "Haverá parcelamento da contratação?"
                }
                next_question_text = question_texts[next_q_num]

        return jsonify({
            **resp_base,
            'analysis': {
                'answered_questions': analysis_result['answered_questions'],
                'extracted_answers': analysis_result['extracted_answers'],
                'next_question_number': remaining_questions[0] if remaining_questions else None,
                'next_question_text': next_question_text,
                'all_questions_answered': len(remaining_questions) == 0,
                'currently_answered_total': list(currently_answered),
                'suggestions': suggestions,
                'needs_suggestion': needs_suggestion
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao analisar resposta: {str(e)}'
        }), 500

@etp_dynamic_bp.route('/confirm-requirements', methods=['POST'])
@cross_origin()
def confirm_requirements():
    """Processa a confirmação, ajuste ou rejeição de requisitos pelo usuário"""
    try:
        _ensure_initialized()
        if not etp_generator:
            return jsonify({'error': 'Gerador ETP não configurado'}), 500

        # PASSO 8: Reutilizar session_id corretamente
        data = request.get_json(force=True)
        sid = (data.get("session_id") or "").strip() or None
        session = EtpSession.query.filter_by(session_id=sid).first() if sid else None
        
        if not session:
            return jsonify({'error': 'Sessão não encontrada'}), 404
            
        # PASSO 8: Base de resposta com session_id
        resp_base = {"success": True, "session_id": session.session_id}
        
        user_action = data.get('action', '')  # 'accept', 'modify', 'add', 'remove'
        requirements = data.get('requirements', [])
        user_message = data.get('message', '')

        # Standardize the next question for consistent flow
        next_question = "👉 **Agora, há previsão no PCA (Plano de Contratações Anual)?**"
        
        # Processar a ação do usuário
        if user_action == 'accept':
            # Usuário aceitou todos os requisitos
            confirmed_requirements = requirements
            ai_response = f"**Perfeito! Requisitos confirmados.**\n\n{next_question}"
            print(f"🔹 Usuário aceitou os requisitos: {len(confirmed_requirements)} requisitos confirmados")

        elif user_action == 'modify':
            # Usuário quer modificar alguns requisitos
            print(f"🔹 Usuário solicitou modificação nos requisitos: {user_message}")
            modify_prompt = f"""
            O usuário quer modificar os requisitos sugeridos. Processe a solicitação:

            Requisitos originais: {requirements}
            Solicitação do usuário: "{user_message}"

            Retorne APENAS um JSON com:
            - "updated_requirements": array com requisitos atualizados
            - "explanation": breve explicação das mudanças feitas
            """

            response = etp_generator.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Você é um especialista em requisitos técnicos para licitações."},
                    {"role": "user", "content": modify_prompt}
                ],
                max_tokens=800,
                temperature=0.7
            )

            # PASSO 5: Parse response safely
            from domain.usecase.etp.utils_parser import parse_json_relaxed
            modification_result = parse_json_relaxed(response.choices[0].message.content.strip())
            
            if modification_result and 'updated_requirements' in modification_result:
                confirmed_requirements = modification_result['updated_requirements']
                explanation = modification_result.get('explanation', 'Requisitos atualizados conforme solicitado.')
                ai_response = f"**Requisitos atualizados!**\n\n{explanation}\n\n{next_question}"
            else:
                # Fallback if parsing fails
                confirmed_requirements = requirements
                ai_response = f"**Mantive os requisitos originais.** Não consegui processar a modificação solicitada.\n\n{next_question}"

        else:
            # Ação não reconhecida - manter requisitos originais
            confirmed_requirements = requirements
            ai_response = f"**Requisitos mantidos.**\n\n{next_question}"

        # Armazenar requisitos confirmados na sessão
        answers = session.get_answers()
        answers['confirmed_requirements'] = confirmed_requirements
        session.set_answers(answers)
        session.updated_at = datetime.utcnow()

        db.session.commit()

        # PASSO 8: Não retroceder estágio - manter em review_requirements ou avançar
        if user_action == 'accept':
            session.conversation_stage = 'legal_norms'  # Avançar para próxima fase
        else:
            session.conversation_stage = 'review_requirements'  # Manter em revisão
        
        session.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({
            **resp_base,
            'kind': 'requirements_confirmed',
            'confirmed_requirements': confirmed_requirements,
            'ai_response': ai_response,
            'message': ai_response,
            'conversation_stage': session.conversation_stage
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao confirmar requisitos: {str(e)}'
        }), 500

@etp_dynamic_bp.route('/suggest-requirements', methods=['POST'])
@cross_origin()
def suggest_requirements():
    """Sugere requisitos baseados na necessidade identificada"""
    try:
        _ensure_initialized()
        if not etp_generator:
            return jsonify({'error': 'Gerador ETP não configurado'}), 500

        data = request.get_json()
        necessity = data.get('necessity', '').strip()

        if not necessity:
            return jsonify({'error': 'Necessidade é obrigatória'}), 400

        # Usar RAG para encontrar requisitos similares
        rag_results = search_requirements("generic", necessity, k=5)
        
        # Gerar requisitos estruturados
        requirements_prompt = f"""
        Baseado na necessidade: "{necessity}"
        
        E nos seguintes exemplos de requisitos similares:
        {json.dumps(rag_results, indent=2)}
        
        Gere uma lista de 3-5 requisitos específicos e objetivos para esta contratação.
        
        Retorne APENAS um JSON no formato:
        {{
            "suggested_requirements": [
                {{"id": "R1", "text": "Descrição do requisito", "justification": "Justificativa"}},
                {{"id": "R2", "text": "Descrição do requisito", "justification": "Justificativa"}}
            ],
            "consultative_message": "Requisitos sugeridos baseados na necessidade identificada"
        }}
        """
        
        response = etp_generator.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Você é um especialista em licitações que gera requisitos técnicos precisos."},
                {"role": "user", "content": requirements_prompt}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        
        # PASSO 5: Parse response safely
        from domain.usecase.etp.utils_parser import parse_requirements_response_safely
        structured_requirements = parse_requirements_response_safely(
            response.choices[0].message.content.strip()
        )

        return jsonify({
            'success': True,
            'requirements': structured_requirements.get('suggested_requirements', []),
            'message': structured_requirements.get('consultative_message', ''),
            'necessity': necessity,
            'rag_sources': len(rag_results),
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao sugerir requisitos: {str(e)}'
        }), 500
