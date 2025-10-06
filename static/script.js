// === INICIALIZAÇÃO DA APLICAÇÃO UNIFICADA ===
// Script principal que gerencia todas as funcionalidades do AutoDoc Licitação

document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

// === VARIÁVEIS GLOBAIS E ESTADO DA APLICAÇÃO ===
// Controle global do estado da aplicação
let currentOpenMenu = null; // Controla qual menu dropdown está aberto
let originalParent = null; // Guarda o pai original do menu dropdown

// PASSO 1A: Sessão persistente para ETP
let SESSION_ID = localStorage.getItem("SESSION_ID") || null;

// Estado da conversa/documento atual
let currentConversation = {
    type: null, // 'chat' ou 'document'
    title: ''
};

// Estado para o fluxo de criação de ETP (Estudo Técnico Preliminar)
let etpState = {
    questionIndex: 0,
    answers: [],
    isGenerating: false,
    answeredQuestions: [], // IDs das perguntas já respondidas (1-5)
    extractedAnswers: {}, // Respostas extraídas por pergunta
    conversationHistory: [], // Histórico da conversa com o modelo fine-tuned
    consultativeOptions: [], // Opções geradas pela IA
    inConsultativePhase: false, // Se está na fase consultiva
    chosenOption: null // Opção escolhida pelo usuário
};

// Perguntas padrão para geração de ETP
const ETP_QUESTIONS = [
    "Qual a descrição da necessidade da contratação?",
    "Possui demonstrativo de previsão no PCA (Plano de Contratações Anual)?",
    "Quais normas legais pretende utilizar?",
    "Qual o quantitativo e valor estimado?",
    "Haverá parcelamento da contratação?"
];

// === ELEMENTOS DO DOM ===
// Cache dos principais elementos para melhor performance
const homeView = document.querySelector('.home-view');
const searchView = document.querySelector('.search-view');
const chatView = document.querySelector('.chat-view');
const chatTitle = document.getElementById('chatTitle');
const chatMessagesContainer = document.getElementById('chatMessages');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const searchInput = document.getElementById('searchInput');
const searchResultsContainer = document.getElementById('searchResults');
const modal = document.getElementById('editProfileModal');

// === INICIALIZAÇÃO E EVENTOS ===
// Configuração inicial da aplicação
function initializeApp() {
    // INTEGRAÇÃO: Verificar autenticação antes de inicializar o sistema
    checkAuthentication();
    setupEventListeners();
    // Adiciona alguns itens iniciais para demonstração
    addToRecentItems("ETP - Compra de Carros", "document", true);
    addToRecentItems("Dúvidas sobre a Lei 14.133", "chat", true);
    addToRecentItems("Contrato de Manutenção", "document", true);
}

// INTEGRAÇÃO: Verifica se o usuário está autenticado
async function checkAuthentication() {
    try {
        const response = await fetch('/api/auth/current');
        const data = await response.json();
        
        if (!data.success || !data.authenticated) {
            // Usuário não autenticado, redirecionar para login
            window.location.href = '/login.html';
            return;
        }
        
        // INTEGRAÇÃO: Atualizar informações do usuário no sistema
        if (data.user) {
            updateUserInfo(data.user);
        }
    } catch (error) {
        console.error('Erro ao verificar autenticação:', error);
        // Em caso de erro, redirecionar para login por segurança
        window.location.href = '/login.html';
    }
}

// INTEGRAÇÃO: Atualiza as informações do usuário na interface
function updateUserInfo(user) {
    // Atualiza nome do usuário
    const userNameElement = document.querySelector('.user-name');
    if (userNameElement && user.username) {
        userNameElement.textContent = user.username;
    }
    
    // Atualiza avatar com iniciais do nome
    const userAvatarElement = document.querySelector('.user-avatar');
    if (userAvatarElement && user.username) {
        const avatarText = user.username.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
        userAvatarElement.textContent = avatarText;
    }
}

