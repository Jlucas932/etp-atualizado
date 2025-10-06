from datetime import datetime
from flask import Blueprint, jsonify

health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health_check():
    """Endpoint de verificação de saúde da aplicação"""
    return jsonify({'status': 'ok'}), 200

@health_bp.route('/version', methods=['GET'])
def get_version():
    """Retorna informações de versão"""
    return jsonify({
        'version': '3.0.0',
        'architecture': 'Clean Architecture',
        'features': [
            'Geração dinâmica de prompts',
            'Análise de documentos PDF',
            'Base de conhecimento estruturada',
            'Sistema de chat integrado',
            'Exportação para Word',
            'Validação de completude'
        ],
        'improvements': [
            'Prompts baseados em documentos existentes',
            'Estrutura padronizada da empresa',
            'Remoção de prompts fixos',
            'Arquitetura limpa e escalável'
        ]
    })

