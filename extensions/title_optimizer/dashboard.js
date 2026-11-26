window.addEventListener('message', async event => {
    if (event.source !== window || event.origin !== location.origin) return;
    const message = event.data;
    if (!['keiper-title-search', 'keiper-title-ping'].includes(message?.type) || typeof message.id !== 'string') return;
    let result;
    try {
        if (message.type === 'keiper-title-search' && (typeof message.query !== 'string' || !message.query.trim() || message.query.length > 240)) return;
        result = await chrome.runtime.sendMessage({ type: message.type === 'keiper-title-ping' ? 'ping' : 'search', query: message.query });
    } catch {
        result = { error: 'A extensão está indisponível. Recarregue a página e tente novamente.' };
    }
    window.postMessage({ type: message.type === 'keiper-title-ping' ? 'keiper-title-ready' : 'keiper-title-results', id: message.id, ...result }, location.origin);
});
