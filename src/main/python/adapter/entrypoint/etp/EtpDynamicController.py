import os
import json
import uuid
import tempfile
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file
from flask_cors import cross_origin

from domain.interfaces.dataprovider.DatabaseConfig import db
from domain.dto.EtpOrm import EtpSession
from domain.dto.EtpDto import DocumentAnalysis, KnowledgeBase, ChatSession, EtpTemplate
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
                {"role": "system", "content": "Você é um consultor especialista em contratações públicas."},
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

@etp_dynamic_bp.route('/chat', methods=['POST'])
@cross_origin()
def chat_endpoint():
    """
    Unified chat endpoint that combines Analyzer (Prompt 1) + Dialogue (Prompt 2).
    Maintains session state without resets.
    
    Request JSON:
    {
        "session_id": "<uuid from client>",
        "message": "<user message>",
        "conversation_history": [{"role":"user|assistant","content":"..."}],
        "need": "<current necessity or empty>",
        "requirements": [{"id":"R1","text":"..."}, ...],
        "version": <int>
    }
    
    Response JSON:
    {
        "reply_markdown": "<natural response in Markdown>",
        "requirements": [{"id":"R1","text":"..."}, ...],
        "meta": {
            "need": "<current necessity>",
            "version": <int>
        }
    }
    """
    try:
        _ensure_initialized()
        if not etp_generator:
            return jsonify({'error': 'Gerador ETP não configurado'}), 500

        data = request.get_json()
        
        # Extract request data
        session_id = data.get('session_id', '').strip()
        user_message = data.get('message', '').strip()
        conversation_history = data.get('conversation_history', [])
        client_need = data.get('need', '').strip()
        client_requirements = data.get('requirements', [])
        client_version = data.get('version', 0)

        if not user_message:
            return jsonify({'error': 'Mensagem é obrigatória'}), 400

        # STEP 1: Load or create session (DO NOT generate new session_id)
        session = None
        if session_id:
            session = EtpSession.query.filter_by(session_id=session_id).first()
        
        if not session:
            # Only create new session if client didn't provide one
            if not session_id:
                session_id = str(uuid.uuid4())
            
            session = EtpSession(
                user_id=1,  # Default user
                session_id=session_id,
                status='active',
                answers=json.dumps({}),
                conversation_stage='collect_need',
                necessity=client_need if client_need else None,
                requirements_json=json.dumps(client_requirements, ensure_ascii=False) if client_requirements else json.dumps([]),
                requirements_version=client_version,
                created_at=datetime.utcnow()
            )
            db.session.add(session)
            db.session.commit()
        
        # STEP 2: Call Analyzer (Prompt 1) to check if message contains new necessity
        analyzer_result = call_analyzer_prompt(
            user_message=user_message,
            conversation_history=conversation_history,
            current_need=session.necessity or ""
        )
        
        contains_need = analyzer_result.get('contains_need', False)
        need_description = analyzer_result.get('need_description', '')
        
        # If new necessity detected, reset requirements
        if contains_need and need_description:
            session.necessity = need_description
            session.set_requirements([])
            session.requirements_version = 1
        
        # STEP 3: Call Dialogue (Prompt 2) with exact system prompt
        dialogue_input = {
            'need': session.necessity or "",
            'requirements': session.get_requirements(),
            'version': session.requirements_version,
            'history': conversation_history,
            'message': user_message
        }
        
        dialogue_result = call_dialogue_model(dialogue_input)
        
        # STEP 4: Update session state
        session.necessity = dialogue_result['meta']['need']
        session.set_requirements(dialogue_result['requirements'])
        session.requirements_version = dialogue_result['meta']['version']
        session.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify(dialogue_result)

    except Exception as e:
        print(f"🔸 Erro no chat endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': f'Erro no chat: {str(e)}'
        }), 500


