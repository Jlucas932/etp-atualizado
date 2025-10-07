import os
import json
import uuid
import logging
from datetime import datetime
from io import BytesIO
from flask import Blueprint, request, jsonify, send_file, session
from flask_cors import cross_origin

from domain.interfaces.dataprovider.DatabaseConfig import db
from domain.dto.EtpDto import EtpSession
from domain.dto.UserDto import User

etp_bp = Blueprint('etp', __name__)

logger = logging.getLogger(__name__)

def check_authentication_and_limits(limit_type='document'):
    """Verifica se o usuário está autenticado e dentro dos limites da demo"""
    if 'user_id' not in session:
        return jsonify({
            'success': False,
            'error': 'Usuário não autenticado'
        }), 401
    
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({
            'success': False,
            'error': 'Usuário não encontrado'
        }), 404
    
    if limit_type == 'document' and not user.can_generate_document():
        return jsonify({
            'success': False,
            'error': 'Você atingiu o limite de 5 documentos na versão demo.',
            'limit_reached': True
        }), 403
    
    if limit_type == 'chat' and not user.can_send_chat_message():
        return jsonify({
            'success': False,
            'error': 'Você atingiu o limite de 5 perguntas na versão demo.',
            'limit_reached': True
        }), 403
    
    return user

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
        "question": "Possui demonstrativo de previsão no PCA?",
        "type": "boolean",
        "required": True,
        "section": "OBJETO DO ESTUDO E ESPECIFICAÇÕES GERAIS"
    },
    {
        "id": 3,
        "question": "Quais normas legais pretende utilizar?",
        "type": "text",
        "required": True,
        "section": "DESCRIÇÃO DOS REQUISITOS DA CONTRATAÇÃO"
    },
    {
        "id": 4,
        "question": "Qual o quantitativo e valor estimado?",
        "type": "text",
        "required": True,
        "section": "ESTIMATIVA DAS QUANTIDADES E VALORES"
    },
    {
        "id": 5,
        "question": "Haverá parcelamento da contratação?",
        "type": "boolean",
        "required": True,
        "section": "JUSTIFICATIVA PARA O PARCELAMENTO"
    }
]

