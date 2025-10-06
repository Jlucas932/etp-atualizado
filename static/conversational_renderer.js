// RENDERIZADOR CONVERSACIONAL - Substitui requirements_renderer.js
// Foco em interface de chat fluída, não estruturada

function escapeHtml(text) {
    if (typeof text !== 'string') {
        return String(text);
    }
    
    const htmlEscapeMap = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;',
        '/': '&#x2F;'
    };
    
    return text.replace(/[&<>"'\/]/g, function(s) {
        return htmlEscapeMap[s];
    });
}

function renderConversationalMessage(data) {
    const container = document.createElement('div');
    container.className = 'conversational-message';
    
    // FLUXO CONVERSACIONAL PROGRESSIVO
    if (data.kind === 'conversational_requirement') {
        return renderProgressiveRequirement(data);
    }
    
    // RESPOSTA A COMANDO DO USUÁRIO
    if (data.kind === 'command_response') {
        return renderCommandResponse(data);
    }
    
    // RESUMO/FINALIZAÇÃO
    if (data.kind === 'requirements_summary') {
        return renderRequirementsSummary(data);
    }
    
    // MENSAGEM PADRÃO (texto simples)
    const messageDiv = document.createElement('div');
    messageDiv.className = 'ai-message conversational';
    messageDiv.innerHTML = formatConversationalText(data.message || data.ai_response || 'Resposta não disponível');
    
    return messageDiv;
}

function renderProgressiveRequirement(data) {
    const container = document.createElement('div');
    container.className = 'progressive-requirement-container';
    
    // Mensagem principal do assistente
    const messageDiv = document.createElement('div');
    messageDiv.className = 'ai-message conversational';
    messageDiv.innerHTML = formatConversationalText(data.ai_response || data.message);
    container.appendChild(messageDiv);
    
    // Se há um requisito atual sendo discutido, destacá-lo sutilmente
    if (data.current_requirement) {
        const reqDiv = document.createElement('div');
        reqDiv.className = 'current-requirement-highlight';
        
        const reqText = data.current_requirement.text || data.current_requirement.description || 'Requisito não disponível';
        reqDiv.innerHTML = `
            <div class="requirement-text">${escapeHtml(reqText)}</div>
        `;
        
        container.appendChild(reqDiv);
    }
    
    // Indicador de progresso sutil (opcional)
    if (data.current_index !== undefined && data.total_requirements > 1) {
        const progressDiv = document.createElement('div');
        progressDiv.className = 'conversation-progress';
        progressDiv.innerHTML = `<small>Requisito ${data.current_index + 1} de ${data.total_requirements}</small>`;
        container.appendChild(progressDiv);
    }
    
    return container;
}

function renderCommandResponse(data) {
    const container = document.createElement('div');
    container.className = 'command-response-container';
    
    // Resposta do assistente
    const messageDiv = document.createElement('div');
    messageDiv.className = 'ai-message conversational';
    messageDiv.innerHTML = formatConversationalText(data.message);
    container.appendChild(messageDiv);
    
    // Se há sugestões, mostrá-las de forma sutil
    if (data.suggestions && data.suggestions.length > 0) {
        const suggestionsDiv = document.createElement('div');
        suggestionsDiv.className = 'conversation-suggestions';
        
        const suggestionsTitle = document.createElement('div');
        suggestionsTitle.className = 'suggestions-title';
        suggestionsTitle.textContent = 'Você pode:';
        suggestionsDiv.appendChild(suggestionsTitle);
        
        data.suggestions.forEach(suggestion => {
            const suggestionDiv = document.createElement('div');
            suggestionDiv.className = 'suggestion-item';
            suggestionDiv.textContent = suggestion;
            suggestionsDiv.appendChild(suggestionDiv);
        });
        
        container.appendChild(suggestionsDiv);
    }
    
    return container;
}

function renderRequirementsSummary(data) {
    const container = document.createElement('div');
    container.className = 'requirements-summary-container';
    
    // Mensagem introdutória
    const introDiv = document.createElement('div');
    introDiv.className = 'ai-message conversational';
    introDiv.innerHTML = formatConversationalText(data.message || 'Aqui está o resumo dos requisitos que definimos:');
    container.appendChild(introDiv);
    
    // Lista de requisitos aprovados (mais limpa que antes)
    if (data.requirements && data.requirements.length > 0) {
        const summaryDiv = document.createElement('div');
        summaryDiv.className = 'requirements-summary';
        
        data.requirements.forEach((req, index) => {
            const reqDiv = document.createElement('div');
            reqDiv.className = 'summary-requirement-item';
            
            const reqText = req.text || req.description || 'Requisito não disponível';
            reqDiv.innerHTML = `
                <div class="req-number">${index + 1}.</div>
                <div class="req-content">${escapeHtml(reqText)}</div>
            `;
            
            summaryDiv.appendChild(reqDiv);
        });
        
        container.appendChild(summaryDiv);
    }
    
    return container;
}

function formatConversationalText(text) {
    if (!text) return '';
    
    // Converter markdown básico para HTML de forma mais natural
    let formatted = text
        // Negrito
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        // Itálico
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        // Quebras de linha duplas para parágrafos
        .replace(/\n\n/g, '</p><p>')
        // Quebras de linha simples para <br>
        .replace(/\n/g, '<br>');
    
    // Envolver em parágrafo se não começar com tag
    if (!formatted.startsWith('<')) {
        formatted = '<p>' + formatted + '</p>';
    }
    
    return formatted;
}

// FUNÇÃO PRINCIPAL PARA SUBSTITUIR A ANTIGA
function renderAssistantMessage(data) {
    return renderConversationalMessage(data);
}

// Função para criar botões de ação rápida (opcional)
function createQuickActionButtons(actions) {
    if (!actions || actions.length === 0) return null;
    
    const buttonsContainer = document.createElement('div');
    buttonsContainer.className = 'quick-actions';
    
    actions.forEach(action => {
        const button = document.createElement('button');
        button.className = 'quick-action-btn';
        button.textContent = action.label;
        button.onclick = () => {
            // Simular que o usuário digitou o comando
            const messageInput = document.getElementById('messageInput');
            if (messageInput) {
                messageInput.value = action.command;
                // Disparar evento de envio
                const sendButton = document.querySelector('.send-button');
                if (sendButton) sendButton.click();
            }
        };
        buttonsContainer.appendChild(button);
    });
    
    return buttonsContainer;
}
