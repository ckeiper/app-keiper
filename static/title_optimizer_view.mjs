import { analyze } from './title_optimizer.mjs';

const form = document.querySelector('#title-search');
const status = document.querySelector('#title-status');
const results = document.querySelector('#title-results');
const submit = form.querySelector('button');
let pending;

function append(parent, tag, text) {
    const child = document.createElement(tag);
    child.textContent = text;
    parent.append(child);
    return child;
}

function show(input, analysis) {
    results.replaceChildren();
    results.hidden = false;
    append(results, 'h3', 'Sugestões de título');
    append(results, 'p', 'Original · ' + input.original);
    if (!analysis.suggestions.length) append(results, 'p', 'Sem sugestões com os dados encontrados.');
    for (const title of analysis.suggestions) {
        const row = append(results, 'p', title + ' · ' + Array.from(title).length + '/60 ');
        append(row, 'button', 'Copiar título').addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(title);
                status.textContent = 'Título copiado.';
            } catch {
                status.textContent = 'Selecione o título para copiar.';
            }
        });
    }
    append(results, 'h3', 'Termos na amostra');
    const keywords = append(results, 'ol', '');
    for (const { term, count } of analysis.keywords) {
        append(keywords, 'li', term + ' · ' + count + ' de ' + analysis.competitors.length);
    }
    const details = append(results, 'details', '');
    append(details, 'summary', 'Concorrentes analisados (' + analysis.competitors.length + ')');
    const list = append(details, 'ol', '');
    for (const competitor of analysis.competitors) {
        const anchor = append(append(list, 'li', ''), 'a', competitor.title);
        anchor.href = competitor.url;
        anchor.target = '_blank';
        anchor.rel = 'noopener noreferrer';
    }
}

form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (pending) return;
    const input = Object.fromEntries(Array.from(new FormData(form), ([key, value]) => [key, value.trim()]));
    if (!input.product || !input.original) {
        status.textContent = 'Informe o título original e o produto.';
        return;
    }
    const id = crypto.randomUUID();
    const timer = setTimeout(() => {
        pending = null;
        submit.disabled = false;
        status.textContent = 'A extensão não respondeu. Confira a instalação e tente novamente.';
    }, 45000);
    pending = { id, timer, input };
    submit.disabled = true;
    results.hidden = true;
    status.textContent = 'Buscando concorrentes no Mercado Livre…';
    window.postMessage({ type: 'keiper-title-search', id, query: [input.product, input.brand, input.model].filter(Boolean).join(' ') }, location.origin);
});

window.addEventListener('message', (event) => {
    if (event.source !== window || event.origin !== location.origin || !pending) return;
    const response = event.data;
    if (response?.type !== 'keiper-title-results' || response.id !== pending.id) return;
    const { timer, input } = pending;
    clearTimeout(timer);
    pending = null;
    submit.disabled = false;
    if (!Array.isArray(response.records) || !response.records.length) {
        status.textContent = response.error || 'A busca não retornou anúncios.';
        return;
    }
    const analysis = analyze(input, response.records);
    status.textContent = (response.error ? response.error + ' ' : '') +
        analysis.competitors.length + ' anúncios comparáveis na amostra da busca.';
    show(input, analysis);
});
