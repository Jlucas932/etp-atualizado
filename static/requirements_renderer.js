export function renderRequirements(list) {
  const ol = document.createElement('ol');
  ol.className = 'req-list';
  (list || []).forEach(req => {
    const li = document.createElement('li');
    const badge = document.createElement('span');
    const crit = req.criticidade === 'Obrigatório' ? 'badge--obg' : 'badge--des';
    badge.className = `badge ${crit}`;
    badge.textContent = `(${req.criticidade || 'Desejável'})`;
    const text = document.createElement('span');
    text.className = 'req-text';
    text.textContent = ` ${req.descricao || req.titulo || ''}`;
    li.append(badge, text);
    ol.appendChild(li);
  });
  return ol;
}

export function renderStrategies(list) {
  const wrap = document.createElement('div');
  wrap.className = 'strategy-grid';
  (list || []).forEach(s => {
    const card = document.createElement('div');
    card.className = 'card';
    const h = document.createElement('h4'); h.textContent = s.titulo || '';
    const prosT = document.createElement('strong'); prosT.textContent = 'Prós:';
    const pros = document.createElement('ul'); (s.pros||[]).forEach(p=>{const li=document.createElement('li'); li.textContent=p; pros.appendChild(li);});
    const consT = document.createElement('strong'); consT.textContent = 'Contras:';
    const cons = document.createElement('ul'); (s.contras||[]).forEach(c=>{const li=document.createElement('li'); li.textContent=c; cons.appendChild(li);});
    card.append(h, prosT, pros, consT, cons);
    wrap.appendChild(card);
  });
  return wrap;
}
