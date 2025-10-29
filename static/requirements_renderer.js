// Renderização de requisitos como lista simples por etapa
export function renderRequirements(raw) {
  const lines = raw
    .split(/\r?\n/)
    .map(l => l.trim())
    .filter(Boolean);

  const items = [];
  let buf = [];
  for (const l of lines) {
    if (/^\d+[\).\s]/.test(l)) {
      if (buf.length) items.push(buf.join(' '));
      buf = [l.replace(/^\d+[\).\s]/, '').trim()];
    } else if (/^[-•]/.test(l)) {
      if (buf.length) items.push(buf.join(' '));
      buf = [l.replace(/^[-•]\s?/, '').trim()];
    } else {
      buf.push(l);
    }
  }
  if (buf.length) items.push(buf.join(' '));

  const ul = document.createElement('ul');
  ul.className = 'req-list';
  items.forEach(t => {
    const li = document.createElement('li');
    li.textContent = t;
    ul.appendChild(li);
  });
  return ul;
}
    // Use backend-provided intro, justification, and rationale ONLY - no defaults
    const intro = intro_paragraph || '';
    const justif = justification || rationale_paragraph || '';  // justification replaces rationale
    
    // Normalize text for deduplication
    function normalizeForDedup(text) {
        return text.toLowerCase().trim().replace(/[.,:;!?]+$/, '');
    }
    
    // Filter and deduplicate requirements - NO question blocking (generator handles this)
    const seen = new Set();
    const validRequirements = requirements.filter(r => {
        const text = typeof r === 'string' ? r : (r.text || r.descricao || r.requirement || String(r));
        const trimmed = text.trim();
        
        // Block duplicates only
        const normalized = normalizeForDedup(trimmed);
        if (seen.has(normalized)) {
            console.log('[REQUIREMENTS_RENDERER] Blocked duplicate item:', trimmed);
            return false;
        }
        
        seen.add(normalized);
        return true;
    });
    
    // If all items were blocked or empty, trigger regeneration
    if (validRequirements.length === 0) {
        console.warn('[REQUIREMENTS_RENDERER] No valid requirements - triggering regeneration');
        // Trigger regeneration via custom event
        if (typeof window !== 'undefined') {
            window.dispatchEvent(new CustomEvent('requirements-empty', {
                detail: { message: 'Reprocessando requisitos…' }
            }));
        }
        return '⏳ Reprocessando requisitos…';
    }
    
    // Build enhanced requirement list with chips
    const lista = validRequirements
        .map((r, i) => {
            // Handle both old format (text) and new format (descricao, metrica, sla, aceite)
            let text, metrica, sla, aceite, opcoes, needsInput, missing;
            
            if (typeof r === 'string') {
                text = r;
            } else {
                text = r.descricao || r.text || r.requirement || String(r);
                metrica = r.metrica;
                sla = r.sla;
                aceite = r.aceite;
                opcoes = r.opcoes || [];
                needsInput = r.needs_input || false;
                missing = r.missing || [];
            }
            
            let result = `${i + 1}. ${text.trim().replace(/\.$/, '')}`;
            
            // Add chips if enhanced data exists
            const chips = [];
            if (metrica && metrica.valor !== undefined) {
                chips.push(`📊 ${metrica.tipo || 'Métrica'}: ${metrica.valor} ${metrica.unidade || ''}`);
            }
            if (sla && sla.valor !== undefined) {
                chips.push(`⏱️ SLA: ${sla.valor} ${sla.unidade || ''} (${sla.janela || 'n/a'})`);
            }
            if (aceite) {
                chips.push(`✅ Aceite: ${aceite.substring(0, 60)}${aceite.length > 60 ? '...' : ''}`);
            }
            
            if (chips.length > 0) {
                result += '\n   ' + chips.join(' | ');
            }
            
            // Show options if available
            if (opcoes && opcoes.length > 0) {
                const opcoesText = opcoes.map(o => `${o.valor} ${o.unidade || ''}`).join(', ');
                result += `\n   💡 Opções: ${opcoesText}`;
            }
            
            // Warn if needs input
            if (needsInput && missing.length > 0) {
                result += `\n   ⚠️ ATENÇÃO: Falta ${missing.join(', ')}`;
            }
            
            return result;
        })
        .join('\n\n');
    
    // Build response with only what backend provides
    let response = '';
    if (intro) response += intro + '\n\n';
    response += lista;
    if (justif) response += '\n\n' + justif;
    
    return response;
}

