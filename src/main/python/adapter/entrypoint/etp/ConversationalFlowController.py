"""
Controlador de Fluxo Conversacional Progressivo
Gerencia o diálogo natural entre usuário e sistema para aprovação de requisitos
"""

from flask import Blueprint, request, jsonify, session as flask_session
from datetime import datetime
import json
import logging

from domain.usecase.etp.conversational_interpreter import parse_conversational_command, generate_conversational_response
from domain.usecase.etp.utils_parser import parse_requirements_response_safely
from domain.interfaces.dataprovider.DatabaseConfig import db
from domain.dto.EtpDto import EtpSession
from rag.retrieval import search_requirements
from domain.usecase.etp.etp_generator import EtpGenerator

# Blueprint para fluxo conversacional
conversational_flow_bp = Blueprint('conversational_flow', __name__, url_prefix='/api/conversational')

logger = logging.getLogger(__name__)
etp_generator = EtpGenerator()


@conversational_flow_bp.route('/process-response', methods=['POST'])
def process_conversational_response():
    """
    Processa resposta do usuário no fluxo conversacional progressivo
    """
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id')
        
        if not user_message:
            return jsonify({'error': 'Mensagem é obrigatória'}), 400
        
        # Buscar sessão
        session = EtpSession.query.filter_by(session_id=session_id).first()
        if not session:
            return jsonify({'error': 'Sessão não encontrada'}), 404
        
        # Obter contexto atual
        current_requirements = session.get_requirements() or []
        current_index = getattr(session, 'current_requirement_index', 0)
        current_requirement = current_requirements[current_index] if current_index < len(current_requirements) else None
        
        # Interpretar comando do usuário
        intent_result = parse_conversational_command(
            user_message, 
            current_requirement=current_requirement,
            context={'session': session, 'requirements': current_requirements}
        )
        
        logger.info(f"[CONVERSATIONAL] Intent: {intent_result.get('intent')}, Action: {intent_result.get('action')}")
        
        # Processar ação baseada na intenção
        response_data = process_intent_action(intent_result, session, current_requirements, current_index)
        
        # Atualizar sessão
        session.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Erro no fluxo conversacional: {str(e)}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500


def process_intent_action(intent_result, session, current_requirements, current_index):
    """Processa a ação baseada na intenção identificada"""
    
    intent = intent_result.get('intent')
    action = intent_result.get('action')
    
    if action == 'suggest_alternative':
        return handle_suggest_alternative(session, current_requirements, current_index)
    
    elif action == 'move_to_next':
        return handle_move_to_next(session, current_requirements, current_index)
    
    elif action == 'apply_modification':
        return handle_apply_modification(intent_result, session, current_requirements, current_index)
    
    elif action == 'display_summary':
        return handle_display_summary(session, current_requirements)
    
    elif action == 'create_new_requirement':
        return handle_create_new_requirement(intent_result, session, current_requirements)
    
    elif action == 'finalize_requirements':
        return handle_finalize_requirements(session, current_requirements)
    
    else:  # ask_clarification
        return handle_ask_clarification(intent_result, session, current_requirements, current_index)


def handle_suggest_alternative(session, current_requirements, current_index):
    """Sugere uma alternativa para o requisito atual"""
    
    if current_index >= len(current_requirements):
        return {
            'kind': 'command_response',
            'message': 'Não há requisito atual para modificar. Vamos continuar?',
            'conversation_stage': 'clarification'
        }
    
    current_req = current_requirements[current_index]
    necessity = session.necessity
    
    # Usar RAG para buscar alternativas
    try:
        rag_results = search_requirements("generic", necessity, k=3)
        
        # Gerar alternativa usando IA
        alternative_prompt = f"""
        O usuário não gostou deste requisito: "{current_req.get('text', '')}"
        
        Necessidade: {necessity}
        
        Baseado nos exemplos similares:
        {json.dumps(rag_results[:2], indent=2)}
        
        Sugira UMA alternativa diferente e melhor para este requisito.
        Responda apenas com o texto do novo requisito, sem numeração.
        """
        
        response = etp_generator.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Você é um consultor especialista em licitações que sugere requisitos alternativos."},
                {"role": "user", "content": alternative_prompt}
            ],
            max_tokens=200,
            temperature=0.7
        )
        
        alternative_text = response.choices[0].message.content.strip()
        
        # Atualizar requisito atual
        current_requirements[current_index]['text'] = alternative_text
        session.set_requirements(current_requirements)
        
        return {
            'kind': 'conversational_requirement',
            'message': f'Entendi! Que tal esta alternativa:\n\n**{alternative_text}**\n\nFica melhor assim?',
            'current_requirement': current_requirements[current_index],
            'current_index': current_index,
            'total_requirements': len(current_requirements),
            'conversation_stage': 'review_requirement_progressive'
        }
        
    except Exception as e:
        logger.error(f"Erro ao gerar alternativa: {str(e)}")
        return {
            'kind': 'command_response',
            'message': 'Desculpe, tive dificuldade para gerar uma alternativa. Pode me dizer especificamente o que gostaria de mudar?',
            'conversation_stage': 'clarification'
        }