// Configuração de todos os event listeners da aplicação
function setupEventListeners() {
    // Fechar menus e modais ao clicar fora
    document.addEventListener('click', function(event) {
        if (currentOpenMenu && !currentOpenMenu.contains(event.target) && !event.target.closest('.item-menu')) {
            closeAllMenus();
        }
        if (event.target === modal) {
            closeEditModal();
        }
    });

    // Eventos da Sidebar
    document.getElementById('newDocBtn').addEventListener('click', () => startNewConversation('document', 'Novo Documento'));
    document.getElementById('newConversationBtn').addEventListener('click', () => startNewConversation('chat', 'Nova Conversa'));
    
    // Eventos do Chat
    sendBtn.addEventListener('click', handleSendMessage);
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    });

    // Eventos da Pesquisa
    searchInput.addEventListener('input', () => renderSearchResults(searchInput.value));
    
    // Atalhos de teclado globais
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            if (currentOpenMenu) closeAllMenus();
            showHomeView(); // Volta para a home ao pressionar Esc
        }
    });
}

// === GERENCIAMENTO DE VIEWS ===
// Controle da navegação entre as três principais telas

// Exibe a tela inicial (home) com opções de documentos
function showHomeView() {
    homeView.style.display = 'flex';
    searchView.style.display = 'none';
    chatView.style.display = 'none';
}

// Exibe a tela de pesquisa
function showSearchView() {
    homeView.style.display = 'none';
    searchView.style.display = 'flex';
    chatView.style.display = 'none';
    renderSearchResults(); // Mostra todos os itens ao abrir
    searchInput.focus();
}

// Exibe a tela de chat/conversa
function showChatView() {
    homeView.style.display = 'none';
    searchView.style.display = 'none';
    chatView.style.display = 'flex';
}

// === LÓGICA DO CHAT E DOCUMENTOS ===
// Gerenciamento de conversas e geração de documentos

// Seleção de tipo de documento na tela inicial
function selectDocument(docType) {
    if (docType === 'estudo-tecnico') {
        startNewConversation('document', 'Novo Estudo Técnico Preliminar');
    } else {
        alert(`A criação de "${docType}" ainda não foi implementada.`);
    }
}

// Inicia uma nova conversa ou documento
function startNewConversation(type, title = "Novo") {
    showChatView();
    chatMessagesContainer.innerHTML = '';
    userInput.value = '';
    etpState = { 
        sessionId: 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9),
        questionIndex: 0, 
        answers: [], 
        isGenerating: false,
        answeredQuestions: [],
        extractedAnswers: {},
        conversationHistory: [],
        suggestedRequirements: [],
        confirmedRequirements: [],
        consultativeOptions: [],
        inConsultativePhase: false,
        chosenOption: null
    };

    currentConversation.type = type;
    currentConversation.title = title;
    chatTitle.textContent = currentConversation.title;

    // Diferentes fluxos para documento vs chat livre
    if (type === 'document') {
        addMessage("Vamos juntos montar seu Estudo Técnico Preliminar. Para começar, me diga qual é a necessidade da contratação?", 'ai');
    } else {
        addMessage("Olá! Como posso ajudar você hoje?", 'ai');
    }
    
    userInput.focus();
}

// Processa o envio de mensagens do usuário
function handleSendMessage() {
    const messageText = userInput.value.trim();
    if (messageText === '' || etpState.isGenerating) return;

    addMessage(messageText, 'user');
    userInput.value = '';

    // Delay para simular processamento
    setTimeout(() => {
        if (currentConversation.type === 'document') {
            handleDocumentFlow(messageText);
        } else {
            getAIChatResponse();
        }
    }, 500);
}

// Simula resposta da IA para chat livre
function getAIChatResponse() {
    const thinkingBubble = addMessage('<div class="typing-indicator"><span></span><span></span><span></span></div>', 'ai');
    // Simula uma resposta de IA
    setTimeout(() => {
        const responseText = "Esta é uma resposta simulada. A integração com um modelo de linguagem real forneceria uma resposta mais elaborada.";
        streamResponse(thinkingBubble, responseText);
    }, 1500);
}

