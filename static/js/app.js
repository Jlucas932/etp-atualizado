import { renderRequirements, renderStrategies } from './requirements_renderer.js';

const userEl = document.querySelector('#user-badge');
const chatEl = document.querySelector('#chat');
const btnNew = document.querySelector('#btn-new');
const btnNewConv = document.querySelector('#btn-new-conv');

async function loadUser() {
  try {
    const r = await fetch('/api/auth/current');
    if (r.ok) { const j = await r.json(); userEl.textContent = j?.username || 'demo_user'; }
  } catch (e) { console.warn('user load failed', e); userEl.textContent = 'demo_user'; }
}
loadUser();

function safeAppend(el) { if (el) { chatEl.appendChild(el); chatEl.scrollTop = chatEl.scrollHeight; } }

function handleAiPayload(payload) {
  try {
    if (payload?.requisitos?.length) return safeAppend(renderRequirements(payload.requisitos));
    if (payload?.estrategias?.length) return safeAppend(renderStrategies(payload.estrategias));
    if (typeof payload?.text === 'string' && !/justificativa|nota técnica/i.test(payload.text)) {
      const p = document.createElement('p'); p.textContent = payload.text; return safeAppend(p);
    }
  } catch (e) { console.error('render error', e); }
}

btnNew?.addEventListener('click', async () => {
  try { await fetch('/api/etp-dynamic/new', { method:'POST' }); /* refresh UI conforme app */ } catch(e){ console.error(e); }
});
btnNewConv?.addEventListener('click', async () => {
  try { await fetch('/api/etp-dynamic/new', { method:'POST' }); } catch(e){ console.error(e); }
});

// Exporte se o front usar via outras partes:
export { handleAiPayload };
