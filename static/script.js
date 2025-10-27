// === INICIALIZAÇÃO DA APLICAÇÃO UNIFICADA ===
// Script principal que gerencia todas as funcionalidades do AutoDoc Licitação
// usa window.renderTextSmart carregado antes

document.addEventListener('DOMContentLoaded', function() {
    // Remover indicador de fase (fallback: some id/classes prováveis)
    const phaseEl = document.querySelector('#phase, #stage, #stage-indicator, .phase, .phase-indicator');
    if (phaseEl) { phaseEl.remove(); }
    initializeApp();
});

// === VARIÁVEIS GLOBAIS E ESTADO DA APLICAÇÃO ===
// Controle global do estado da aplicação
let currentOpenMenu = null; // Controla qual menu dropdown está aberto
let originalParent = null; // Guarda o pai original do menu dropdown

// Conversation persistence for persistent chat
let CONVERSATION_ID = localStorage.getItem("CONVERSATION_ID") || null;

// Helper functions for conversation management
function setConversationId(cid) {
    if (!cid) return;
    try {
        CONVERSATION_ID = cid;
        localStorage.setItem('CONVERSATION_ID', cid);
        window.__CONVERSATION_ID__ = cid;
        console.log('[CONVERSATION] Set conversation_id:', cid);
    } catch(e) {
        console.warn('Não foi possível salvar CONVERSATION_ID', e);
    }
}

function getConversationId() {
    return CONVERSATION_ID || window.__CONVERSATION_ID__ || localStorage.getItem('CONVERSATION_ID');
}

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

// Perguntas padrão para geração de ETP - REMOVED per issue requirements
// Flow now uses stage-based approach without ready-made questionnaires
const ETP_QUESTIONS = [];

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
    // Load conversation history from backend
    loadConversationHistory();
}

