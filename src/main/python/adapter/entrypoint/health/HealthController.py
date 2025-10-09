import os
from datetime import datetime
from flask import Blueprint, jsonify
from flask_cors import cross_origin

health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
@cross_origin()
def health_check():
    """Endpoint de verificação de saúde da aplicação"""
    try:
        # Verificar configurações essenciais
        openai_configured = bool(os.getenv('OPENAI_API_KEY'))
        
        return jsonify({
            'status': 'healthy',
            'service': 'ETP Sistema Padronizado',
            'version': '3.0.0',
            'architecture': 'Clean Architecture',
            'openai_configured': openai_configured,
            'database_type': 'PostgreSQL',
            'features': {
                'dynamic_prompts': True,
                'document_analysis': True,
                'knowledge_base': True,
                'chat_support': True,
                'word_export': True
            },
            'timestamp': datetime.now().isoformat(),
            'uptime': 'Sistema iniciado com sucesso'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@health_bp.route('/version', methods=['GET'])
@cross_origin()
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

