(() => {
  const status = document.getElementById('qa-refresh-status');
  const content = document.getElementById('qa-live-content');
  if (!content) return;
  let refreshing = false;

  async function update() {
    if (refreshing || document.hidden || content.contains(document.activeElement)) return;
    refreshing = true;
    try {
      const response = await fetch(location.href, {cache: 'no-store'});
      if (response.redirected) {
        if (status) status.textContent = 'A sessão expirou. Recarregue para entrar novamente.';
        return;
      }
      if (!response.ok) throw new Error('Atualização indisponível');
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      const next = page.getElementById(content.id);
      if (next && !content.contains(document.activeElement) && next.innerHTML !== content.innerHTML) {
        content.replaceChildren(...next.childNodes);
      }
      if (status) status.textContent = 'Atualização automática a cada 8 segundos';
    } catch (_) {
      if (status) status.textContent = 'Conexão indisponível. O painel vai tentar novamente.';
    } finally {
      refreshing = false;
    }
  }

  setInterval(update, 8000);
  document.addEventListener('visibilitychange', update);
})();