// INTEGRAÇÃO: Verifica se o usuário está autenticado
async function checkAuthentication() {
    try {
        const response = await fetch('/api/auth/current', {
            credentials: 'include'
        });
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
    if (!user) return;

    const displayName = user.full_name || user.username || 'Demo';
    const initials = (displayName || 'U')
        .split(/\s+/)
        .filter(Boolean)
        .map(part => part[0])
        .join('')
        .substring(0, 2)
        .toUpperCase() || 'D';

    const nameElement = document.getElementById('currentUserName') || document.querySelector('.user-name');
    if (nameElement) {
        nameElement.textContent = displayName;
    }

    const avatarElement = document.getElementById('currentUserInitials') || document.querySelector('.user-avatar');
    if (avatarElement) {
        avatarElement.textContent = initials;
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
    const newDocBtn = document.getElementById('newDocBtn');
    if (newDocBtn) {
        newDocBtn.addEventListener('click', () => startNewConversation('document', 'Novo Documento'));
    }
    const newConversationBtn = document.getElementById('newConversationBtn');
    if (newConversationBtn) {
        newConversationBtn.addEventListener('click', () => startNewConversation('chat', 'Nova Conversa'));
    }

    // Eventos do Chat
    if (sendBtn) {
        sendBtn.addEventListener('click', handleSendMessage);
    }
    if (userInput) {
        userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
            }
        });
    }

    // Eventos da Pesquisa
    if (searchInput) {
        searchInput.addEventListener('input', () => renderSearchResults(searchInput.value));
    }
    
    // Atalhos de teclado globais
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            if (currentOpenMenu) closeAllMenus();
            showHomeView(); // Volta para a home ao pressionar Esc
        }
    });

    // Reset de conversa: botão/ação "Nova Conversa" dispara reset no servidor
    const newConvEls = Array.from(document.querySelectorAll('#new-conversation, [data-action="new-conversation"], a[href="#new-conversation"]'));
    newConvEls.forEach(el => {
        el.addEventListener('click', async (e) => {
            e.preventDefault();
            const sid = getSessionId();
            await fetch('/api/etp-dynamic/conversation', {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reset: true, session_id: sid })
            }).catch(()=>{});
            // limpa UI
            document.getElementById('chat-log') && (document.getElementById('chat-log').innerHTML = '');
            if (chatMessagesContainer) chatMessagesContainer.innerHTML = '';
            const req = document.getElementById('requirements');
            if (req) req.innerHTML = '';
            addMessage('Vamos começar um novo ETP. Qual é a necessidade da contratação?', 'ai');
        });
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
async function startNewConversation(type, title = "Novo") {
    showChatView();
    chatMessagesContainer.innerHTML = '';
    userInput.value = '';
    
    // Call backend to create new conversation
    try {
        const response = await fetch('/api/etp-dynamic/new', {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Erro ao criar nova conversa');
        }
        
        console.log('[NEW] Created conversation:', data.conversation_id);
        
        // Set global conversation ID
        setConversationId(data.conversation_id);
        
        // Initialize local state
        etpState = { 
            conversationId: data.conversation_id,
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
        currentConversation.title = data.title || title;
        chatTitle.textContent = currentConversation.title;

        // Add to sidebar with conversation_id
        addToRecentItems(currentConversation.title, type, false, data.conversation_id);

        // Initial greeting
        addMessage("Olá! Vamos conversar sobre seu Estudo Técnico Preliminar. Qual é a necessidade da contratação?", 'ai');
        
        userInput.focus();
    } catch (error) {
        console.error('Error creating new conversation:', error);
        alert('Erro ao criar nova conversa: ' + error.message);
    }
}

// Track active streams by message ID
const activeStreams = new Map();

// Stream a message using Server-Sent Events (SSE)
async function handleSendMessageStreaming() {
    const messageText = userInput.value.trim();
    if (messageText === '' || etpState.isGenerating) return;
    
    const conversationId = getConversationId();
    if (!conversationId) {
        alert('Nenhuma conversa ativa. Por favor, inicie uma nova conversa.');
        return;
    }

    addMessage(messageText, 'user');
    userInput.value = '';
    
    // Generate unique message ID for this request
    const messageId = `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    
    // Create empty AI message bubble that will be filled with streaming content
    const aiMessageElement = addMessage('', 'ai');
    const aiMessageContent = aiMessageElement.querySelector('.message-text') || aiMessageElement;
    
    // Add small typing indicator (non-blocking)
    const typingIndicator = document.createElement('span');
    typingIndicator.className = 'streaming-indicator';
    typingIndicator.textContent = '▊';
    typingIndicator.style.opacity = '0.5';
    typingIndicator.style.animation = 'blink 1s infinite';
    aiMessageContent.appendChild(typingIndicator);
    
    let fullText = '';
    let eventSource = null;
    
    try {
        // Use fetch to POST the message, then establish SSE connection
        const response = await fetch('/api/etp-dynamic/chat-stream', {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: conversationId,
                message: messageText,
                message_id: messageId
            })
        });

        if (!response.ok) {
            throw new Error('Failed to initiate streaming');
        }

        // Read the response as a stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        // Store active stream
        activeStreams.set(messageId, { reader, aiMessageContent });
        
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) {
                break;
            }
            
            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.substring(6);
                    
                    try {
                        const event = JSON.parse(data);
                        
                        if (event.type === 'token') {
                            // Append token to message buffer
                            fullText += event.content;
                            typingIndicator.remove();
                            
                            // Use renderTextSmart if available, with throttling
                            if (typeof window.renderTextSmart === 'function') {
                                // Store buffer in dataset for re-rendering
                                aiMessageContent.dataset.buf = fullText;
                                aiMessageContent.dataset.stage = event.stage || etpState.currentStage || '';
                                
                                // Throttle rendering during streaming
                                if (!aiMessageContent._rendering) {
                                    aiMessageContent._rendering = true;
                                    requestAnimationFrame(() => {
                                        window.renderTextSmart(aiMessageContent, aiMessageContent.dataset.buf, aiMessageContent.dataset.stage);
                                        aiMessageContent._rendering = false;
                                    });
                                }
                            } else {
                                // Fallback to simple text
                                aiMessageContent.textContent = fullText;
                            }
                            
                            aiMessageContent.appendChild(typingIndicator);
                            
                            // Auto-scroll to bottom
                            chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
                            
                        } else if (event.type === 'final') {
                            // Backend sends final sanitized content for re-rendering
                            fullText = event.content;
                            aiMessageContent.dataset.buf = fullText;
                            const stage = event.stage || aiMessageContent.dataset.stage || etpState.currentStage || '';
                            
                            if (typeof window.renderTextSmart === 'function') {
                                window.renderTextSmart(aiMessageContent, fullText, stage);
                            } else {
                                aiMessageContent.textContent = fullText;
                            }
                            
                        } else if (event.type === 'done') {
                            // Stream complete - final render with renderTextSmart
                            typingIndicator.remove();
                            const finalText = fullText || event.full_response || 'Resposta concluída.';
                            const stage = event.stage || aiMessageContent.dataset.stage || etpState.currentStage || '';
                            
                            if (typeof window.renderTextSmart === 'function') {
                                window.renderTextSmart(aiMessageContent, finalText, stage);
                            } else {
                                aiMessageContent.textContent = finalText;
                            }
                            
                            // Update state if needed
                            if (event.state_changed) {
                                console.log(`[STREAM] State changed to: ${event.state}`);
                            }
                            
                        } else if (event.type === 'error') {
                            // Stream error
                            typingIndicator.remove();
                            aiMessageContent.textContent = `Erro: ${event.error}`;
                            aiMessageElement.classList.add('error');
                        }
                        
                    } catch (parseError) {
                        console.warn('Failed to parse SSE data:', data, parseError);
                    }
                }
            }
        }
        
        // Clean up
        activeStreams.delete(messageId);
        
    } catch (error) {
        console.error('Error in streaming:', error);
        typingIndicator.remove();
        aiMessageContent.textContent = 'Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente.';
        aiMessageElement.classList.add('error');
        activeStreams.delete(messageId);
    }
}

// Processa o envio de mensagens do usuário
async function handleSendMessage() {
    // Check if streaming is enabled (default to true)
    const useStreaming = localStorage.getItem('useStreaming') !== 'false';
    
    if (useStreaming) {
        return handleSendMessageStreaming();
    }
    
    // Fallback to non-streaming version
    const messageText = userInput.value.trim();
    if (messageText === '' || etpState.isGenerating) return;
    
    const conversationId = getConversationId();
    if (!conversationId) {
        alert('Nenhuma conversa ativa. Por favor, inicie uma nova conversa.');
        return;
    }

    addMessage(messageText, 'user');
    userInput.value = '';
    etpState.isGenerating = true;

    // Show typing indicator
    const thinkingBubble = addMessage('<div class="typing-indicator"><span></span><span></span><span></span></div>', 'ai');

    try {
        // Use stage-based endpoint for deterministic flow
        const response = await fetch('/api/etp-dynamic/chat-stage', {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                conversation_id: conversationId,
                message: messageText
            })
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Erro ao enviar mensagem');
        }

        // Remove thinking bubble and add AI response
        thinkingBubble.remove();
        
        // Display AI response
        addMessage(data.ai_response, 'ai');
        
        // If requirements are returned, store them
        if (data.requirements) {
            etpState.suggestedRequirements = data.requirements;
        }
        
        // Preview is handled via code block in the AI response message itself
        // No separate download links block needed

    } catch (error) {
        console.error('Error sending message:', error);
        thinkingBubble.remove();
        addMessage('Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente.', 'ai');
    } finally {
        etpState.isGenerating = false;
    }
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
            credentials: 'include',
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
    // Novo fluxo: usa pipeline (UM POST /conversation por turno, sem auto-avanço)
    await pipeline(userMessage);
}

// Novo pipeline: UMA única ida ao backend /conversation por turno
async function pipeline(message) {
    const sid = getSessionId();
    const res = await fetch('/api/etp-dynamic/conversation', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, session_id: sid })
    });
    if (!res.ok) {
        addMessage('Algo deu errado. Tente reformular sua mensagem.', 'ai');
        return;
    }
    const data = await res.json();
    
    // IMPORTANTE: Capturar session_id se for nova sessão
    if (data.session_id && !SESSION_ID) {
        setSessionId(data.session_id);
        // Adicionar conversa na sidebar
        addToRecentItems(`ETP - ${new Date().toLocaleDateString()}`, 'document', false);
    }
    
    // Se há requisitos, usar renderização conversacional (única mensagem)
    if (Array.isArray(data.requirements) && data.requirements.length > 0) {
        // Usar a função do requirements_renderer.js
        const reqMessage = window.renderRequirementsMessage 
            ? window.renderRequirementsMessage(data) 
            : data.requirements.map((r, i) => `${i + 1}. ${typeof r === 'string' ? r : (r.text || String(r))}`).join('\n');
        addMessage(reqMessage, 'ai');
    } 
    // Senão, mensagem principal do assistente
    else if (data.message || data.response || data.ai_response) {
        addMessage(data.message || data.response || data.ai_response, 'ai');
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
            credentials: 'include',
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
    // Enhanced guard against empty content - render placeholder instead of empty bubble
    if (!content || (typeof content === 'string' && !content.trim())) {
        if (!responseData || !responseData.kind) {
            console.warn('[EMPTY_BUBBLE_GUARD] Empty content detected, rendering placeholder');
            // For AI messages, render a placeholder that can be updated later
            if (sender === 'ai') {
                const messageWrapper = document.createElement('div');
                messageWrapper.className = `chat-message ${sender}-message`;
                const bubble = document.createElement('div');
                bubble.className = 'message-bubble msg-placeholder';
                bubble.innerHTML = '<div class="placeholder-spinner"></div><span>Preparando resposta…</span>';
                messageWrapper.appendChild(bubble);
                chatMessagesContainer.appendChild(messageWrapper);
                chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
                return bubble;
            }
            // For user messages, don't render at all
            return null;
        }
    }
    
    const messageWrapper = document.createElement('div');
    messageWrapper.className = `chat-message ${sender}-message`;
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    
    // Se é resposta estruturada do backend, renderizar apropriadamente
    if (sender === 'ai' && responseData && responseData.kind) {
        bubble.innerHTML = renderStructuredResponse(responseData);
    } else if (sender === 'ai') {
        const sanitizedContent = sanitizeJsonInText(content || '');
        if (typeof marked !== 'undefined') {
            try {
                marked.setOptions({ breaks: true, gfm: true });
                bubble.innerHTML = marked.parse(sanitizedContent || '');
                enhanceEtpPreviewBlocks(bubble);
            } catch (err) {
                console.warn('[MARKDOWN] Falha ao renderizar markdown:', err);
                bubble.textContent = sanitizedContent || '';
            }
        } else {
            bubble.textContent = sanitizedContent || '';
        }
    } else {
        bubble.textContent = content || '';
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
        const renderedElement = renderAssistantMessage(responseData);
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

// Enhance ETP preview code blocks with download button
function enhanceEtpPreviewBlocks(container) {
    // Find all code blocks with language "etp-preview"
    const codeBlocks = container.querySelectorAll('pre code.language-etp-preview');
    
    codeBlocks.forEach(codeBlock => {
        const pre = codeBlock.parentElement;
        
        // Add class for styling
        pre.classList.add('etp-preview-block');
        
        // Get ETP content
        const etpContent = codeBlock.textContent;
        
        // Create wrapper for preview and sticky button
        const previewWrapper = document.createElement('div');
        previewWrapper.className = 'etp-preview-wrapper';
        previewWrapper.style.position = 'relative';
        
        // Wrap the pre element
        pre.parentNode.insertBefore(previewWrapper, pre);
        previewWrapper.appendChild(pre);
        
        // Create sticky button container
        const stickyButtonContainer = document.createElement('div');
        stickyButtonContainer.className = 'etp-sticky-buttons';
        stickyButtonContainer.style.position = 'sticky';
        stickyButtonContainer.style.bottom = '16px';
        stickyButtonContainer.style.right = '16px';
        stickyButtonContainer.style.display = 'flex';
        stickyButtonContainer.style.gap = '8px';
        stickyButtonContainer.style.justifyContent = 'flex-end';
        stickyButtonContainer.style.paddingTop = '8px';
        stickyButtonContainer.style.zIndex = '10';
        
        // Create HTML download button
        const downloadHtmlBtn = document.createElement('button');
        downloadHtmlBtn.className = 'etp-download-btn html';
        downloadHtmlBtn.innerHTML = '📄 HTML';
        downloadHtmlBtn.title = 'Baixar como HTML';
        downloadHtmlBtn.setAttribute('aria-label', 'Baixar documento ETP em formato HTML');
        downloadHtmlBtn.onclick = () => downloadEtpDocument(etpContent);
        
        // Create DOCX download button
        const downloadDocxBtn = document.createElement('button');
        downloadDocxBtn.className = 'etp-download-btn docx';
        downloadDocxBtn.innerHTML = '📝 DOCX';
        downloadDocxBtn.title = 'Baixar como DOCX';
        downloadDocxBtn.setAttribute('aria-label', 'Baixar documento ETP em formato DOCX');
        downloadDocxBtn.disabled = false;
        downloadDocxBtn.onclick = () => downloadEtpDocx();
        
        // Add buttons to container
        stickyButtonContainer.appendChild(downloadHtmlBtn);
        stickyButtonContainer.appendChild(downloadDocxBtn);
        
        // Add sticky container to wrapper
        previewWrapper.appendChild(stickyButtonContainer);
        
        console.log('[ETP_PREVIEW] Enhanced ETP preview block with sticky download buttons');
    });
}

// Download ETP document as DOCX
async function downloadEtpDocx() {
    console.log('[ETP_DOWNLOAD] Generating DOCX document');
    
    const conversationId = getConversationId();
    if (!conversationId) {
        alert('Nenhuma conversa ativa. Por favor, inicie uma nova conversa.');
        return;
    }
    
    // Find the DOCX button and disable it during generation
    const docxButtons = document.querySelectorAll('.etp-download-btn.docx');
    docxButtons.forEach(btn => {
        btn.disabled = true;
        btn.innerHTML = '⏳ Gerando...';
    });
    
    try {
        const response = await fetch('/api/etp-dynamic/export/docx', {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: conversationId,
                title: 'Estudo Técnico Preliminar',
                organ: 'Órgão Contratante',
                object: 'Contratação'
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Erro ao gerar documento DOCX');
        }
        
        // Download the file
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `ETP-${conversationId.substring(0, 8)}.docx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        console.log('[ETP_DOWNLOAD] DOCX document downloaded successfully');
        
    } catch (error) {
        console.error('[ETP_DOWNLOAD] Error generating DOCX:', error);
        alert(`Erro ao gerar documento DOCX: ${error.message}`);
        
    } finally {
        // Re-enable button
        docxButtons.forEach(btn => {
            btn.disabled = false;
            btn.innerHTML = '📝 DOCX';
        });
    }
}

// Download ETP document as styled HTML
function downloadEtpDocument(etpContent) {
    console.log('[ETP_DOWNLOAD] Generating document for download');
    
    // Generate styled HTML document
    const htmlDoc = generateStyledEtpHtml(etpContent);
    
    // Create blob and download
    const blob = new Blob([htmlDoc], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ETP_${new Date().getTime()}.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    console.log('[ETP_DOWNLOAD] Document downloaded successfully');
}

// Generate styled HTML document based on ETP template design
function generateStyledEtpHtml(content) {
    // Convert markdown to HTML if needed
    let htmlContent = content;
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            breaks: true,
            gfm: true
        });
        htmlContent = marked.parse(content);
    }
    
    // Create full HTML document with professional styling
    return `<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Estudo Técnico Preliminar (ETP)</title>
    <style>
        @page {
            margin: 2.5cm;
        }
        
        body {
            font-family: 'Calibri', 'Arial', sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 21cm;
            margin: 0 auto;
            padding: 2.5cm;
            background: #fff;
        }
        
        h1 {
            color: #003366;
            border-bottom: 3px solid #0066cc;
            padding-bottom: 10px;
            margin-top: 0;
            font-size: 24pt;
            text-align: center;
        }
        
        h2 {
            color: #003366;
            border-bottom: 2px solid #0066cc;
            padding-bottom: 5px;
            margin-top: 30px;
            font-size: 18pt;
        }
        
        h3 {
            color: #0066cc;
            margin-top: 20px;
            font-size: 14pt;
        }
        
        h4 {
            color: #003366;
            margin-top: 15px;
            font-size: 12pt;
        }
        
        p {
            text-align: justify;
            margin: 10px 0;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 11pt;
        }
        
        table th {
            background-color: #003366;
            color: white;
            padding: 10px;
            text-align: left;
            border: 1px solid #003366;
        }
        
        table td {
            padding: 8px;
            border: 1px solid #ccc;
        }
        
        table tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        
        ul, ol {
            margin: 10px 0;
            padding-left: 30px;
        }
        
        li {
            margin: 5px 0;
        }
        
        strong {
            color: #003366;
        }
        
        .metadata {
            text-align: right;
            color: #666;
            font-size: 10pt;
            margin-bottom: 30px;
        }
        
        hr {
            border: none;
            border-top: 1px solid #0066cc;
            margin: 20px 0;
        }
        
        @media print {
            body {
                padding: 0;
            }
            
            h1, h2 {
                page-break-after: avoid;
            }
            
            table {
                page-break-inside: avoid;
            }
        }
    </style>
</head>
<body>
    ${htmlContent}
</body>
</html>`;
}

