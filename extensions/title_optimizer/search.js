const host = 'lista.mercadolivre.com.br';
let searching = false;

function readPage() {
    const records = [];
    for (const card of document.querySelectorAll('li.ui-search-layout__item')) {
        if (!card.getClientRects().length || /\b(patrocinado|publicidade|promovido)\b/i.test(card.innerText)) continue;
        const heading = card.querySelector('h2, h3');
        const link = heading?.closest('a[href]') || heading?.querySelector('a[href]');
        if (heading?.innerText && link) records.push({ title: heading.innerText, url: link.href });
    }
    const next = document.querySelector('a[rel="next"], .andes-pagination__button--next a');
    return { records, next: next?.href };
}

async function navigate(tabId, url) {
    await new Promise((resolve, reject) => {
        const finish = (error) => {
            clearTimeout(timer);
            chrome.tabs.onUpdated.removeListener(updated);
            if (error) reject(error);
            else resolve();
        };
        const updated = (id, change) => {
            if (id === tabId && change.status === 'complete') finish();
        };
        const timer = setTimeout(() => finish(new Error('tempo esgotado')), 12000);
        chrome.tabs.onUpdated.addListener(updated);
        chrome.tabs.update(tabId, { url }).catch(finish);
    });
}

async function search(query) {
    const tab = await chrome.tabs.create({ active: false });
    const records = [];
    let next = 'https://' + host + '/' + encodeURIComponent(query.trim().replace(/\s+/g, '-'));
    const visited = new Set();
    try {
        while (next && !visited.has(next) && visited.size < 3 && records.length < 150) {
            const url = new URL(next);
            if (url.origin !== 'https://' + host) break;
            visited.add(next);
            await navigate(tab.id, next);
            const [{ result }] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: readPage });
            if (!result.records.length) break;
            records.push(...result.records);
            next = result.next;
        }
    } catch {
        return { records, error: 'A busca foi interrompida pelo navegador ou pelo Mercado Livre.' };
    } finally {
        await chrome.tabs.remove(tab.id).catch(() => {});
    }
    return records.length ? { records } : { error: 'Não foi possível ler resultados da busca do Mercado Livre.' };
}

chrome.runtime.onMessage.addListener((message, sender, reply) => {
    const url = new URL(sender.url || 'about:blank');
    if (url.origin !== 'https://app.keiperconsultoria.com.br' || !/^\/otimizador-titulos(?:\/\d+)?$/.test(url.pathname)) return;
    if (typeof message.query !== 'string' || !message.query.trim() || message.query.length > 240) return;
    if (searching) {
        reply({ error: 'Já há uma busca em andamento.' });
        return;
    }
    searching = true;
    search(message.query).then(reply).catch(() => reply({ error: 'Falha ao abrir a busca.' })).finally(() => { searching = false; });
    return true;
});
