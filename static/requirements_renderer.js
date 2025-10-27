// UMD simples: expõe em window.renderTextSmart (sem ESM)
(function (global) {
  function renderTextSmart(containerEl, text, stage) {
    const esc = s => s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
    const badge = s => {
      const low = s.toLowerCase();
      if (low.includes("(obrigatório)")) return s.replace(/\(obrigatório\)/ig, '<span class="badge-od badge-obr">(Obrigatório)</span>');
      if (low.includes("(desejável)"))  return s.replace(/\(desejável\)/ig,  '<span class="badge-od badge-des">(Desejável)</span>');
      return s;
    };

    const txt = (text || "").replace(/\r\n/g, "\n");
    const lines = txt.split("\n");

    const hasNumbered = lines.some(l => /^\s*\d+\.\s+/.test(l));
    const hasBullets  = lines.some(l => /^\s*[•\-]\s+/.test(l));

    containerEl.innerHTML = "";
    if (stage === 'solution_strategies' && lines.some(l => /^\s*•\s+/.test(l))) {
      // cards simples por estratégia
      let block = document.createElement('div');
      block.className = "formatted";
      let curr = null;
      lines.forEach(l => {
        if (/^\s*•\s+/.test(l)) {
          curr && block.appendChild(curr);
          curr = document.createElement('div');
          curr.style.marginBottom = "10px";
          const title = document.createElement('div');
          title.style.fontWeight = "600";
          title.textContent = l.replace(/^\s*•\s+/, "");
          curr.appendChild(title);
        } else if (curr) {
          const p = document.createElement('div');
          p.textContent = l.trim();
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
        if (/^\s*\d+\.\s+/.test(l)) {
          const li = document.createElement('li');
          li.innerHTML = badge(esc(l.replace(/^\s*\d+\.\s+/, "")));
          ol.appendChild(li);
        } else {
          const last = ol.lastElementChild;
          if (last && l.trim()) last.innerHTML += "<br>" + badge(esc(l));
        }
      });
      containerEl.appendChild(ol);
      return;
    }

    if (hasBullets) {
      const ul = document.createElement('ul');
      lines.forEach(l => {
        const li = document.createElement('li');
        li.innerHTML = badge(esc(l.replace(/^\s*[•\-]\s+/, "")));
        ul.appendChild(li);
      });
      containerEl.appendChild(ul);
      return;
    }

    const pre = document.createElement('pre');
    pre.className = "formatted";
    pre.textContent = txt;
    containerEl.appendChild(pre);
  }
  global.renderTextSmart = renderTextSmart;
})(window);