// Export functions to global namespace for access
if (typeof window !== 'undefined') {
    window.AutoDoc = window.AutoDoc || {};
    window.AutoDoc.downloadEtpPreview = downloadEtpDocument;
    window.AutoDoc.enhanceEtpPreviewBlocks = enhanceEtpPreviewBlocks;
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

// REMOVIDO: consultative-options (auto-avanço). O servidor decide transições.
// Esta função não deve mais disparar nada automaticamente.
async function generateConsultativeOptions() {
    return null;
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
function addToRecentItems(name, type, isInitial = false, sessionId = null) {
    const recentItemsContainer = document.querySelector('.recent-items');
    const iconClass = type === 'chat' ? 'fas fa-comments' : 'fas fa-file-alt';
    
    const newItem = document.createElement('div');
    newItem.className = 'recent-item';
    newItem.dataset.type = type; // Importante para a busca e para abrir a conversa
    newItem.dataset.sessionId = sessionId; // Store session_id
    
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
            const sid = newItem.dataset.sessionId;
            if (sid) {
                openConversation(sid);
            } else {
                startNewConversation(type, name);
            }
        }
    });

    // Adiciona no topo (novos) ou no final (iniciais)
    if (isInitial) {
        recentItemsContainer.appendChild(newItem);
    } else {
        recentItemsContainer.insertBefore(newItem, recentItemsContainer.firstChild);
    }
}