// Gerencia a conversa durante a fase consultiva de opções
async function handleConsultativeConversation(userMessage) {
    // Adicionar mensagem do usuário ao histórico
    etpState.conversationHistory.push({
        role: 'user',
        content: userMessage
    });
    
    // Mostrar indicador de processamento
    const thinkingBubble = addMessage('<div class="typing-indicator"><span></span><span></span><span></span></div>', 'ai');
    
    try {
        const response = await fetch('/api/etp-dynamic/option-conversation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: userMessage,
                session_id: SESSION_ID,
                options: etpState.consultativeOptions,
                conversation_history: etpState.conversationHistory.slice(0, -1) // Excluir a mensagem atual
            })
        });
        
        const data = await response.json();
        
        // Remover indicador de processamento
        thinkingBubble.remove();
        
        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Erro na conversa consultiva');
        }
        
        const aiResponse = data.ai_response;
        const choiceAnalysis = data.choice_analysis;
        
        // Adicionar resposta da IA ao histórico
        etpState.conversationHistory.push({
            role: 'assistant',
            content: aiResponse
        });
        
        // Mostrar resposta da IA
        addMessage(aiResponse, 'ai');
        
        // Verificar se o usuário fez uma escolha final
        if (choiceAnalysis && choiceAnalysis.made_choice) {
            etpState.chosenOption = choiceAnalysis.chosen_option;
            etpState.inConsultativePhase = false;
            
            // Confirmar a escolha e proceder para geração do ETP
            setTimeout(() => {
                addMessage(`Perfeito! Registrei sua escolha pela "${choiceAnalysis.chosen_option}". Agora vou gerar o Estudo Técnico Preliminar baseado nesta solução...`, 'ai');
                setTimeout(() => {
                    etpState.isGenerating = true;
                    generateDocumentPreview();
                }, 2000);
            }, 1500);
        }
        
    } catch (error) {
        // Remover indicador de processamento em caso de erro
        thinkingBubble.remove();
        
        console.error('Erro na conversa consultiva:', error);
        addMessage('Desculpe, ocorreu um erro. Pode repetir sua mensagem?', 'ai');
    }
}

// Gerencia o fluxo de conversa natural para coleta de informações do ETP usando modelo fine-tuned
async function handleDocumentFlow(userMessage) {
    // Verificar se está na fase consultiva
    if (etpState.inConsultativePhase) {
        await handleConsultativeConversation(userMessage);
        return;
    }
    
    // Adicionar mensagem do usuário ao histórico da conversa
    etpState.conversationHistory.push({
        role: 'user',
        content: userMessage
    });
    
    // Mostrar indicador de processamento
    const thinkingBubble = addMessage('<div class="typing-indicator"><span></span><span></span><span></span></div>', 'ai');
    
    try {
        // Fazer chamada para o modelo fine-tuned com tratamento de erro de rede
        let response;
        try {
            response = await fetch('/api/etp-dynamic/conversation', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: userMessage,
                    session_id: SESSION_ID,
                    conversation_history: etpState.conversationHistory.slice(0, -1), // Excluir a mensagem atual já enviada
                    answered_questions: etpState.answeredQuestions,
                    extracted_answers: etpState.extractedAnswers
                })
            });
        } catch (networkError) {
            // Resiliência de rede: erro transitório sem resetar sessão
            thinkingBubble.remove();
            addMessage('Erro de conexão. Tente novamente em alguns instantes.', 'ai', {kind: 'text'});
            return;
        }
        
        const data = await response.json();
        
        // PASSO 1A: Capturar e persistir session_id
        if (!SESSION_ID && data.session_id) {
            SESSION_ID = data.session_id;
            localStorage.setItem("SESSION_ID", SESSION_ID);
        }
        
        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Erro na conversa com IA');
        }
        
        const aiResponse = data.ai_response;
        
        // Adicionar resposta da IA ao histórico da conversa
        etpState.conversationHistory.push({
            role: 'assistant',
            content: aiResponse
        });
        
        // Remover indicador de processamento e mostrar resposta
        thinkingBubble.remove();
        
        // PASSO 1B - Usar responseData se disponível para renderização estruturada
        if (data.kind) {
            addMessage(aiResponse, 'ai', data);
        } else {
            addMessage(aiResponse, 'ai');
        }
        
        // All responses are now handled as regular chat messages
        // No UI interruption for requirement suggestions
        
        // Analisar se a conversa está completa executando análise semântica em paralelo
        analyzeConversationProgress(userMessage);
        
    } catch (error) {
        // Remover indicador de processamento em caso de erro
        thinkingBubble.remove();
        
        console.error('Erro na conversa:', error);
        addMessage('Desculpe, ocorreu um erro ao processar sua mensagem. Pode tentar novamente?', 'ai');
    }
}

