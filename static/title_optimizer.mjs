const stop = new Set('a as o os e de do da dos das para com em por um uma no na nos nas'.split(' '));
export const normalized = text => text.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
export const tokens = text => text.match(/[\p{L}\p{N}]+(?:[-.,/][\p{L}\p{N}]+)*/gu) || [];
const size = text => Array.from(text).length;
// Exact identity matching avoids treating a different capacity/model as comparable.
export function analyze({ product = '', brand = '', model = '', original = '', confirmed = [] }, records) {
    const parts = [product, brand, model].map(text => text.trim()).filter(Boolean);
    const baseWords = new Set();
    const base = parts.flatMap(tokens).filter(term => { const key = normalized(term); if (baseWords.has(key)) return false; baseWords.add(key); return true; }).join(' ');
    const identity = new Set(tokens(base).map(normalized));
    const known = new Set([...tokens(original), ...confirmed.flatMap(tokens)].map(normalized));
    const competitors = new Map();
    for (const record of Array.isArray(records) ? records.slice(0, 240) : []) {
        if (typeof record?.title !== 'string' || typeof record.url !== 'string' || record.sponsored === true) continue;
        let url;
        try { url = new URL(record.url); } catch { continue; }
        if (url.protocol !== 'https:' || !['www.mercadolivre.com.br', 'produto.mercadolivre.com.br'].includes(url.host) || url.username || url.password) continue;
        const title = record.title.trim().slice(0, 300);
        const words = new Set(tokens(title).map(normalized));
        if (!Array.from(identity).filter(word => !stop.has(word)).every(word => words.has(word))) continue;
        // MLBU pages identify different offers with item_id; preserve it when present.
        const item = url.searchParams.get('item_id') || url.searchParams.get('pdp_filters')?.match(/item_id:(MLB\d+)/)?.[1];
        const id = url.pathname.match(/MLB-?(\d{6,})/i)?.[1];
        const key = item && /^MLB\d+$/.test(item) ? item : id ? 'MLB'+id : url.hostname + url.pathname;
        if (item && /^MLB\d+$/.test(item)) { url.search = ''; url.searchParams.set('pdp_filters', 'item_id:'+item); }
        else url.search = '';
        url.hash = '';
        if (!competitors.has(key)) competitors.set(key, { title, url: url.href, position: competitors.size + 1 });
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
    const approved = keywords.filter(row => row.confirmed).map(row => row.term);
    const suggestions = new Set();
    if (base && size(base) <= 60 && competitors.size) {
        // Three complete, distinct arrangements where the available facts permit it.
        for (const order of [approved, [...approved].reverse(), [...approved.slice(1), ...approved.slice(0, 1)]]) {
            let title = base;
            for (const term of order) if (size(title+' '+term) <= 60) title += ' '+term;
            suggestions.add(title);
        }
    }
    const titles = Array.from(suggestions).slice(0, 3);
    const used = new Set(tokens(titles[0] || '').map(normalized));
    return { base, baseTooLong: size(base) > 60, competitors: Array.from(competitors.values()), keywords, suggestions: titles,
        overflow: keywords.filter(row => row.confirmed && !used.has(normalized(row.term))).map(row => row.term),
        sampleComplete: competitors.size >= 30 };
}
