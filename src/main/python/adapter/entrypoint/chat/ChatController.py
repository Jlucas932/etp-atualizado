import os
import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, session
from flask_cors import cross_origin
import openai

from domain.interfaces.dataprovider.DatabaseConfig import db
from domain.dto.EtpDto import ChatSession, EtpSession
from domain.dto.UserDto import User
from domain.dto.KbDto import KbChunk
from domain.services.requirements_interpreter import (
    parse_update_command, apply_update_command, detect_requirements_discussion, 
    format_requirements_list
)

chat_bp = Blueprint('chat', __name__)

logger = logging.getLogger(__name__)

# Configurar cliente OpenAI
openai_api_key = os.getenv('OPENAI_API_KEY')
openai_client = openai.OpenAI(api_key=openai_api_key) if openai_api_key else None

def search_relevant_chunks(query_text, limit=3):
    """Busca chunks relevantes na knowledge base baseado na consulta do usuário"""
    try:
        # Busca simples por texto nas chunks
        chunks = KbChunk.query.filter(
            KbChunk.content_text.contains(query_text)
        ).limit(limit).all()
        
        if not chunks:
            # Se não encontrar com a query completa, tenta com palavras individuais
            words = query_text.split()
            if len(words) > 1:
                for word in words:
                    if len(word) > 3:  # Ignorar palavras muito pequenas
                        chunks = KbChunk.query.filter(
                            KbChunk.content_text.contains(word)
                        ).limit(limit).all()
                        if chunks:
                            break
        
        return chunks
    except Exception as e:
        logger.error("Erro ao buscar chunks relevantes: %s", e, exc_info=True)
        return []

@chat_bp.route('/health', methods=['GET'])
@cross_origin()
def health_check():
    """Verificação de saúde da API de chat"""
    return jsonify({
        'status': 'healthy',
        'version': '3.0.0',
        'openai_configured': bool(openai_api_key),
        'features': ['chat_support', 'etp_assistance', 'legal_guidance'],
        'timestamp': datetime.now().isoformat()
    })

