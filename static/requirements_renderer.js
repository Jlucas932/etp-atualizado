function escapeHtml(text) {
    if (typeof text !== 'string') {
        return String(text ?? '');
    }

    const htmlEscapeMap = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;',
        '/': '&#x2F;'
    };

    return text.replace(/[&<>"'/]/g, function (s) {
        return htmlEscapeMap[s];
    });
}

function renderRequirementsList(requirements, showJustificativa = false) {
    const items = Array.isArray(requirements) ? requirements.filter(Boolean) : [];
    if (items.length === 0) {
        return document.createTextNode('Nenhum requisito disponível.');
    }

    const ul = document.createElement('ul');
    ul.className = 'requirements-list';

    items.forEach((text) => {
        const li = document.createElement('li');
        li.className = 'requirement-item';

        const span = document.createElement('span');
        span.textContent = text;
        li.appendChild(span);

        if (showJustificativa === true) {
            li.dataset.showJustificativa = 'true';
        }

        ul.appendChild(li);
    });

    return ul;
}

function renderAssistantMessage(data) {
    const container = document.createElement('div');
    container.className = 'requirements-response';

    if (data && Array.isArray(data.requirements) && data.requirements.length > 0) {
        const requirementsDiv = document.createElement('div');
        requirementsDiv.className = 'requirements-section';

        const title = document.createElement('h4');
        title.textContent = 'Requisitos:';
        requirementsDiv.appendChild(title);

        const list = renderRequirementsList(data.requirements, Boolean(data.showJustificativa));
        requirementsDiv.appendChild(list);

        container.appendChild(requirementsDiv);
    }

    if (data && data.message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'ai-message';
        messageDiv.textContent = data.message;
        container.appendChild(messageDiv);
    }

    if (container.childNodes.length === 0) {
        const fallback = document.createElement('div');
        fallback.className = 'ai-message';
        fallback.textContent = data && data.message ? data.message : 'Resposta não disponível';
        return fallback;
    }

    return container;
}

if (typeof module !== 'undefined') {
    module.exports = {
        escapeHtml,
        renderRequirementsList,
        renderAssistantMessage,
    };
}
