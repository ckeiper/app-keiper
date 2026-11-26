/* Kept self-contained because Chrome serializes this function into the search tab. */
function readTitleSearchPage() {
    const records = [];
    const cards = document.querySelectorAll('li.ui-search-layout__item');
    let excludedSponsored = 0;
    for (const card of cards) {
        if (!card.getClientRects().length) continue;
        const text = card.innerText || '';
        const ads = card.querySelector('[class*="advertising"], [class*="promoted"], [data-sponsored="true"]');
        if (ads || /\b(patrocinado|publicidade|promovido|sponsored)\b/i.test(text)) { excludedSponsored++; continue; }
        const heading = card.querySelector('h2, h3');
        const anchor = heading?.closest('a[href]') || heading?.querySelector('a[href]') || card.querySelector('a.poly-component__title');
        const raw = anchor?.href;
        let url;
        try { url = new URL(raw); } catch { continue; }
        // Tracking and click URLs are deliberately excluded; never resolve ads redirects.
        if (url.protocol !== 'https:' || !['www.mercadolivre.com.br', 'produto.mercadolivre.com.br'].includes(url.host)) continue;
        const title = (heading?.innerText || anchor?.innerText || '').trim();
        if (title) records.push({ title, url: url.href });
    }
    const next = document.querySelector('a[rel="next"], .andes-pagination__button--next:not(.andes-pagination__button--disabled) a');
    const body = (document.body?.innerText || '').slice(0, 10000);
    const error = !cards.length && /error accediendo|access denied|acesso negado|não foi possível|verifique que|confirme que|captcha|não sou um robô/i.test(body);
    return { records, next: next?.href || null, excludedSponsored, state: error ? 'unavailable' : cards.length ? 'read' : 'empty' };
}
