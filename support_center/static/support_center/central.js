(() => {
  'use strict';

  async function copyText(text) {
    if (!text) return false;
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
    const area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', 'readonly');
    area.style.position = 'fixed';
    area.style.left = '-10000px';
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand('copy');
    area.remove();
    return ok;
  }

  document.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-copy-target]');
    if (!button) return;
    const target = document.getElementById(button.dataset.copyTarget || '');
    if (!target) return;
    const original = button.textContent;
    try {
      const ok = await copyText(target.value || target.textContent || '');
      button.textContent = ok ? 'Copiado' : 'Selecione e copie';
    } catch (_) {
      button.textContent = 'Selecione e copie';
    }
    window.setTimeout(() => { button.textContent = original; }, 1800);
  });
})();
