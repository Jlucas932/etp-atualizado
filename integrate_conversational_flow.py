#!/usr/bin/env python3
"""
Script para integrar as melhorias conversacionais no projeto autodoc-ia
Aplica as correções necessárias para restaurar o fluxo consultivo
"""

import os
import shutil
import re

def integrate_conversational_improvements():
    """Integra todas as melhorias conversacionais"""
    
    print("🔄 Integrando melhorias conversacionais...")
    
    # 1. Atualizar index.html para usar novos scripts
    update_index_html()
    
    # 2. Atualizar script.js para usar novo renderer
    update_script_js()
    
    # 3. Registrar novo blueprint no applicationApi.py
    register_conversational_blueprint()
    
    # 4. Adicionar campo current_requirement_index ao modelo EtpSession
    update_etp_session_model()
    
    print("✅ Integração concluída!")


def update_index_html():
    """Atualiza index.html para incluir novos estilos e scripts"""
    
    index_path = "static/index.html"
    
    if not os.path.exists(index_path):
        print(f"❌ Arquivo {index_path} não encontrado")
        return
    
    with open(index_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Adicionar CSS conversacional
    if 'conversational_styles.css' not in content:
        css_link = '<link rel="stylesheet" href="conversational_styles.css">'
        content = content.replace('</head>', f'    {css_link}\n</head>')
    
    # Adicionar script conversacional
    if 'conversational_renderer.js' not in content:
        script_tag = '<script src="conversational_renderer.js"></script>'
        content = content.replace('</body>', f'    {script_tag}\n</body>')
    
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ index.html atualizado")


def update_script_js():
    """Atualiza script.js para usar renderização conversacional"""
    
    script_path = "static/script.js"
    
    if not os.path.exists(script_path):
        print(f"❌ Arquivo {script_path} não encontrado")
        return
    
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Substituir chamadas para renderAssistantMessage
    old_pattern = r'renderAssistantMessage\(([^)]+)\)'
    new_pattern = r'renderConversationalMessage(\1)'
    
    content = re.sub(old_pattern, new_pattern, content)
    
    # Adicionar endpoint para fluxo conversacional
    if '/api/conversational/process-response' not in content:
        # Encontrar função de envio de mensagem e adicionar lógica conversacional
        send_function_pattern = r'(function sendMessage\(\) \{[^}]+\})'
        
        if re.search(send_function_pattern, content):
            conversational_logic = '''
// Lógica conversacional adicionada
function handleConversationalResponse(data) {
    if (data.conversation_stage === 'review_requirement_progressive') {
        // Usuário está revisando requisito progressivamente
        return fetch('/api/conversational/process-response', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: messageInput.value,
                session_id: currentSessionId,
                conversation_history: conversationHistory
            })
        });
    }
    
    // Fluxo normal
    return fetch('/api/etp-dynamic/conversation', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            message: messageInput.value,
            session_id: currentSessionId,
            conversation_history: conversationHistory
        })
    });
}
'''
            content = content.replace('function sendMessage() {', conversational_logic + '\nfunction sendMessage() {')
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ script.js atualizado")


def register_conversational_blueprint():
    """Registra o blueprint conversacional no applicationApi.py"""
    
    app_path = "src/main/python/applicationApi.py"
    
    if not os.path.exists(app_path):
        print(f"❌ Arquivo {app_path} não encontrado")
        return
    
    with open(app_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Adicionar import do blueprint conversacional
    if 'ConversationalFlowController' not in content:
        import_line = 'from adapter.entrypoint.etp.ConversationalFlowController import conversational_flow_bp'
        
        # Encontrar outros imports de blueprints
        blueprint_import_pattern = r'(from adapter\.entrypoint\.etp\.[^import]+ import [^_]+_bp)'
        match = re.search(blueprint_import_pattern, content)
        
        if match:
            content = content.replace(match.group(0), match.group(0) + '\n' + import_line)
        else:
            # Adicionar após outros imports
            content = content.replace('from flask import Flask', f'from flask import Flask\n{import_line}')
    
    # Registrar blueprint
    if 'app.register_blueprint(conversational_flow_bp)' not in content:
        register_line = 'app.register_blueprint(conversational_flow_bp)'
        
        # Encontrar outros registros de blueprints
        blueprint_register_pattern = r'(app\.register_blueprint\([^_]+_bp\))'
        match = re.search(blueprint_register_pattern, content)
        
        if match:
            content = content.replace(match.group(0), match.group(0) + '\n' + register_line)
        else:
            # Adicionar antes do if __name__
            content = content.replace('if __name__ == "__main__":', f'{register_line}\n\nif __name__ == "__main__":')
    
    with open(app_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ applicationApi.py atualizado")


def update_etp_session_model():
    """Adiciona campo current_requirement_index ao modelo EtpSession"""
    
    model_path = "src/main/python/domain/entity/etp/EtpSession.py"
    
    if not os.path.exists(model_path):
        print(f"❌ Arquivo {model_path} não encontrado")
        return
    
    with open(model_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Adicionar campo current_requirement_index se não existir
    if 'current_requirement_index' not in content:
        # Encontrar definição da classe
        class_pattern = r'(class EtpSession\([^:]+\):.*?)(    def __init__)'
        match = re.search(class_pattern, content, re.DOTALL)
        
        if match:
            new_field = '    current_requirement_index = db.Column(db.Integer, default=0)\n'
            content = content.replace(match.group(2), new_field + match.group(2))
    
    with open(model_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ EtpSession.py atualizado")


if __name__ == "__main__":
    integrate_conversational_improvements()