@etp_bp.route('/health', methods=['GET'])
@cross_origin()
def health_check():
    """Verificação de saúde da API ETP legada"""
    try:
        return jsonify({
            'status': 'healthy',
            'version': '2.0.0-legacy',
            'openai_configured': bool(os.getenv('OPENAI_API_KEY')),
            'note': 'Esta é a API legada. Use /api/etp-dynamic para funcionalidades avançadas',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@etp_bp.route('/questions', methods=['GET'])
@cross_origin()
def get_questions():
    """Retorna as perguntas do ETP"""
    return jsonify({
        'success': True,
        'questions': ETP_QUESTIONS,
        'total': len(ETP_QUESTIONS)
    })

# NOVA ROTA ADICIONADA - Esta é a correção principal
@etp_bp.route('/generate', methods=['POST'])
@cross_origin()
def generate_session():
    """Inicia uma nova sessão de ETP (compatibilidade com frontend antigo)"""
    try:
        # Verificar autenticação e limites
        user_check = check_authentication_and_limits('document')
        if isinstance(user_check, tuple):  # É uma resposta de erro
            return user_check
        
        user = user_check  # É um objeto User válido
        
        # O frontend pode não enviar JSON, então usar get_json() com silent=True
        try:
            data = request.get_json(silent=True) or {}
        except:
            data = {}

        # Criar nova sessão
        etp_session = EtpSession(
            user_id=user.id,
            session_id=str(uuid.uuid4()),
            status='active',
            answers=json.dumps({}),
            created_at=datetime.utcnow()
        )

        db.session.add(etp_session)
        db.session.commit()

        return jsonify({
            'success': True,
            'session_id': etp_session.session_id,
            'questions': ETP_QUESTIONS,
            'message': 'Sessão iniciada com sucesso',
            'note': 'Para melhor qualidade, considere usar /api/etp-dynamic'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@etp_bp.route('/session/start', methods=['POST'])
@cross_origin()
def start_session():
    """Inicia uma nova sessão de ETP (versão legada)"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id', 1)

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
            'message': 'Sessão iniciada com sucesso (versão legada)',
            'recommendation': 'Para melhor qualidade, use /api/etp-dynamic'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@etp_bp.route('/session/<session_id>/answer', methods=['POST'])
@cross_origin()
def save_answer(session_id):
    """Salva resposta de uma pergunta"""
    try:
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

@etp_bp.route('/session/<session_id>/generate', methods=['POST'])
@cross_origin()
def generate_etp_legacy(session_id):
    """Gera ETP usando método legado (redirecionamento interno para API dinâmica)"""
    try:
        from domain.services.etp_dynamic import etp_generator
        
        if not etp_generator:
            return jsonify({
                'success': False,
                'error': 'Gerador ETP não configurado. Verifique a chave da OpenAI.'
            }), 500
        
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
            'message': 'ETP gerado com sucesso',
            'generation_method': 'dynamic_prompts_legacy_compat'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Adicionar endpoints ausentes que o frontend está chamando
@etp_bp.route('/generate-preview', methods=['POST'])
@cross_origin()
def generate_etp_preview():
    """Gera preview do ETP (compatibilidade com frontend)"""
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({'error': 'session_id é obrigatório'}), 400
            
        from domain.services.etp_dynamic import etp_generator
        
        if not etp_generator:
            return jsonify({
                'success': False,
                'error': 'Gerador ETP não configurado. Verifique a chave da OpenAI.'
            }), 500
        
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
        
        # Salvar preview gerado na sessão
        session.generated_etp = preview_content
        session.status = 'preview_generated'
        session.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'preview_content': preview_content,
            'message': 'Preview gerado com sucesso',
            'generation_method': 'dynamic_prompts_legacy_compat',
            'is_preview': True
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@etp_bp.route('/generate-final-document', methods=['POST'])
@cross_origin()
def generate_final_document():
    """Gera documento final do ETP (compatibilidade com frontend)"""
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({'error': 'session_id é obrigatório'}), 400
            
        from domain.services.etp_dynamic import etp_generator
        
        if not etp_generator:
            return jsonify({
                'success': False,
                'error': 'Gerador ETP não configurado. Verifique a chave da OpenAI.'
            }), 500
        
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
        
        # Gerar ETP final usando sistema dinâmico
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
            'message': 'ETP final gerado com sucesso',
            'generation_method': 'dynamic_prompts_legacy_compat',
            'document_ready': True
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@etp_bp.route('/generate-final', methods=['POST'])
@cross_origin()
def generate_final():
    """Endpoint adicional para geração final (compatibilidade com frontend) - OTIMIZADO"""
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({'error': 'session_id é obrigatório'}), 400
            
        # Buscar sessão
        session = EtpSession.query.filter_by(session_id=session_id).first()
        if not session:
            return jsonify({'error': 'Sessão não encontrada'}), 404
        
        # Se já existe ETP gerado e status é completado, não regerar (CACHE)
        if session.generated_etp and session.status == 'completed':
            return jsonify({
                'success': True,
                'etp_content': session.generated_etp,
                'message': 'Documento final já estava pronto (cache)',
                'document_ready': True,
                'cached': True
            })
            
        # Caso contrário, chamar generate_final_document()
        return generate_final_document()
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@etp_bp.route('/upload-document', methods=['POST'])
@cross_origin()
def upload_document():
    """Upload de documento para análise (funcionalidade básica)"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400
        
        file = request.files['file']
        session_id = request.form.get('session_id')
        
        if file.filename == '':
            return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
            
        if not session_id:
            return jsonify({'error': 'session_id é obrigatório'}), 400
        
        # Verificar se a sessão existe
        session = EtpSession.query.filter_by(session_id=session_id).first()
        if not session:
            return jsonify({'error': 'Sessão não encontrada'}), 404
        
        # Por ora, apenas confirmamos o upload - funcionalidade de análise pode ser implementada depois
        return jsonify({
            'success': True,
            'message': 'Documento recebido. Por favor, continue respondendo as perguntas manualmente.',
            'filename': file.filename,
            'note': 'Análise automática de documentos será implementada em breve.'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@etp_bp.route('/validate-answers', methods=['POST'])
@cross_origin()
def validate_answers():
    """Valida as respostas do ETP (compatibilidade com frontend)"""
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id')
        answers = data.get('answers', {})
        
        if not session_id:
            return jsonify({'error': 'session_id é obrigatório'}), 400
            
        # Buscar sessão
        session = EtpSession.query.filter_by(session_id=session_id).first()
        if not session:
            return jsonify({'error': 'Sessão não encontrada'}), 404
        
        # Salvar as respostas na sessão
        session.set_answers(answers)
        session.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Respostas validadas com sucesso',
            'answers_count': len(answers)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@etp_bp.route('/get-preview', methods=['POST'])
@cross_origin()
def get_preview():
    """Retorna o preview do ETP (compatibilidade com frontend) - OTIMIZADO"""
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({'error': 'session_id é obrigatório'}), 400
            
        # Buscar sessão
        session = EtpSession.query.filter_by(session_id=session_id).first()
        if not session:
            return jsonify({'error': 'Sessão não encontrada'}), 404
        
        # SEMPRE retornar preview existente se disponível (evita chamadas desnecessárias à API)
        if session.generated_etp:
            return jsonify({
                'success': True,
                'preview': session.generated_etp,
                'message': 'Preview recuperado do cache (sem gasto de API)',
                'cached': True
            })
        
        # Se não existe preview, retornar erro - não gerar automaticamente
        return jsonify({
            'success': False,
            'error': 'Preview não encontrado. Execute "Gerar Preview" primeiro.',
            'requires_generation': True
        }), 404
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@etp_bp.route('/session/<session_id>', methods=['GET'])
@cross_origin()
def get_session(session_id):
    """Retorna dados da sessão"""
    try:
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

@etp_bp.route('/approve-preview', methods=['POST'])
@cross_origin()
def approve_preview():
    """Aprova o preview do ETP (compatibilidade com frontend)"""
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({'error': 'session_id é obrigatório'}), 400
            
        # Buscar sessão
        session = EtpSession.query.filter_by(session_id=session_id).first()
        if not session:
            return jsonify({'error': 'Sessão não encontrada'}), 404
        
        # Marcar preview como aprovado
        session.status = 'preview_approved'
        session.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Preview aprovado com sucesso',
            'session_id': session_id,
            'status': session.status
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@etp_bp.route('/download/<session_id>', methods=['GET'])
@cross_origin()
def download_document(session_id):
    """Download do documento Word gerado - OTIMIZADO com verificações"""
    try:
        # Verificar autenticação
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
        
        # Buscar sessão ETP
        etp_session = EtpSession.query.filter_by(session_id=session_id).first()
        if not etp_session:
            return jsonify({'error': 'Sessão não encontrada'}), 404
        
        # Verificar se é do usuário atual
        if etp_session.user_id != current_user.id:
            return jsonify({
                'success': False,
                'error': 'Acesso não autorizado'
            }), 403
        
        if not etp_session.generated_etp:
            return jsonify({'error': 'ETP não foi gerado ainda. Execute "Gerar Documento Final" primeiro.'}), 400
        
        # Debug: verificar conteúdo do ETP
        logger.debug(
            "[DEBUG] ETP Content length: %s",
            len(etp_session.generated_etp) if etp_session.generated_etp else 0
        )
        logger.debug(
            "[DEBUG] ETP Content preview: %s...",
            etp_session.generated_etp[:200] if etp_session.generated_etp else 'None'
        )
        
        # Verificar se o status permite download
        if etp_session.status not in ['completed', 'preview_approved', 'preview_generated']:
            return jsonify({'error': 'Documento ainda não está pronto para download. Status: ' + str(etp_session.status)}), 400
        
        # Importar dependências necessárias
        from domain.usecase.utils.word_formatter import ProfessionalWordFormatter
        
        # Tentar criar documento Word com tratamento de erro robusto
        try:
            word_formatter = ProfessionalWordFormatter()
            doc_path = word_formatter.create_professional_document(
                content=etp_session.generated_etp,
                session_data={
                    'session_id': session_id,
                    'user_id': etp_session.user_id,
                    'created_at': etp_session.created_at.isoformat() if etp_session.created_at else None
                }
            )
            
            # Verificar se o arquivo foi criado
            if not os.path.exists(doc_path):
                raise ValueError("Arquivo Word não foi criado")
            
            file_size = os.path.getsize(doc_path)
            if file_size == 0:
                raise ValueError("Arquivo Word está vazio")
            
            logger.debug("[DEBUG] Created Word file: %s, size: %s bytes", doc_path, file_size)
            
            # Ler o arquivo criado para buffer
            with open(doc_path, 'rb') as f:
                doc_buffer = BytesIO(f.read())
            
            # Limpar arquivo temporário
            if os.path.exists(doc_path):
                os.remove(doc_path)
            
            # Verificar se o buffer foi criado corretamente
            doc_buffer.seek(0, 2)  # Move para o final para verificar tamanho
            buffer_size = doc_buffer.tell()
            doc_buffer.seek(0)     # Volta para o início para envio
            if not doc_buffer or buffer_size == 0:
                raise ValueError("Documento Word vazio ou não criado corretamente")
                
        except ImportError as ie:
            return jsonify({
                'success': False,
                'error': f'Erro de dependência para criação do Word: {str(ie)}'
            }), 500
        except Exception as we:
            return jsonify({
                'success': False,
                'error': f'Erro ao criar documento Word: {str(we)}'
            }), 500
        
        # Incrementar contador de documentos gerados (demo limit)
        current_user.increment_documents_generated()
        db.session.commit()
        
        # Retornar arquivo para download
        return send_file(
            doc_buffer,
            as_attachment=True,
            download_name=f'ETP_{session_id}.docx',
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao gerar documento: {str(e)}'
        }), 500