// Renderização principal de requisitos - retorna apenas texto conversacional
function renderRequirementsMessage(payload) {
    if (!payload || !payload.requirements || !Array.isArray(payload.requirements)) {
        return 'Nenhum requisito disponível.';
    }
    
    return buildConversationalRequirements({
        necessityText: payload.necessity || payload.necessityText || '',
        requirements: payload.requirements
    });
}

// Função de renderização para mensagens do assistente
function renderAssistantMessage(data) {
    // Para requisitos, retornar texto conversacional puro
    if (data.kind && data.kind.startsWith('requirements_')) {
        const text = renderRequirementsMessage(data);
        const container = document.createElement('div');
        container.className = 'ai-message-content';
        container.textContent = text;
        return container;
    }
    
    // Renderização padrão para outras mensagens
    const messageDiv = document.createElement('div');
    messageDiv.className = 'ai-message-content';
    messageDiv.textContent = data.message || data.ai_response || 'Resposta não disponível';
    return messageDiv;
}

// Smart renderer for lists with OL/UL and badges (HOTFIX)
function renderTextSmart(containerEl, text, stage) {
    // 1) se houver linhas numeradas "N. ..." → OL
    const lines = (text || "").split(/\r?\n/).map(l => l.trim()).filter(Boolean);
    const hasNumbered = lines.some(l => /^\d+\.\s+/.test(l));
    const hasBullets = lines.some(l => /^[•\-]\s+/.test(l));

    // helper para escapar HTML básico
    const esc = s => s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
    const badge = s => {
        const low = s.toLowerCase();
        if (low.includes("(obrigatório)")) return s.replace(/\(obrigatório\)/ig, '<span class="badge-od badge-obr">(Obrigatório)</span>');
        if (low.includes("(desejável)")) return s.replace(/\(desejável\)/ig, '<span class="badge-od badge-des">(Desejável)</span>');
        return s;
    };

    // Limpa container
    containerEl.innerHTML = "";

    // Se for strategies, formatar cards simples a partir do texto padrão do backend
    if (stage === 'solution_strategies' && !hasNumbered && lines.some(l => /^•\s+/.test(l))) {
        let block = document.createElement('div');
        block.className = "formatted";
        // converte:
        // • Nome
        //   Quando usar: ...
        //   Prós: a, b
        //   Contras: x, y
        // em blocos separados
        let curr = null;
        lines.forEach(l => {
            if (/^•\s+/.test(l)) {
                curr && block.appendChild(curr);
                curr = document.createElement('div');
                curr.style.marginBottom = "10px";
                let title = document.createElement('div');
                title.style.fontWeight = "600";
                title.textContent = l.replace(/^•\s+/, "");
                curr.appendChild(title);
            } else if (curr) {
                let p = document.createElement('div');
                p.textContent = l;
                curr.appendChild(p);
            }
        });
        curr && block.appendChild(curr);
        containerEl.appendChild(block);
        return;
    }

    if (hasNumbered) {
        const ol = document.createElement('ol');
        lines.forEach(l => {
            if (/^\d+\.\s+/.test(l)) {
                const li = document.createElement('li');
                li.innerHTML = badge(esc(l.replace(/^\d+\.\s+/, "")));
                ol.appendChild(li);
            } else {
                // linha complementar ao item anterior
                const last = ol.lastElementChild;
                if (last) {
                    last.innerHTML += "<br>"+badge(esc(l));
                }
            }
        });
        containerEl.appendChild(ol);
        return;
    }
    if (hasBullets) {
        const ul = document.createElement('ul');
        lines.forEach(l => {
            const li = document.createElement('li');
            li.innerHTML = badge(esc(l.replace(/^[•\-]\s+/, "")));
            ul.appendChild(li);
        });
        containerEl.appendChild(ul);
        return;
    }
    // fallback: respeita quebras de linha
    const pre = document.createElement('pre');
    pre.className = "formatted";
    pre.textContent = text || "";
    containerEl.appendChild(pre);
}

// Exportar para uso global
if (typeof window !== 'undefined') {
    window.renderRequirementsMessage = renderRequirementsMessage;
    window.renderAssistantMessage = renderAssistantMessage;
    window.renderTextSmart = renderTextSmart;
}