def call_analyzer_prompt(user_message, conversation_history, current_need):
    """
    Analyzer (Prompt 1): Detects if user message contains a new necessity.
    Returns: {"contains_need": bool, "need_description": str}
    """
    try:
        _ensure_initialized()
        
        messages = [
            {
                "role": "system",
                "content": """Você é um ANALISADOR de intenção. Recebe a última mensagem do usuário + histórico.
Tarefa: dizer se a mensagem DEFINE uma nova necessidade (tema do ETP) ou não.

REGRAS:
- Se já existe uma necessidade definida no histórico e a nova mensagem só pede ajustes nos requisitos
  (ex.: "inclua outros", "troque o R4", "remova o item 2", "mantenha esses"), ENTÃO NÃO crie nova necessidade.
  Retorne contains_need=false e need_description="".
- Só retorne contains_need=true quando o usuário de fato apresentar um NOVO tema/escopo para a contratação
  (ou disser explicitamente que mudou o tema).
- Saída OBRIGATÓRIA em JSON estrito:
  {
    "contains_need": true|false,
    "need_description": "<texto ou vazio>"
  }
- Não escreva nada além do JSON."""
            }
        ]
        
        # Add conversation history
        for msg in conversation_history:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })
        
        # Add current need context if exists
        if current_need:
            messages.append({
                "role": "system",
                "content": f"Necessidade atual já definida: {current_need}"
            })
        
        # Add user message
        messages.append({
            "role": "user",
            "content": user_message
        })

        response = etp_generator.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=300,
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        return {
            'contains_need': result.get('contains_need', False),
            'need_description': result.get('need_description', '')
        }
    except Exception as e:
        print(f"🔸 Erro no Analyzer: {e}")
        return {'contains_need': False, 'need_description': ''}


