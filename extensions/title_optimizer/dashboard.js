window.addEventListener('message', async (event) => {
    if (event.source !== window || event.origin !== location.origin) return;
    const message = event.data;
    if (message?.type !== 'keiper-title-search' || typeof message.query !== 'string') return;
    let result;
    try {
        result = await chrome.runtime.sendMessage({ query: message.query });
    } catch {
        result = { error: 'A extensão está indisponível. Recarregue a página e tente novamente.' };
    }
    window.postMessage({ type: 'keiper-title-results', id: message.id, ...result }, location.origin);
});
