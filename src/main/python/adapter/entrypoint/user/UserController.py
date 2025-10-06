from flask import Blueprint, request, jsonify, session
from flask_cors import cross_origin
from domain.usecase.user.UserAuthenticationUseCase import UserAuthenticationUseCase
from adapter.gateway.UserRepository import UserRepository
from functools import wraps

user_bp = Blueprint('user', __name__)

def login_required(f):
    """Decorator para verificar se o usuário está autenticado"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({
                'success': False,
                'error': 'Usuário não autenticado'
            }), 401
        return f(*args, **kwargs)
    return decorated_function

@user_bp.route('/auth/login', methods=['POST'])
@cross_origin()
def login():
    """Autentica o usuário"""
    try:
        data = request.get_json()
        
        if not data or not data.get('username') or not data.get('password'):
            return jsonify({
                'success': False,
                'error': 'Username e senha são obrigatórios'
            }), 400
        
        # Initialize use case with repository
        user_repository = UserRepository()
        auth_use_case = UserAuthenticationUseCase(user_repository)
        
        # Authenticate user
        user = auth_use_case.authenticate(data['username'], data['password'])
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'Username ou senha incorretos'
            }), 401
        
        # Criar sessão
        session['user_id'] = user.id
        session['username'] = user.username
        
        return jsonify({
            'success': True,
            'message': 'Login realizado com sucesso',
            'user': user.to_dict()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@user_bp.route('/auth/logout', methods=['POST'])
@cross_origin()
def logout():
    """Desconecta o usuário"""
    try:
        session.clear()
        return jsonify({
            'success': True,
            'message': 'Logout realizado com sucesso'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@user_bp.route('/auth/current', methods=['GET'])
@cross_origin()
def current_user():
    """Retorna o usuário atual da sessão"""
    try:
        if 'user_id' not in session:
            return jsonify({
                'success': False,
                'authenticated': False
            }), 401
        
        # Initialize use case with repository
        user_repository = UserRepository()
        auth_use_case = UserAuthenticationUseCase(user_repository)
        
        user = auth_use_case.get_user_by_id(session['user_id'])
        if not user:
            session.clear()
            return jsonify({
                'success': False,
                'authenticated': False,
                'error': 'Usuário não encontrado'
            }), 404
        
        return jsonify({
            'success': True,
            'authenticated': True,
            'user': user.to_dict()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@user_bp.route('/users', methods=['GET'])
@cross_origin()
def get_users():
    """Lista todos os usuários"""
    try:
        users = User.query.all()
        return jsonify({
            'success': True,
            'users': [user.to_dict() for user in users],
            'total': len(users)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@user_bp.route('/users', methods=['POST'])
@cross_origin()
def create_user():
    """Criação de usuário desabilitada na versão demo"""
    return jsonify({
        'success': False,
        'error': 'Criação de conta não disponível na versão demo. Use um dos usuários pré-cadastrados.'
    }), 403

@user_bp.route('/users/<int:user_id>', methods=['GET'])
@cross_origin()
def get_user(user_id):
    """Busca um usuário específico"""
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'Usuário não encontrado'
            }), 404
        
        return jsonify({
            'success': True,
            'user': user.to_dict()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@user_bp.route('/users/<int:user_id>', methods=['PUT'])
@cross_origin()
def update_user(user_id):
    """Atualiza um usuário"""
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'Usuário não encontrado'
            }), 404
        
        data = request.get_json()
        
        if data.get('username'):
            # Verificar se username já existe em outro usuário
            existing = User.query.filter(
                User.username == data['username'],
                User.id != user_id
            ).first()
            
            if existing:
                return jsonify({
                    'success': False,
                    'error': 'Username já existe'
                }), 400
            
            user.username = data['username']
        
        if data.get('email'):
            # Verificar se email já existe em outro usuário
            existing = User.query.filter(
                User.email == data['email'],
                User.id != user_id
            ).first()
            
            if existing:
                return jsonify({
                    'success': False,
                    'error': 'Email já existe'
                }), 400
            
            user.email = data['email']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'user': user.to_dict(),
            'message': 'Usuário atualizado com sucesso'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@user_bp.route('/users/<int:user_id>', methods=['DELETE'])
@cross_origin()
def delete_user(user_id):
    """Remove um usuário"""
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'Usuário não encontrado'
            }), 404
        
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Usuário removido com sucesso'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