// Analisa o progresso da conversa para determinar quando todas as informações foram coletadas
async function analyzeConversationProgress(lastUserMessage) {
    try {
        // Usar a análise semântica para verificar se novas informações foram coletadas
        const response = await fetch('/api/etp-dynamic/analyze-response', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: lastUserMessage,
                session_id: SESSION_ID,
                response: lastUserMessage,
                answered_questions: etpState.answeredQuestions
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            const analysis = data.analysis;
            
            // Atualizar estado com as novas respostas identificadas
            analysis.answered_questions.forEach(questionId => {
                if (!etpState.answeredQuestions.includes(questionId)) {
                    etpState.answeredQuestions.push(questionId);
                }
            });
            
            // Mesclar respostas extraídas para armazenamento
            Object.assign(etpState.extractedAnswers, analysis.extracted_answers);
            
            // Verificar se todas as 5 perguntas foram respondidas
            if (analysis.all_questions_answered) {
                setTimeout(() => {
                    etpState.isGenerating = true;
                    addMessage("Perfeito! Coletei todas as informações necessárias. Antes de gerar o ETP, vou apresentar algumas opções de solução para você analisar...", 'ai');
                    setTimeout(generateConsultativeOptions, 2000);
                }, 1000);
            }
        }
        
    } catch (error) {
        console.error('Erro na análise de progresso:', error);
        // Não mostrar erro para o usuário, já que isso é processamento em background
    }
}

// REMOVED: suggestRequirements function - no longer needed as requirements are handled as regular chat messages

// REMOVED: createRequirementsInterface function - no longer needed as requirements are handled as regular chat messages

// REMOVED: All button handling functions - no longer needed as requirements are handled through regular chat messages

// Confirma requisitos com o backend
async function confirmRequirements(action, requirements, message) {
    try {
        // Mostrar indicador de processamento
        const thinkingBubble = addMessage('<div class="typing-indicator"><span></span><span></span><span></span></div>', 'ai');
        
        const response = await fetch('/api/etp-dynamic/confirm-requirements', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: SESSION_ID,
                action: action,
                requirements: requirements,
                message: message
            })
        });
        
        const data = await response.json();
        
        // Remover indicador de processamento
        thinkingBubble.remove();
        
        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Erro ao confirmar requisitos');
        }
        
        // Interface de requisitos removida - não há mais elementos para ocultar
        
        // Armazenar requisitos confirmados no estado
        etpState.confirmedRequirements = data.confirmed_requirements;
        
        // Mostrar resposta da IA
        addMessage(data.ai_response, 'ai');
        
    } catch (error) {
        thinkingBubble.remove();
        console.error('Erro ao confirmar requisitos:', error);
        addMessage('Desculpe, ocorreu um erro ao processar os requisitos. Vamos continuar com as outras informações do ETP.', 'ai');
    }
}