def handle_move_to_next(session, current_requirements, current_index):
    """Move para o próximo requisito"""
    
    next_index = current_index + 1
    
    if next_index >= len(current_requirements):
        # Chegou ao fim - mostrar resumo
        return handle_display_summary(session, current_requirements, final=True)
    
    # Atualizar índice na sessão
    session.current_requirement_index = next_index
    next_req = current_requirements[next_index]
    
    return {
        'kind': 'conversational_requirement',
        'message': f'Perfeito! Agora vamos para o próximo requisito:\n\n**{next_req.get("text", "")}**\n\nO que acha deste?',
        'current_requirement': next_req,
        'current_index': next_index,
        'total_requirements': len(current_requirements),
        'conversation_stage': 'review_requirement_progressive'
    }


def handle_apply_modification(intent_result, session, current_requirements, current_index):
    """Aplica modificação solicitada pelo usuário"""
    
    if current_index >= len(current_requirements):
        return {
            'kind': 'command_response',
            'message': 'Não há requisito atual para modificar.',
            'conversation_stage': 'clarification'
        }
    
    modification_request = intent_result.get('modification_request', '')
    current_req = current_requirements[current_index]
    
    # Usar IA para aplicar a modificação
    try:
        modify_prompt = f"""
        Requisito atual: "{current_req.get('text', '')}"
        
        Modificação solicitada: {modification_request}
        
        Aplique a modificação solicitada e retorne apenas o texto do requisito modificado.
        """
        
        response = etp_generator.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Você modifica requisitos conforme solicitado pelo usuário."},
                {"role": "user", "content": modify_prompt}
            ],
            max_tokens=200,
            temperature=0.3
        )
        
        modified_text = response.choices[0].message.content.strip()
        
        # Atualizar requisito
        current_requirements[current_index]['text'] = modified_text
        session.set_requirements(current_requirements)
        
        return {
            'kind': 'conversational_requirement',
            'message': f'Ajustei conforme solicitado:\n\n**{modified_text}**\n\nFicou melhor agora?',
            'current_requirement': current_requirements[current_index],
            'current_index': current_index,
            'total_requirements': len(current_requirements),
            'conversation_stage': 'review_requirement_progressive'
        }
        
    except Exception as e:
        logger.error(f"Erro ao modificar requisito: {str(e)}")
        return {
            'kind': 'command_response',
            'message': 'Desculpe, tive dificuldade para fazer essa modificação. Pode ser mais específico sobre o que quer mudar?',
            'conversation_stage': 'clarification'
        }


def handle_display_summary(session, current_requirements, final=False):
    """Mostra resumo dos requisitos"""
    
    if not current_requirements:
        return {
            'kind': 'command_response',
            'message': 'Ainda não temos requisitos definidos.',
            'conversation_stage': 'clarification'
        }
    
    message = "Aqui estão os requisitos que definimos até agora:" if not final else "Excelente! Aqui está o resumo final dos requisitos:"
    
    return {
        'kind': 'requirements_summary',
        'message': message,
        'requirements': current_requirements,
        'conversation_stage': 'summary' if not final else 'finalization'
    }


def handle_create_new_requirement(intent_result, session, current_requirements):
    """Cria novo requisito baseado na solicitação do usuário"""
    
    new_req_text = intent_result.get('new_requirement', '')
    
    if not new_req_text:
        return {
            'kind': 'command_response',
            'message': 'Não consegui identificar o novo requisito. Pode me dizer especificamente o que quer adicionar?',
            'conversation_stage': 'clarification'
        }
    
    # Criar novo requisito
    new_req = {
        'id': f'R{len(current_requirements) + 1}',
        'text': new_req_text,
        'description': new_req_text
    }
    
    current_requirements.append(new_req)
    session.set_requirements(current_requirements)
    
    return {
        'kind': 'conversational_requirement',
        'message': f'Adicionei o novo requisito:\n\n**{new_req_text}**\n\nEste requisito está adequado?',
        'current_requirement': new_req,
        'current_index': len(current_requirements) - 1,
        'total_requirements': len(current_requirements),
        'conversation_stage': 'review_requirement_progressive'
    }


def handle_finalize_requirements(session, current_requirements):
    """Finaliza os requisitos e prepara para geração do documento"""
    
    if not current_requirements:
        return {
            'kind': 'command_response',
            'message': 'Não temos requisitos para finalizar. Vamos começar definindo alguns?',
            'conversation_stage': 'clarification'
        }
    
    # Marcar sessão como finalizada
    session.conversation_stage = 'finalized'
    
    return {
        'kind': 'requirements_summary',
        'message': 'Perfeito! Finalizamos os requisitos. Agora posso gerar o documento completo para você.',
        'requirements': current_requirements,
        'conversation_stage': 'finalized',
        'actions': [
            {'label': 'Gerar Documento', 'command': 'gerar documento'},
            {'label': 'Revisar Requisitos', 'command': 'revisar requisitos'}
        ]
    }


def handle_ask_clarification(intent_result, session, current_requirements, current_index):
    """Pede esclarecimento quando não entende o comando"""
    
    message = intent_result.get('message', 'Não entendi bem. Como posso ajudar?')
    suggestions = intent_result.get('suggestions', [])
    
    return {
        'kind': 'command_response',
        'message': message,
        'suggestions': suggestions,
        'conversation_stage': 'clarification'
    }
