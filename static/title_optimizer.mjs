const stop = new Set('a as o os e de do da dos das para com em por um uma no na nos nas'.split(' '));
const normalized = (text) => text.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
const tokens = (text) => text.match(/[\p{L}\p{N}]+(?:[-.,/][\p{L}\p{N}]+)*/gu) || [];
const size = (text) => Array.from(text).length;

export function analyze({ product, brand, model, original }, records) {
    const base = [product, brand, model].filter(Boolean).join(' ').trim();
    const identity = new Set(tokens(base).map(normalized));
    const known = new Set(tokens(original).map(normalized));
    const competitors = new Map();
    for (const record of records.slice(0, 200)) {
        if (typeof record?.title !== 'string' || typeof record.url !== 'string') continue;
        let url;
        try { url = new URL(record.url); } catch { continue; }
        const hosts = ['www.mercadolivre.com.br', 'produto.mercadolivre.com.br'];
        if (url.protocol !== 'https:' || !hosts.includes(url.host) || url.username || url.password) continue;
        const title = record.title.trim().slice(0, 300);
        const words = new Set(tokens(title).map(normalized));
        if (!Array.from(identity).filter(word => !stop.has(word)).every(word => words.has(word))) continue;
        const key = url.hostname + url.pathname;
        if (!competitors.has(key)) competitors.set(key, { title, url: 'https://' + key });
        if (competitors.size === 50) break;
    }
    const terms = new Map();
    for (const competitor of competitors.values()) {
        const seen = new Set();
        for (const term of tokens(competitor.title)) {
            const key = normalized(term);
            if (identity.has(key) || stop.has(key) || seen.has(key) || key.length < 2) continue;
            seen.add(key);
            if (!terms.has(key)) terms.set(key, { term, count: 0, confirmed: known.has(key) });
            terms.get(key).count += 1;
        }
    }
    const keywords = Array.from(terms.values()).sort((a, b) => b.count - a.count || a.term.localeCompare(b.term, 'pt-BR')).slice(0, 10);
    const suggestions = new Set();
    const confirmed = keywords.filter(({ confirmed }) => confirmed).map(({ term }) => term);
    if (base && size(base) <= 60 && competitors.size) {
        for (let start = 0; start <= confirmed.length && suggestions.size < 3; start += 1) {
            let title = base;
            for (const term of confirmed.slice(start)) {
                if (size(title + ' ' + term) <= 60) title += ' ' + term;
            }
            suggestions.add(title);
        }
    }
    return { competitors: Array.from(competitors.values()), keywords, suggestions: Array.from(suggestions) };
}