// Load conversation history from backend
async function loadConversationHistory() {
    try {
        const response = await fetch('/api/etp-dynamic/list', {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (!response.ok || !data.success) {
            console.error('Failed to load conversation history:', data.error);
            return;
        }
        
        console.log('[LIST] Loaded', data.conversations.length, 'conversations');
        
        // Clear existing items
        const recentItemsContainer = document.querySelector('.recent-items');
        recentItemsContainer.innerHTML = '';
        
        // Add conversations to sidebar with conversation_id
        data.conversations.forEach(conv => {
            addToRecentItems(conv.title, 'document', true, conv.id);
        });
    } catch (error) {
        console.error('Error loading conversation history:', error);
    }
}

// Open existing conversation
async function openConversation(conversationId) {
    try {
        const response = await fetch(`/api/etp-dynamic/open/${conversationId}`, {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Erro ao abrir conversa');
        }
        
        console.log('[OPEN] Opening conversation:', conversationId, 'with', data.messages.length, 'messages');
        
        // Set global conversation ID
        setConversationId(data.id);
        
        // Show chat view and clear messages
        showChatView();
        chatMessagesContainer.innerHTML = '';
        
        // Update UI
        currentConversation.type = 'document';
        currentConversation.title = data.title;
        chatTitle.textContent = data.title;
        
        // Initialize state
        etpState = { 
            conversationId: data.id,
            questionIndex: 0, 
            answers: {}, 
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
        
        // Render all messages from database
        data.messages.forEach(msg => {
            const role = msg.role === 'user' ? 'user' : 'ai';
            addMessage(msg.content, role);
        });
        
        userInput.focus();
        
    } catch (error) {
        console.error('Error opening conversation:', error);
        alert('Erro ao abrir conversa: ' + error.message);
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
async function renameItem(button) {
    const recentItem = originalParent;
    const itemNameEl = recentItem.querySelector('.item-name');
    const currentName = itemNameEl.textContent;
    const conversationId = recentItem.dataset.sessionId; // Actually stores conversation_id now
    
    const newName = prompt('Digite o novo nome:', currentName);
    if (!newName || newName.trim() === '' || newName === currentName) {
        closeAllMenus();
        return;
    }
    
    try {
        const response = await fetch('/api/etp-dynamic/rename', {
            method: 'PATCH',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                conversation_id: conversationId,
                title: newName.trim()
            })
        });
        
        const data = await response.json();
        
        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Erro ao renomear conversa');
        }
        
        // Update UI with persisted name
        itemNameEl.textContent = data.title;
        
        // Update current conversation title if it's the active one
        if (getConversationId() === conversationId) {
            currentConversation.title = data.title;
            chatTitle.textContent = data.title;
        }
        
        console.log('[RENAME] Renamed conversation:', conversationId, 'to', data.title);
        
    } catch (error) {
        console.error('Error renaming conversation:', error);
        alert('Erro ao renomear conversa: ' + error.message);
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
            credentials: 'include',
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

// === DOCUMENT GENERATION FEATURES ===
// Funções para gerar documento ETP e exibir links de download

// REQUIREMENT 2: Removed phase label from UI
// function updateStageBadge(stage) {
//     const el = document.getElementById('stage-badge');
//     if (!el) return;
//     el.textContent = `Fase: ${stage}`;
// }

// Alias para adicionar mensagem do assistente
function appendAssistantMessage(text) {
    addMessage(text, 'ai');
}

// Gera documento ETP baseado na sessão atual
async function generateDocument(sessionId) {
    try {
        const res = await fetch('/api/etp-dynamic/generate-document', {
            method: 'POST',
            credentials: 'include',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ session_id: sessionId })
        });
        const data = await res.json();
        if (data.success === false) { 
            alert(`Erro: ${data.error}`); 
            return; 
        }
        appendAssistantMessage(data.ai_response || data.message || 'Documento gerado.');
        if (data.doc_id) {
            const htmlUrl = `/api/etp-dynamic/document/${data.doc_id}/html`;
            const docxUrl = `/api/etp-dynamic/document/${data.doc_id}/download-docx`;
            const panel = document.getElementById('doc-actions');
            if (panel) {
                panel.innerHTML = `
                    <a href="${htmlUrl}" target="_blank">Ver HTML</a> |
                    <a href="${docxUrl}">Baixar DOCX</a>
                `;
            }
        }
    } catch (e) { 
        console.error(e); 
        alert('Falha ao gerar documento.'); 
    }
}