def call_dialogue_model(dialogue_input):
    """
    Dialogue (Prompt 2): ETP Consultant with RAG-first approach and strict JSON output.
    Returns: {"necessidade": str, "requisitos": [], "estado": {}}
    """
    try:
        _ensure_initialized()
        
        need = dialogue_input['need']
        requirements = dialogue_input['requirements']
        version = dialogue_input['version']
        history = dialogue_input['history']
        user_message = dialogue_input['message']
        
        # RAG-first: Search knowledge base for relevant requirements
        kb_context = ""
        if need:
            try:
                rag_results = search_requirements("generic", need, k=5)
                if rag_results:
                    kb_context = "\n\nConteúdo recuperado da base de conhecimento:\n"
                    for idx, result in enumerate(rag_results[:3], 1):
                        kb_context += f"{idx}. {result.get('content', '')}\n"
            except Exception as e:
                print(f"⚠️ Erro ao buscar RAG: {e}")
        
        # New system prompt from issue description
        system_prompt = """Você é Consultor(a) de ETP (Estudo Técnico Preliminar) para compras públicas.
Atue como consultor durante todo o fluxo, seguindo RAG-first: sempre consulte a base de conhecimento antes de escrever qualquer coisa. Só gere conteúdo novo quando a base não cobrir.

Regras inquebráveis

Saída sempre em JSON válido. Sem texto fora do JSON. Sem markdown, títulos, bullets, explicações ou comentários.

Formato de saída (mínimo e estável):

{
  "necessidade": "<texto curto e claro>",
  "requisitos": ["R1 ...", "R2 ...", "R3 ...", "R4 ...", "R5 ..."],
  "estado": {
    "etapa_atual": "<nome_da_etapa>",
    "proxima_etapa": "<nome_da_proxima_etapa>|null",
    "origem_requisitos": "base|gerado",
    "requisitos_confirmados": true|false
  }
}

requisitos é lista de strings (R1…R5). Não inclua "Justificativa" nem campos extras.

Se houver menos ou mais itens na base, normalize para 5 itens claros e não redundantes (se necessário, consolide).

origem_requisitos: "base" se vierem da base; "gerado" se não houver evidência suficiente.

RAG-first:

Use os índices fornecidos pelo sistema (BM25/FAISS). Busque pelos termos da necessidade, sinônimos e variações.

Se os trechos recuperados forem suficientes/coerentes, monte os requisitos a partir deles.

Se forem insuficientes, aí sim gere requisitos originais com boas práticas do domínio.

Persistência do fluxo (não reiniciar):

Nunca retorne à pergunta inicial se já existe necessidade no contexto.

Ajustes: quando o usuário pedir "troque o R1", "melhore o R3", "remova o R4" etc., mantenha os demais itens e retorne a lista completa atualizada (R1…R5) no mesmo formato.

Aceite: se o usuário disser "aceito", "ok", "pode seguir", defina estado.requisitos_confirmados = true e avance etapa_atual para a próxima etapa, sem apagar necessidade e requisitos.

Estilo dos requisitos: curtos, objetivos, verificáveis. Sem números dentro do texto que conflitem com a numeração R1..R5.

Idioma: português do Brasil.

Etapas do fluxo (sempre agir como consultor)

O servidor controla a etapa; você nunca deve voltar ao início por conta própria.

coleta_necessidade → sugestao_requisitos → ajustes_requisitos → confirmacao_requisitos → próximas etapas do ETP (benefícios, alternativas, riscos, estimativa de custos, marco legal etc.) conforme o sistema indicar.

Se a etapa não vier explícita, infira pelo último estado recebido e continue.

Interpretação de comandos do usuário

"gera requisitos", "sugira requisitos", "quero 5 requisitos" ⇒ produzir requisitos conforme regras.

"não gostei do R1", "troque o R3 por algo sobre manutenção", "remova o R4" ⇒ aplicar a mudança e devolver a lista inteira atualizada.

"aceito", "pode seguir", "concluir requisitos" ⇒ marcar requisitos_confirmados=true e avançar proxima_etapa.

Perguntas abertas ("e agora?", "o que falta?") ⇒ responder apenas com o JSON no formato acima, atualizando etapa_atual/proxima_etapa.

Validações antes de responder

Se não houver necessidade no contexto e o usuário pedir requisitos, crie necessidade a partir da mensagem dele (curta e clara) e siga.

Nunca inclua campo "justificativa". Se a base trouxer justificativas, não as exponha no JSON.

Sempre retorne a lista completa R1..R5 depois de qualquer ajuste."""
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add RAG context if available
        if kb_context:
            messages.append({"role": "system", "content": kb_context})
        
        # Convert old format requirements to new format (list of strings)
        requisitos_str = []
        if requirements:
            for req in requirements:
                req_id = req.get('id', '')
                req_text = req.get('text', '')
                requisitos_str.append(f"{req_id} — {req_text}")
        
        # Determine current stage
        etapa_atual = "coleta_necessidade"
        if need and not requirements:
            etapa_atual = "sugestao_requisitos"
        elif need and requirements:
            etapa_atual = "ajustes_requisitos"
        
        # Add context about current state
        context_msg = f"""Contexto atual:
- Necessidade: {need if need else "ainda não definida"}
- Requisitos atuais: {json.dumps(requisitos_str, ensure_ascii=False) if requisitos_str else "[]"}
- Etapa atual: {etapa_atual}
- Versão: {version}"""
        
        messages.append({"role": "system", "content": context_msg})
        
        # Add conversation history
        for msg in history[-10:]:  # Last 10 messages
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})

        response = etp_generator.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=1500,
            temperature=0.1,  # Lower temperature for more consistent JSON output
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        
        # Convert new format to old format for backward compatibility
        # New format: {"necessidade": str, "requisitos": ["R1 ...", "R2 ..."], "estado": {...}}
        # Old format: {"reply_markdown": str, "requirements": [{"id": "R1", "text": "..."}], "meta": {...}}
        
        if 'necessidade' in result and 'requisitos' in result and 'estado' in result:
            # New format detected - convert to old format
            converted_requirements = []
            requisitos = result.get('requisitos', [])
            
            for idx, req_str in enumerate(requisitos):
                # Parse "R1 — text" or "R1 - text" format
                if '—' in req_str:
                    parts = req_str.split('—', 1)
                    req_id = parts[0].strip()
                    req_text = parts[1].strip()
                elif ' - ' in req_str:
                    parts = req_str.split(' - ', 1)
                    req_id = parts[0].strip()
                    req_text = parts[1].strip()
                else:
                    # Fallback if format is different
                    req_id = f"R{idx+1}"
                    req_text = req_str.strip()
                
                converted_requirements.append({
                    "id": req_id,
                    "text": req_text
                })
            
            estado = result.get('estado', {})
            necessidade = result.get('necessidade', need or '')
            
            # Generate a simple reply message based on stage
            etapa_atual = estado.get('etapa_atual', 'sugestao_requisitos')
            reply = ""
            if etapa_atual == 'coleta_necessidade':
                reply = "Por favor, descreva a necessidade da contratação."
            elif etapa_atual == 'sugestao_requisitos':
                reply = "Aqui estão os requisitos sugeridos com base na necessidade identificada."
            elif etapa_atual == 'ajustes_requisitos':
                reply = "Requisitos atualizados. Você pode solicitar mais ajustes ou confirmar."
            elif etapa_atual == 'confirmacao_requisitos':
                if estado.get('requisitos_confirmados'):
                    reply = "Requisitos confirmados! Podemos prosseguir para a próxima etapa."
                else:
                    reply = "Por favor, revise os requisitos e confirme se está de acordo."
            else:
                reply = "Como posso ajudá-lo com o ETP?"
            
            # Increment version if requirements changed
            new_version = version
            if converted_requirements != requirements:
                new_version = version + 1
            
            result = {
                'reply_markdown': reply,
                'requirements': converted_requirements,
                'meta': {
                    'need': necessidade,
                    'version': new_version,
                    'estado': estado  # Keep original estado for debugging
                }
            }
        else:
            # Old format or fallback - ensure no justification fields
            if 'requirements' in result:
                for req in result['requirements']:
                    if 'justification' in req:
                        del req['justification']
                    if 'justificativa' in req:
                        del req['justificativa']
            
            # Validate response structure
            if 'reply_markdown' not in result:
                result['reply_markdown'] = "Olá! Como posso ajudar com seu ETP?"
            if 'requirements' not in result:
                result['requirements'] = requirements
            if 'meta' not in result:
                result['meta'] = {'need': need, 'version': version}
        
        return result
        
    except Exception as e:
        print(f"🔸 Erro no Dialogue: {e}")
        # Return fallback response
        return {
            'reply_markdown': f"Entendi sua mensagem. Como posso ajudar?",
            'requirements': dialogue_input['requirements'],
            'meta': {
                'need': dialogue_input['need'],
                'version': dialogue_input['version']
            }
        }


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
                    rag_results = search_requirements("generic", need_description, k=5)
                    
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
                    
                    # Generate AI response
                    ai_response = f"Perfeito! Identifiquei sua necessidade: **{need_description}**\n\n"
                    
                    # Add formatted requirements list with proper Markdown formatting
                    if structured_requirements:
                        ai_response += "**Requisitos sugeridos para este tipo de contratação:**\n\n"
                        for req in structured_requirements:
                            req_id = req.get('id', 'R?')
                            req_text = req.get('text', req.get('description', 'Requisito sem descrição'))
                            ai_response += f"**{req_id}** - {req_text}\n"
                        ai_response += "\n👉 **Você gostaria de manter esses requisitos, ajustar algum deles ou incluir outros?**"
                    
                    # PASSO 6: Return with unified contract
                    return jsonify({
                        **resp_base,
                        "kind": "requirements_suggestion", 
                        "necessity": session.necessity,
                        "requirements": structured_requirements,
                        "ai_response": ai_response,
                        "message": ai_response,
                        "conversation_stage": "suggest_requirements"
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
        
        # Gerar requisitos no formato R# — descrição (sem justificativas)
        requirements_prompt = f"""
        Baseado na necessidade: "{necessity}"
        
        E nos seguintes exemplos de requisitos similares:
        {json.dumps(rag_results, indent=2)}
        
        Gere uma lista de 3-5 requisitos específicos e objetivos para esta contratação.
        
        FORMATO OBRIGATÓRIO:
        Retorne APENAS uma lista de requisitos no formato:
        R1 — <descrição do requisito em uma única linha>
        R2 — <descrição do requisito em uma única linha>
        R3 — <descrição do requisito em uma única linha>
        
        REGRAS ESTRITAS:
        - NÃO inclua justificativas, explicações ou qualquer texto adicional
        - Cada linha deve começar com R seguido de número, espaço, travessão — e espaço
        - Cada requisito em uma única linha
        - Sem bullets, asteriscos, numeração dupla, tabelas ou JSON
        - Requisitos devem ser específicos e verificáveis
        
        Retorne SOMENTE as linhas no formato R# — descrição, nada mais.
        """
        
        response = etp_generator.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Você é um especialista em licitações que gera requisitos técnicos precisos no formato R# — descrição, sem justificativas."},
                {"role": "user", "content": requirements_prompt}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        
        # Parse response in R# — format
        result_raw = response.choices[0].message.content.strip()
        
        # Parse requirements from R# — format
        requirements = []
        for line in result_raw.split('\n'):
            line = line.strip()
            if line and (line.startswith('R') or (line and line[0].isdigit())):
                requirements.append(line)
        
        # Fallback if no requirements were parsed
        if not requirements:
            requirements = [
                f"R1 — Requisitos técnicos específicos para {necessity.lower()}",
                "R2 — Especificações técnicas adequadas ao objeto da contratação",
                "R3 — Comprovação de capacidade técnica adequada"
            ]

        return jsonify({
            'success': True,
            'requirements': requirements,
            'message': 'Requisitos sugeridos baseados na necessidade identificada e na base de conhecimento.',
            'necessity': necessity,
            'rag_sources': len(rag_results),
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao sugerir requisitos: {str(e)}'
        }), 500