// Adiciona uma mensagem ao chat
function addMessage(content, sender, responseData = null) {
    const messageWrapper = document.createElement('div');
    messageWrapper.className = `chat-message ${sender}-message`;
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    
    // Se é resposta estruturada do backend, renderizar apropriadamente
    if (sender === 'ai' && responseData && responseData.kind) {
        bubble.innerHTML = renderStructuredResponse(responseData);
    }
    // Parse Markdown content if it's from AI and contains Markdown syntax
    else if (sender === 'ai' && typeof marked !== 'undefined' && 
        (content.includes('**') || content.includes('*') || content.includes('- ') || 
         content.includes('# ') || content.includes('\n'))) {
        // Configure marked for better formatting
        marked.setOptions({
            breaks: true, // Convert \n to <br>
            gfm: true // GitHub Flavored Markdown
        });
        // Sanitizar conteúdo antes do parsing
        const sanitizedContent = sanitizeJsonInText(content);
        bubble.innerHTML = marked.parse(sanitizedContent);
    } else {
        // Sanitizar conteúdo básico
        const sanitizedContent = sanitizeJsonInText(content);
        bubble.innerHTML = sanitizedContent;
    }
    
    messageWrapper.appendChild(bubble);
    chatMessagesContainer.appendChild(messageWrapper);
    chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    return bubble;
}

// PASSO 1B - Renderiza respostas estruturadas baseadas no campo 'kind'
function renderStructuredResponse(responseData) {
    const kind = responseData.kind;
    
    if (kind && kind.startsWith('requirements_')) {
        // Usar função de renderização limpa do requirements_renderer.js
        const renderedElement = renderConversationalMessage(responseData);
        return renderedElement.outerHTML;
    }
    
    // Para outros tipos, usar mensagem padrão em Markdown
    if (responseData.message && typeof marked !== 'undefined') {
        marked.setOptions({
            breaks: true,
            gfm: true
        });
        return marked.parse(responseData.message);
    }
    
    return responseData.message || 'Resposta recebida.';
}

// PASSO 1B - Função removida - usando renderAssistantMessage do requirements_renderer.js