@chat_bp.route('/message', methods=['POST'])
@cross_origin()
def send_message_direct():
    """Envia uma mensagem no chat (compatibilidade com frontend antigo)"""
    try:
        # Verificar autenticação e limites de chat
        if 'user_id' not in session:
            return jsonify({
                'success': False,
                'error': 'Usuário não autenticado'
            }), 401
        
        current_user = User.query.get(session['user_id'])
        if not current_user:
            return jsonify({
                'success': False,
                'error': 'Usuário não encontrado'
            }), 404
        
        # Verificar limite de mensagens de chat (demo)
        if not current_user.can_send_chat_message():
            return jsonify({
                'success': False,
                'error': 'Você atingiu o limite de 5 perguntas na versão demo.',
                'limit_reached': True
            }), 429
        
        if not openai_client:
            return jsonify({
                'success': False,
                'error': 'OpenAI não configurado. Verifique a variável OPENAI_API_KEY.'
            }), 500

        data = request.get_json()
        user_message = data.get('message')
        session_id = data.get('session_id')  # Opcional para compatibilidade

        if not user_message:
            return jsonify({
                'success': False,
                'error': 'Mensagem é obrigatória'
            }), 400

        # Se há session_id, tentar usar contexto da sessão ETP
        etp_context = ""
        etp_session = None
        if session_id:
            etp_session = EtpSession.query.filter_by(session_id=session_id).first()
            if etp_session:
                answers = etp_session.get_answers()
                if answers:
                    etp_context = f"\nContexto da sessão ETP:\n{json.dumps(answers, indent=2, ensure_ascii=False)}"
        
        # NOVA LÓGICA: Verificar se está na fase de requisitos e aplicar interpretador
        if etp_session and etp_session.conversation_stage in ['suggest_requirements', 'review_requirements']:
            # Verificar se a mensagem é sobre requisitos
            if detect_requirements_discussion(user_message):
                return handle_requirements_revision(etp_session, user_message, current_user)
        
        # Se não é sobre requisitos ou não tem sessão ETP, continuar fluxo normal

        # Buscar chunks relevantes na knowledge base
        relevant_chunks = search_relevant_chunks(user_message)
        kb_context = ""
        if relevant_chunks:
            kb_context = "\nDocumentos da base de conhecimento relevantes:\n"
            for i, chunk in enumerate(relevant_chunks, 1):
                kb_context += f"\n--- Documento {i} ---\n{chunk.content_text[:500]}...\n"
            kb_context += "\nUse essas informações para enriquecer sua resposta quando relevante."

        # Gerar resposta da IA
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": f"""Você é um assistente especializado EXCLUSIVAMENTE em contratações públicas, Estudos Técnicos Preliminares (ETP) e na Lei 14.133/21.

                    IMPORTANTE: Você deve responder APENAS sobre contratações públicas. Se a pergunta não estiver relacionada a este tema, responda com: "Este chat foi configurado para responder apenas sobre contratações públicas. Por favor, reformule sua pergunta nesse contexto."

                    Temas permitidos:
                    1. Estudos Técnicos Preliminares (ETP)
                    2. Lei 14.133/21 (Nova Lei de Licitações)
                    3. Procedimentos licitatórios
                    4. Contratos administrativos
                    5. Pregão eletrônico
                    6. Modalidades licitatórias
                    7. Documentação para licitações
                    8. Aspectos técnicos de contratações públicas

                    Diretrizes:
                    - Seja preciso e técnico
                    - Cite artigos da lei quando relevante
                    - Mantenha linguagem formal e profissional
                    - Foque em aspectos práticos e aplicáveis
                    - REJEITE qualquer pergunta fora do escopo de contratações públicas
                    - Quando disponível, utilize as informações dos documentos da base de conhecimento para enriquecer suas respostas

                    {etp_context}{kb_context}"""
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            max_tokens=1000,
            temperature=0.3
        )

        ai_response = response.choices[0].message.content

        # Se há session_id, salvar no histórico da sessão
        if session_id:
            chat_session = ChatSession.query.filter_by(session_id=session_id).first()
            if not chat_session:
                # Criar nova sessão de chat se não existir
                chat_session = ChatSession(
                    session_id=session_id,
                    messages=json.dumps([]),
                    context='Assistente especializado em ETP e Lei 14.133/21',
                    status='active',
                    created_at=datetime.utcnow()
                )
                db.session.add(chat_session)

            # Adicionar mensagens ao histórico
            chat_session.add_message('user', user_message)
            chat_session.add_message('assistant', ai_response)
            chat_session.updated_at = datetime.utcnow()

            db.session.commit()
        
        # Incrementar contador de mensagens de chat (demo limit)
        current_user.increment_chat_messages_sent()
        db.session.commit()

        return jsonify({
            'success': True,
            'response': ai_response,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chat_bp.route('/session/<session_id>/start', methods=['POST'])
@cross_origin()
def start_chat_session(session_id):
    """Inicia uma sessão de chat para uma sessão ETP"""
    try:
        # Verificar se a sessão ETP existe
        etp_session = EtpSession.query.filter_by(session_id=session_id).first()
        if not etp_session:
            return jsonify({'error': 'Sessão ETP não encontrada'}), 404

        # Verificar se já existe uma sessão de chat
        existing_chat = ChatSession.query.filter_by(session_id=session_id).first()
        if existing_chat:
            return jsonify({
                'success': True,
                'chat_session': existing_chat.to_dict(),
                'message': 'Sessão de chat já existe'
            })

        # Criar nova sessão de chat
        chat_session = ChatSession(
            session_id=session_id,
            messages=json.dumps([]),
            context='Assistente especializado em ETP e Lei 14.133/21',
            status='active',
            created_at=datetime.utcnow()
        )

        db.session.add(chat_session)
        db.session.commit()

        return jsonify({
            'success': True,
            'chat_session': chat_session.to_dict(),
            'message': 'Sessão de chat iniciada com sucesso'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chat_bp.route('/session/<session_id>/message', methods=['POST'])
@cross_origin()
def send_message(session_id):
    """Envia uma mensagem no chat"""
    try:
        if not openai_client:
            return jsonify({'error': 'OpenAI não configurado'}), 500

        data = request.get_json()
        user_message = data.get('message')

        if not user_message:
            return jsonify({'error': 'Mensagem é obrigatória'}), 400

        # Buscar sessão de chat
        chat_session = ChatSession.query.filter_by(session_id=session_id).first()
        if not chat_session:
            return jsonify({'error': 'Sessão de chat não encontrada'}), 404

        # Buscar contexto da sessão ETP
        etp_session = EtpSession.query.filter_by(session_id=session_id).first()
        etp_context = ""
        if etp_session:
            answers = etp_session.get_answers()
            if answers:
                etp_context = f"\nContexto da sessão ETP:\n{json.dumps(answers, indent=2, ensure_ascii=False)}"

        # Adicionar mensagem do usuário
        chat_session.add_message('user', user_message)

        # Preparar contexto para IA
        messages = chat_session.get_messages()

        # Construir histórico de mensagens para OpenAI
        openai_messages = [
            {
                "role": "system",
                "content": f"""Você é um assistente especializado em Estudos Técnicos Preliminares (ETP) e na Lei 14.133/21.

                Suas responsabilidades:
                1. Ajudar com dúvidas sobre elaboração de ETP
                2. Esclarecer aspectos da Lei 14.133/21
                3. Orientar sobre procedimentos licitatórios
                4. Fornecer suporte técnico durante a geração de documentos

                Diretrizes:
                - Seja preciso e técnico
                - Cite artigos da lei quando relevante
                - Mantenha linguagem formal e profissional
                - Foque em aspectos práticos e aplicáveis

                {etp_context}"""
            }
        ]

        # Adicionar mensagens do histórico (últimas 10 para não exceder limite)
        for msg in messages[-10:]:
            openai_messages.append({
                "role": msg['role'],
                "content": msg['content']
            })

        # Gerar resposta da IA
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=openai_messages,
            max_tokens=1000,
            temperature=0.3
        )

        ai_response = response.choices[0].message.content

        # Adicionar resposta da IA
        chat_session.add_message('assistant', ai_response)
        chat_session.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            'success': True,
            'response': ai_response,
            'message_count': len(chat_session.get_messages()),
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chat_bp.route('/session/<session_id>/history', methods=['GET'])
@cross_origin()
def get_chat_history(session_id):
    """Retorna histórico do chat"""
    try:
        chat_session = ChatSession.query.filter_by(session_id=session_id).first()
        if not chat_session:
            return jsonify({'error': 'Sessão de chat não encontrada'}), 404

        return jsonify({
            'success': True,
            'messages': chat_session.get_messages(),
            'session_info': {
                'status': chat_session.status,
                'created_at': chat_session.created_at.isoformat() if chat_session.created_at else None,
                'updated_at': chat_session.updated_at.isoformat() if chat_session.updated_at else None
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chat_bp.route('/session/<session_id>/clear', methods=['POST'])
@cross_origin()
def clear_chat_history(session_id):
    """Limpa histórico do chat"""
    try:
        chat_session = ChatSession.query.filter_by(session_id=session_id).first()
        if not chat_session:
            return jsonify({'error': 'Sessão de chat não encontrada'}), 404

        chat_session.set_messages([])
        chat_session.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Histórico do chat limpo com sucesso'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chat_bp.route('/conversations', methods=['GET'])
@cross_origin()
def list_conversations():
    """Lista todas as conversas do usuário atual"""
    try:
        # Verificar autenticação
        if 'user_id' not in session:
            return jsonify({
                'success': False,
                'error': 'Usuário não autenticado'
            }), 401

        user_id = session['user_id']
        
        # Buscar todas as sessões ETP do usuário que têm chat
        etp_sessions_with_chat = db.session.query(EtpSession).join(ChatSession).filter(
            EtpSession.user_id == user_id
        ).order_by(EtpSession.updated_at.desc()).all()
        
        conversations = []
        for etp_session in etp_sessions_with_chat:
            # Pegar a primeira mensagem do usuário como título
            chat_session = ChatSession.query.filter_by(session_id=etp_session.session_id).first()
            if chat_session:
                messages = chat_session.get_messages()
                title = "Nova Conversa"
                if messages:
                    # Procurar primeira mensagem do usuário
                    for msg in messages:
                        if msg.get('role') == 'user':
                            content = msg.get('content', '')
                            title = content[:50] + ('...' if len(content) > 50 else '')
                            break
                
                conversations.append({
                    'session_id': etp_session.session_id,
                    'title': title,
                    'message_count': len(messages),
                    'last_updated': etp_session.updated_at.isoformat(),
                    'created_at': etp_session.created_at.isoformat()
                })
        
        return jsonify({
            'success': True,
            'conversations': conversations
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chat_bp.route('/general', methods=['POST'])
@cross_origin()
def general_chat():
    """Chat geral sobre ETP e Lei 14.133/21 (sem sessão específica)"""
    try:
        if not openai_client:
            return jsonify({
                'success': False,
                'error': 'OpenAI não configurado. Verifique a variável OPENAI_API_KEY.'
            }), 500

        data = request.get_json()
        user_message = data.get('message')

        if not user_message:
            return jsonify({
                'success': False,
                'error': 'Mensagem é obrigatória'
            }), 400
        
        # Gerar resposta direta
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": """Você é um assistente especializado em Estudos Técnicos Preliminares (ETP) e na Lei 14.133/21.
                    
                    Forneça respostas precisas, técnicas e práticas sobre:
                    - Elaboração de ETP
                    - Procedimentos da Lei 14.133/21
                    - Licitações e contratos públicos
                    - Critérios de sustentabilidade
                    - Modalidades licitatórias
                    
                    Mantenha linguagem formal e cite artigos da lei quando relevante."""
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            max_tokens=1000,
            temperature=0.3
        )
        
        ai_response = response.choices[0].message.content
        
        return jsonify({
            'success': True,
            'response': ai_response,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def handle_requirements_revision(etp_session, user_message, current_user):
    """Trata revisões de requisitos usando o interpretador determinístico"""
    try:
        # Obter requisitos atuais da sessão
        current_requirements = etp_session.get_requirements()
        necessity = etp_session.necessity or ""
        
        # Interpretar o comando do usuário
        command = parse_update_command(user_message, current_requirements)
        
        # Aplicar o comando determinísticamente
        updated_requirements, response_message = apply_update_command(
            command, current_requirements, necessity
        )
        
        # Atualizar a sessão ETP
        etp_session.set_requirements(updated_requirements)
        
        # Se requisitos foram confirmados, avançar estágio
        if command.get("intent") == "confirm":
            etp_session.conversation_stage = "legal_norms"
        else:
            etp_session.conversation_stage = "review_requirements"
            
        etp_session.updated_at = datetime.utcnow()
        
        # Salvar no histórico de chat se existe sessão de chat
        chat_session = ChatSession.query.filter_by(session_id=etp_session.session_id).first()
        if not chat_session:
            chat_session = ChatSession(
                session_id=etp_session.session_id,
                messages=json.dumps([]),
                context='Revisão de requisitos ETP',
                necessity=necessity,
                conversation_stage=etp_session.conversation_stage,
                requirements_json=etp_session.requirements_json,
                status='active',
                created_at=datetime.utcnow()
            )
            db.session.add(chat_session)
        else:
            # Sincronizar estado com a sessão ETP
            chat_session.necessity = necessity
            chat_session.conversation_stage = etp_session.conversation_stage
            chat_session.requirements_json = etp_session.requirements_json
            chat_session.updated_at = datetime.utcnow()
        
        # Adicionar mensagens ao histórico
        chat_session.add_message('user', user_message)
        chat_session.add_message('assistant', response_message)
        
        db.session.commit()
        
        # Incrementar contador de mensagens (demo limit)
        current_user.increment_chat_messages_sent()
        db.session.commit()
        
        # Preparar resposta estruturada
        if command.get("intent") == "confirm":
            # Requisitos confirmados - avançar para próxima fase
            response_data = {
                'success': True,
                'kind': 'requirements_confirmed',
                'necessity': necessity,
                'requirements': updated_requirements,
                'message': response_message + "\n\nAgora vamos definir as normas legais federais para sua contratação.",
                'timestamp': datetime.now().isoformat()
            }
        elif command.get("intent") == "unclear":
            # Comando não compreendido - pedir esclarecimento
            requirements_display = format_requirements_list(updated_requirements)
            response_data = {
                'success': True,
                'kind': 'requirements_review',
                'necessity': necessity,
                'requirements': updated_requirements,
                'message': f"{response_message}\n\n{requirements_display}\n\nDiga 'confirmar' para prosseguir ou indique ajustes específicos.",
                'timestamp': datetime.now().isoformat()
            }
        else:
            # Requisitos foram atualizados
            requirements_display = format_requirements_list(updated_requirements)
            response_data = {
                'success': True,
                'kind': 'requirements_update',
                'necessity': necessity,
                'requirements': updated_requirements,
                'message': f"{response_message}\n\n{requirements_display}\n\nDiga 'confirmar' para prosseguir ou faça mais ajustes.",
                'timestamp': datetime.now().isoformat()
            }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao processar revisão de requisitos: {str(e)}'
        }), 500