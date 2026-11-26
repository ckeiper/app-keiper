importScripts('collector.js');
const host = 'lista.mercadolivre.com.br';
let searching = false;

async function navigate(tabId, url) {
    await new Promise((resolve, reject) => {
        let done = false;
        const finish = error => {
            if (done) return;
            done = true;
            clearTimeout(timer);
            chrome.tabs.onUpdated.removeListener(updated);
            chrome.tabs.onRemoved.removeListener(removed);
            if (error) reject(error); else resolve();
        };
        const updated = (id, change) => { if (id === tabId && change.status === 'complete') finish(); };
        const removed = id => { if (id === tabId) finish(new Error('A aba de pesquisa foi fechada.')); };
        const timer = setTimeout(() => finish(new Error('O Mercado Livre não terminou de carregar a busca.')), 15000);
        chrome.tabs.onUpdated.addListener(updated);
        chrome.tabs.onRemoved.addListener(removed);
        chrome.tabs.update(tabId, { url }).catch(finish);
    });
}

async function search(query) {
    const tab = await chrome.tabs.create({ active: false });
    const records = []; const seen = new Set(); const visited = new Set();
    let next = 'https://' + host + '/' + encodeURIComponent(query.trim().replace(/\s+/g, '-'));
    let excludedSponsored = 0; let error = '';
    try {
        while (next && !visited.has(next) && visited.size < 5 && records.length < 240) {
            const url = new URL(next);
            if (url.origin !== 'https://' + host || url.username || url.password) { error = 'A paginação retornou um endereço não permitido.'; break; }
            visited.add(next);
            await navigate(tab.id, next);
            const execution = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: readTitleSearchPage });
            const result = execution?.[0]?.result;
            if (!result || result.state === 'unavailable') { error = 'O Mercado Livre não disponibilizou a busca. Nenhuma tentativa automática adicional foi feita.'; break; }
            if (!result.records.length) { error = 'A página não apresentou resultados legíveis. A coleta precisa ser conferida.'; break; }
            excludedSponsored += result.excludedSponsored;
            for (const record of result.records) {
                const clean = new URL(record.url); clean.hash = '';
                // Keep offer identifiers for the analyzer; strip tracking only for pagination dedup.
                const key = clean.origin + clean.pathname + (clean.searchParams.get('pdp_filters') || clean.searchParams.get('item_id') || '');
                if (!seen.has(key)) { seen.add(key); records.push(record); }
                if (records.length >= 240) break;
            }
            next = result.next;
        }
    } catch {
        error = 'A coleta foi interrompida pelo navegador ou pelo Mercado Livre.';
    } finally {
        await chrome.tabs.remove(tab.id).catch(() => {});
    }
    return { records, error, pages: visited.size, excludedSponsored, collectedAt: new Date().toISOString(), query };
}

chrome.runtime.onMessage.addListener((message, sender, reply) => {
    let url;
    try { url = new URL(sender.url || 'about:blank'); } catch { return; }
    if (sender.id !== chrome.runtime.id || url.origin !== 'https://app.keiperconsultoria.com.br' || !/^\/otimizador-titulos(?:\/\d+)?$/.test(url.pathname)) return;
    if (message?.type === 'ping') { reply({ ready: true, version: '0.2.0' }); return; }
    if (message?.type !== 'search' || typeof message.query !== 'string' || !message.query.trim() || message.query.length > 240) return;
    if (searching) { reply({ error: 'Já há uma busca em andamento.' }); return; }
    searching = true;
    search(message.query).then(reply).catch(() => reply({ error: 'Falha ao abrir a busca.' })).finally(() => { searching = false; });
    return true;
});