// Sanitiza texto removendo objetos JSON visíveis
function sanitizeJsonInText(text) {
    if (typeof text !== 'string') {
        return text;
    }
    
    // Remove objetos JSON que aparecem no formato { "key": "value" }
    let sanitized = text.replace(/\{\s*["'][\w_]+["']\s*:\s*["'][^"']*["']\s*(?:,\s*["'][\w_]+["']\s*:\s*["'][^"']*["']\s*)*\}/g, '');
    
    // Remove arrays JSON que aparecem no formato [{"key": "value"}]
    sanitized = sanitized.replace(/\[\s*\{\s*["'][\w_]+["']\s*:\s*["'][^"']*["']\s*(?:,\s*["'][\w_]+["']\s*:\s*["'][^"']*["']\s*)*\}\s*(?:,\s*\{\s*["'][\w_]+["']\s*:\s*["'][^"']*["']\s*(?:,\s*["'][\w_]+["']\s*:\s*["'][^"']*["']\s*)*\}\s*)*\]/g, '');
    
    return sanitized.trim();
}

// Escapa HTML para prevenir XSS
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, function(m) { return map[m]; });
}

// Efeito de digitação para respostas da IA
function streamResponse(bubbleElement, text) {
    bubbleElement.innerHTML = '';
    let index = 0;
    const interval = setInterval(() => {
        if (index < text.length) {
            bubbleElement.textContent += text.charAt(index);
            index++;
            chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
        } else {
            clearInterval(interval);
            // After streaming is complete, parse Markdown if content contains Markdown syntax
            if (typeof marked !== 'undefined' && 
                (text.includes('**') || text.includes('*') || text.includes('- ') || 
                 text.includes('# ') || text.includes('\n'))) {
                marked.setOptions({
                    breaks: true, // Convert \n to <br>
                    gfm: true // GitHub Flavored Markdown
                });
                bubbleElement.innerHTML = marked.parse(text);
            }
        }
    }, 25);
}

// Funções de sugestões removidas - o novo fluxo usa conversa natural sem botões

// Gera opções consultivas baseadas nas respostas coletadas
async function generateConsultativeOptions() {
    try {
        // Mostrar indicador de processamento
        const thinkingBubble = addMessage('<div class="typing-indicator"><span></span><span></span><span></span></div>', 'ai');
        
        const response = await fetch('/api/etp-dynamic/consultative-options', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: SESSION_ID,
                extracted_answers: etpState.extractedAnswers
            })
        });
        
        const data = await response.json();
        
        // Remover indicador de processamento
        thinkingBubble.remove();
        
        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Erro ao gerar opções consultivas');
        }
        
        // Armazenar opções no estado
        etpState.consultativeOptions = data.options;
        etpState.inConsultativePhase = true;
        etpState.isGenerating = false;
        
        // Apresentar mensagem consultiva
        addMessage(data.consultative_message, 'ai');
        
        // Apresentar cada opção de forma natural
        setTimeout(() => {
            presentOptionsNaturally(data.options);
        }, 1500);
        
    } catch (error) {
        console.error('Erro ao gerar opções consultivas:', error);
        addMessage('Desculpe, ocorreu um erro ao gerar as opções. Vou proceder diretamente com a geração do ETP.', 'ai');
        setTimeout(() => {
            etpState.inConsultativePhase = false;
            generateDocumentPreview();
        }, 2000);
    }
}

// Apresenta as opções de forma natural, como conversa
function presentOptionsNaturally(options) {
    options.forEach((option, index) => {
        setTimeout(() => {
            let optionMessage = `**${option.name}**\n\n${option.summary}\n\n`;
            
            if (option.pros && option.pros.length > 0) {
                optionMessage += `**Vantagens:**\n`;
                option.pros.forEach(pro => {
                    optionMessage += `• ${pro}\n`;
                });
                optionMessage += '\n';
            }
            
            if (option.cons && option.cons.length > 0) {
                optionMessage += `**Pontos de atenção:**\n`;
                option.cons.forEach(con => {
                    optionMessage += `• ${con}\n`;
                });
            }
            
            addMessage(optionMessage, 'ai');
            
            // Após apresentar todas as opções, perguntar qual escolher
            if (index === options.length - 1) {
                setTimeout(() => {
                    addMessage("Essas são as principais alternativas que identifiquei. Você pode me perguntar mais detalhes sobre qualquer uma delas, sugerir uma terceira opção, ou me dizer qual prefere seguir. O que acha?", 'ai');
                }, 1000);
            }
        }, (index + 1) * 2000);
    });
}

// Gera o preview do documento ETP
function generateDocumentPreview() {
    const messageWrapper = document.createElement('div');
    messageWrapper.className = 'chat-message ai-message';
    const previewBlock = document.createElement('div');
    previewBlock.className = 'document-preview-block';
    previewBlock.innerHTML = `
        <div class="preview-header">
            <span class="preview-title">Preview do Documento</span>
            <button class="download-doc-btn" id="downloadBtn" disabled>Baixar Documento</button>
        </div>
        <div class="preview-content"><pre><code></code></pre></div>
    `;
    messageWrapper.appendChild(previewBlock);
    chatMessagesContainer.appendChild(messageWrapper);

    const codeElement = previewBlock.querySelector('code');
    const downloadBtn = previewBlock.querySelector('#downloadBtn');

    // Template do documento ETP baseado nas respostas dinamicamente coletadas
    const documentText = `
1. DO OBJETO
   - Descrição da Necessidade: ${etpState.extractedAnswers[1] || 'Não informado'}
   - Previsão no PCA: ${etpState.extractedAnswers[2] || 'Não informado'}
   - Normas Legais: ${etpState.extractedAnswers[3] || 'Não informado'}

2. DOS VALORES E QUANTITATIVOS
   - Quantitativo e Valor Estimado: ${etpState.extractedAnswers[4] || 'Não informado'}
   - Parcelamento da Contratação: ${etpState.extractedAnswers[5] || 'Não informado'}

3. JUSTIFICATIVA TÉCNICA
   - A contratação se justifica pela necessidade de...

Este documento foi gerado automaticamente pelo AutoDoc Licitação usando análise semântica inteligente.
    `;

    streamDocument(codeElement, downloadBtn, documentText.trim().split('\n'));
}

// Efeito de digitação para o documento
function streamDocument(codeElement, downloadBtn, lines) {
    let lineIndex = 0;
    const interval = setInterval(() => {
        if (lineIndex < lines.length) {
            codeElement.textContent += lines[lineIndex] + '\n';
            lineIndex++;
            chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
        } else {
            clearInterval(interval);
            downloadBtn.disabled = false;
            etpState.isGenerating = false;
            downloadBtn.addEventListener('click', () => alert('Simulando download do documento .docx...'));
        }
    }, 100);
}

// === LÓGICA DE PESQUISA ===
// Sistema de busca por conversas e documentos
function renderSearchResults(query = '') {
    searchResultsContainer.innerHTML = '';
    const recentItems = document.querySelectorAll('.sidebar .recent-item');
    const normalizedQuery = query.toLowerCase().trim();

    recentItems.forEach(item => {
        const itemName = item.querySelector('.item-name').textContent.toLowerCase();
        if (itemName.includes(normalizedQuery)) {
            const iconClass = item.querySelector('.item-icon').className;
            const originalName = item.querySelector('.item-name').textContent;
            const type = item.dataset.type;

            const resultEl = document.createElement('div');
            resultEl.className = 'search-result-item';
            resultEl.innerHTML = `<i class="${iconClass}"></i><span class="item-name">${originalName}</span>`;
            resultEl.addEventListener('click', () => {
                startNewConversation(type, originalName);
            });
            searchResultsContainer.appendChild(resultEl);
        }
    });
}

// === FUNÇÕES DA SIDEBAR ===
// Gerenciamento de itens recentes e navegação lateral

// Adiciona um item à lista de recentes
function addToRecentItems(name, type, isInitial = false) {
    const recentItemsContainer = document.querySelector('.recent-items');
    const iconClass = type === 'chat' ? 'fas fa-comments' : 'fas fa-file-alt';
    
    const newItem = document.createElement('div');
    newItem.className = 'recent-item';
    newItem.dataset.type = type; // Importante para a busca e para abrir a conversa
    
    newItem.innerHTML = `
        <i class="${iconClass} item-icon"></i>
        <span class="item-name">${name}</span>
        <button class="item-menu" onclick="toggleMenu(event, this)">
            <i class="fas fa-ellipsis-v"></i>
        </button>
        <div class="dropdown-menu">
            <button onclick="pinItem(this)"><i class="fas fa-thumbtack"></i> Fixar</button>
            <button onclick="renameItem(this)"><i class="fas fa-edit"></i> Renomear</button>
            <button onclick="deleteItem(this)"><i class="fas fa-trash"></i> Excluir</button>
        </div>
    `;
    
    // Event listener para abrir conversa ao clicar no item
    newItem.addEventListener('click', (e) => {
        if (!e.target.closest('.item-menu')) {
            startNewConversation(type, name);
        }
    });

    // Adiciona no topo (novos) ou no final (iniciais)
    if (isInitial) {
        recentItemsContainer.appendChild(newItem);
    } else {
        recentItemsContainer.insertBefore(newItem, recentItemsContainer.firstChild);
    }
}

// Controla abertura/fechamento dos menus dropdown
function toggleMenu(event, button) {
    event.stopPropagation(); // Impede que o clique no menu abra a conversa
    const recentItem = button.closest('.recent-item');
    const menu = recentItem.querySelector('.dropdown-menu');

    if (currentOpenMenu && currentOpenMenu !== menu) {
        closeAllMenus();
    }
    
    if (!menu.classList.contains('show')) {
        currentOpenMenu = menu;
        originalParent = recentItem;
        document.body.appendChild(menu);
        menu.classList.add('show');
        const rect = button.getBoundingClientRect();
        menu.style.top = `${rect.bottom}px`;
        menu.style.left = `${rect.left}px`;
        
        // Atualiza texto do botão fixar baseado no estado atual
        const pinButton = menu.querySelector('button[onclick="pinItem(this)"]');
        pinButton.innerHTML = recentItem.classList.contains('pinned') 
            ? '<i class="fas fa-thumbtack"></i> Desfixar' 
            : '<i class="fas fa-thumbtack"></i> Fixar';
    } else {
        closeAllMenus();
    }
}

// Fecha todos os menus dropdown abertos
function closeAllMenus() {
    if (currentOpenMenu) {
        currentOpenMenu.classList.remove('show');
        originalParent.appendChild(currentOpenMenu); // Devolve o menu ao seu local original
        currentOpenMenu = null;
        originalParent = null;
    }
}

// Fixa/desfixa um item no topo da lista
function pinItem(button) {
    const recentItem = originalParent;
    const isPinned = recentItem.classList.toggle('pinned');
    
    if (isPinned) {
        // Adiciona ícone de fixado
        if (!recentItem.querySelector('.pinned-icon')) {
            const pinIcon = document.createElement('i');
            pinIcon.className = 'fas fa-thumbtack pinned-icon';
            recentItem.prepend(pinIcon);
        }
        recentItem.parentElement.prepend(recentItem);
    } else {
        // Remove ícone de fixado
        recentItem.querySelector('.pinned-icon')?.remove();
    }
    closeAllMenus();
}

// Remove um item da lista
function deleteItem(button) {
    const itemToDelete = originalParent;
    const itemName = itemToDelete.querySelector('.item-name').textContent;
    if (confirm(`Tem certeza que deseja excluir "${itemName}"?`)) {
        itemToDelete.style.opacity = '0';
        itemToDelete.style.transform = 'translateX(-20px)';
        setTimeout(() => itemToDelete.remove(), 300);
    }
    closeAllMenus();
}

// Renomeia um item da lista
function renameItem(button) {
    const itemNameEl = originalParent.querySelector('.item-name');
    const currentName = itemNameEl.textContent;
    const newName = prompt('Digite o novo nome:', currentName);
    if (newName && newName.trim() !== '' && newName !== currentName) {
        itemNameEl.textContent = newName.trim();
    }
    closeAllMenus();
}

// Recolhe/expande a sidebar
function toggleSidebar() {
    document.querySelector('.sidebar').classList.toggle('collapsed');
}

// === MODAL DE USUÁRIO ===
// Funcionalidades relacionadas ao perfil do usuário

// Abre modal de edição de perfil
function editUser() {
    document.getElementById('userName').value = document.querySelector('.user-name').textContent;
    document.getElementById('userEmail').value = "ale.maciel@exemplo.com"; // Email de exemplo
    modal.classList.add('show');
}

// Fecha modal de edição de perfil
function closeEditModal() {
    modal.classList.remove('show');
}

// Salva alterações do perfil
function saveProfile(event) {
    event.preventDefault();
    const newName = document.getElementById('userName').value.trim();
    if (newName) {
        document.querySelector('.user-name').textContent = newName;
        // Atualiza avatar com iniciais do nome
        const avatarText = newName.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
        document.querySelector('.user-avatar').textContent = avatarText;
    }
    closeEditModal();
}

// INTEGRAÇÃO: Logout integrado com o backend de autenticação
function logout() {
    if (confirm('Tem certeza que deseja sair?')) {
        // Chama o endpoint de logout do backend
        fetch('/api/auth/logout', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Redireciona para a página de login após logout bem-sucedido
                window.location.href = '/login.html';
            } else {
                alert('Erro ao fazer logout: ' + (data.error || 'Erro desconhecido'));
            }
        })
        .catch(error => {
            console.error('Erro na requisição de logout:', error);
            // Mesmo em caso de erro, redireciona para login por segurança
            window.location.href = '/login.html';
        });
    }
}