// PASSO 1B: Renderização limpa de requisitos (sem JSON cru)

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

function renderRequirementsList(items) {
    if (!Array.isArray(items) || items.length === 0) {
        return document.createTextNode('Nenhum requisito disponível.');
    }
    
    const ul = document.createElement('ul');
    ul.className = 'requirements-list';
    
    items.forEach((item) => {
        const li = document.createElement('li');
        li.className = 'requirement-item';
        
        const id = item.id || 'R?';
        const text = item.text || item.requirement || 'Texto não disponível';
        const justification = item.justification || 'Justificativa não disponível';
        
        li.innerHTML = `
            <strong>${escapeHtml(id)}</strong> — ${escapeHtml(text)}
            <br><em>Justificativa:</em> ${escapeHtml(justification)}
        `;
        
        ul.appendChild(li);
    });
    
    return ul;
}

function renderAssistantMessage(data) {
    // PASSO 1B: Renderização baseada no campo 'kind'
    if (data.kind && data.kind.startsWith('requirements_')) {
        const container = document.createElement('div');
        container.className = 'requirements-response';
        
        if (data.necessity) {
            const necessityDiv = document.createElement('div');
            necessityDiv.className = 'necessity-section';
            necessityDiv.innerHTML = `<strong>Necessidade:</strong> ${escapeHtml(data.necessity)}`;
            container.appendChild(necessityDiv);
        }
        
        if (data.requirements && data.requirements.length > 0) {
            const requirementsDiv = document.createElement('div');
            requirementsDiv.className = 'requirements-section';
            
            const title = document.createElement('h4');
            title.textContent = data.kind === 'requirements_suggestion' ? 'Requisitos Sugeridos:' : 'Requisitos Atualizados:';
            requirementsDiv.appendChild(title);
            
            const requirementsList = renderRequirementsList(data.requirements);
            requirementsDiv.appendChild(requirementsList);
            
            container.appendChild(requirementsDiv);
        }
        
        if (data.message) {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'ai-message';
            messageDiv.textContent = data.message;
            container.appendChild(messageDiv);
        }
        
        return container;
    }
    
    // Renderização padrão para mensagens de texto
    const messageDiv = document.createElement('div');
    messageDiv.className = 'ai-message';
    messageDiv.textContent = data.message || data.ai_response || 'Resposta não disponível';
    return messageDiv;
}
