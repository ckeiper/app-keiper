import { analyze, tokens, normalized } from './title_optimizer.mjs';
const root = document.querySelector('.title-tool');
const form = document.querySelector('#title-search');
const status = document.querySelector('#title-status');
const results = document.querySelector('#title-results');
const submit = document.querySelector('#title-submit');
const extensionStatus = document.querySelector('#title-extension-status');
let pending; let current; let policy = { state: 'unknown', message: 'Categoria não verificada. Confira se os termos descrevem o modelo real antes de usar esse campo.' };
let confirmed = new Set(); let available = false;
let modelTerms = new Set();
const pingId = crypto.randomUUID();
const values = () => Object.fromEntries(Array.from(new FormData(form), ([key, value]) => [key, value.trim()]));
const fingerprint = input => JSON.stringify([input.original, input.product, input.brand, input.model]);
function append(parent, tag, text, className) {
    const child = document.createElement(tag); child.textContent = text;
    if (className) child.className = className;
    parent.append(child); return child;
}
function copyButton(parent, text, label) {
    const button = append(parent, 'button', label); button.type = 'button';
    button.addEventListener('click', async () => {
        try { await navigator.clipboard.writeText(text); status.textContent = 'Texto copiado.'; }
        catch { status.textContent = 'Não foi possível copiar automaticamente. Selecione o texto e copie.'; }
    });
}
function show() {
    const analysis = analyze({ ...current.input, confirmed: [...confirmed] }, current.records);
    results.replaceChildren(); results.hidden = false;
    append(results, 'h3', 'Sugestões de título');
    append(results, 'p', analysis.competitors.length + ' anúncios comparáveis · ' + current.pages + ' página(s) consultada(s) · ' + current.excludedSponsored + ' patrocinado(s) identificado(s) e excluído(s).', 'to-metrics');
    if (!analysis.sampleComplete) append(results, 'p', 'Amostra insuficiente: foram encontrados menos de 30 anúncios comparáveis. Os termos abaixo descrevem apenas esta amostra.', 'to-hint');
    if (current.error) append(results, 'p', current.error + ' Resultado parcial.', 'to-hint');
    const original = append(results, 'div', '', 'to-original');
    append(original, 'small', 'TÍTULO ORIGINAL · ' + Array.from(current.input.original).length + ' caracteres');
    append(original, 'div', current.input.original);
    const grid = append(results, 'div', '', 'to-suggestions');
    analysis.suggestions.forEach((title, index) => {
        const row = append(grid, 'article', '', 'to-suggestion');
        append(row, 'small', 'OPÇÃO ' + (index + 1) + ' · ' + Array.from(title).length + '/60');
        append(row, 'p', title); copyButton(row, title, 'Copiar título');
        const originalWords = new Set(tokens(current.input.original).map(normalized));
        const newWords = tokens(title).filter(term => !originalWords.has(normalized(term)));
        append(row, 'small', newWords.length ? 'Incluído: ' + newWords.join(', ') : 'Reorganização dos termos informados');
    });
    if (analysis.baseTooLong) append(results, 'p', 'Produto, marca e modelo ultrapassam 60 caracteres. Encurte a identificação preservando os dados essenciais.');
    else if (!analysis.suggestions.length) append(results, 'p', 'Nenhum anúncio comparável encontrado. Confira os campos e faça uma nova busca.');
    else if (analysis.suggestions.length < 3) append(results, 'p', 'Os dados confirmados permitem ' + analysis.suggestions.length + ' sugestão(ões) distinta(s). Confirme abaixo outros termos que se aplicam ao produto.', 'to-hint');
    append(results, 'h3', 'Palavras-chave encontradas');
    append(results, 'p', 'Ranking pela presença nos títulos da amostra. Não representa volume de buscas nem vendas.', 'to-hint');
    const table = append(results, 'table', '', 'to-keywords');
    const head = append(append(table, 'thead', ''), 'tr', '');
    ['Termo', 'Anúncios', 'Presença'].forEach(text => { const th = append(head, 'th', text); th.scope = 'col'; });
    const tbody = append(table, 'tbody', '');
    analysis.keywords.forEach(({term, count}) => { const tr = append(tbody, 'tr', ''); [term, count + '/' + analysis.competitors.length, Math.round(count / analysis.competitors.length * 100) + '%'].forEach(text => append(tr, 'td', text)); });
    if (!analysis.keywords.length) append(results, 'p', 'Sem termos adicionais nesta amostra.');
    const unconfirmed = analysis.keywords.filter(row => !tokens(current.input.original).map(normalized).includes(normalized(row.term)));
    if (unconfirmed.length) {
        const review = append(results, 'div', '', 'to-review'); append(review, 'h4', 'Quais termos também descrevem seu produto?');
        append(review, 'p', 'Marque somente características verdadeiras. As sugestões serão atualizadas sem repetir a busca.');
        unconfirmed.forEach(({term}) => {
            const label = append(review, 'label', ''); const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.checked = confirmed.has(term); label.append(checkbox); label.append(document.createTextNode(term));
            checkbox.addEventListener('change', () => { checkbox.checked ? confirmed.add(term) : confirmed.delete(term); const selected = term; show(); const target = Array.from(results.querySelectorAll('label')).find(label => label.textContent === selected)?.querySelector('input'); target?.focus(); });
        });
    }
    const extra = append(results, 'div', '', 'to-review'); append(extra, 'h4', 'Termos que não couberam no título');
    append(extra, 'p', analysis.overflow.length ? analysis.overflow.join(' · ') : 'Nenhum termo confirmado excedente.');
    append(extra, 'p', policy.message);
    if (policy.state === 'review' && analysis.overflow.length) {
        append(extra, 'p', 'Selecione apenas termos que descrevam o Modelo. Material, tamanho e quantidade podem ter campos próprios.');
        const preview = append(extra, 'p', '');
        const controls = append(extra, 'div', '');
        function updateModel() {
            const value = [current.input.model, ...analysis.overflow.filter(term => modelTerms.has(term))].filter(Boolean).join(' ');
            preview.textContent = value ? 'Sugestão para Modelo: ' + value : 'Selecione os termos que pertencem ao Modelo.';
            controls.replaceChildren();
            if (policy.max_length && Array.from(value).length > policy.max_length) append(controls, 'p', 'A sugestão ultrapassa o limite de ' + policy.max_length + ' caracteres da categoria.');
            else if (modelTerms.size) copyButton(controls, value, 'Copiar sugestão de Modelo');
        }
        analysis.overflow.forEach(term => {
            const label = append(extra, 'label', ''); const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.checked = modelTerms.has(term); label.append(checkbox); label.append(document.createTextNode(term));
            checkbox.addEventListener('change', () => { checkbox.checked ? modelTerms.add(term) : modelTerms.delete(term); updateModel(); });
        });
        updateModel();
    }
    const details = append(results, 'details', ''); append(details, 'summary', 'Concorrentes analisados (' + analysis.competitors.length + ')');
    const list = append(details, 'ol', '');
    analysis.competitors.forEach(competitor => { const anchor = append(append(list, 'li', ''), 'a', competitor.title); anchor.href = competitor.url; anchor.target = '_blank'; anchor.rel = 'noopener noreferrer'; });
    append(results, 'p', 'Coleta: ' + new Date(current.collectedAt).toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo' }) + ' · Busca: ' + current.query, 'to-hint');
}
form.addEventListener('input', () => { results.hidden = true; current = null; confirmed.clear(); modelTerms.clear(); policy = {state:'unknown',message:'Dados editados: confira as regras da categoria antes de usar o campo Modelo.'}; });
form.addEventListener('submit', event => {
    event.preventDefault(); if (pending) return;
    if (identify?.disabled) return;
    if (!available) { status.textContent = 'Instale ou atualize a extensão Keiper e recarregue esta página.'; root.querySelector('.to-setup').open = true; return; }
    const input = values(); if (!input.product || !input.original) return;
    if (Array.from(analyze(input, []).base).length > 60) { status.textContent = 'A identificação do produto ultrapassa 60 caracteres. Encurte os campos antes de buscar.'; return; }
    const id = crypto.randomUUID();
    const timer = setTimeout(() => { pending = null; submit.disabled = false; status.textContent = 'A pesquisa não respondeu no prazo. Confira a extensão e o acesso ao Mercado Livre.'; }, 100000);
    pending = { id, timer, input }; submit.disabled = true; results.hidden = true;
    status.textContent = 'Buscando concorrentes no Mercado Livre… A pesquisa pode levar até 90 segundos.';
    window.postMessage({ type: 'keiper-title-search', id, query: [input.product, input.brand, input.model].filter(Boolean).join(' ') }, location.origin);
});
window.addEventListener('message', event => {
    if (event.source !== window || event.origin !== location.origin) return;
    const response = event.data;
    if (response?.type === 'keiper-title-ready' && response.id === pingId && response.ready && response.version === '0.2.0') { available = true; extensionStatus.textContent = 'Extensão conectada · Como instalar ou atualizar'; return; }
    if (response?.type !== 'keiper-title-results' || !pending || response.id !== pending.id) return;
    const { timer, input } = pending; clearTimeout(timer); pending = null; submit.disabled = false;
    if (fingerprint(input) !== fingerprint(values())) { status.textContent = 'Os campos foram alterados durante a pesquisa. Faça uma nova busca para usar a identificação atual.'; return; }
    if (!Array.isArray(response.records) || !response.records.length) { status.textContent = response.error || 'A busca não retornou anúncios legíveis.'; return; }
    current = {input, records: response.records, pages: Number(response.pages) || 0, excludedSponsored: Number(response.excludedSponsored) || 0, error: typeof response.error === 'string' ? response.error : '', collectedAt: response.collectedAt, query: response.query};
    confirmed.clear(); modelTerms.clear(); show(); status.textContent = 'Pesquisa recebida. Confira a amostra e as sugestões abaixo.';
});
const identify = document.querySelector('#title-identify');
identify?.addEventListener('click', async () => {
    if (pending) return;
    const item = document.querySelector('#title-item').value.trim();
    if (!/^MLB\d{1,20}$/.test(item)) { status.textContent = 'Selecione um anúncio da lista ou informe o código MLB.'; return; }
    identify.disabled = true; submit.disabled = true; status.textContent = 'Lendo produto, marca, modelo e regras da categoria…';
    try {
        const response = await fetch(root.dataset.identityPath, {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':root.dataset.csrf}, body:JSON.stringify({item})});
        const data = await response.json(); if (!response.ok) throw new Error(data.error || 'Não foi possível identificar este anúncio.');
        for (const key of ['original','product','brand','model']) form.elements[key].value = data[key] || '';
        current = null; confirmed.clear(); results.hidden = true; policy = data.model_policy;
        document.querySelector('#title-identity-note').textContent = 'Marca e modelo lidos dos atributos do anúncio. Confira e encurte o campo Produto se necessário.';
        status.textContent = 'Dados carregados. Confira a identificação e inicie a busca.';
    } catch (error) { status.textContent = error.message || 'Falha na leitura. Você pode preencher os campos manualmente.'; }
    finally { identify.disabled = false; submit.disabled = Boolean(pending); }
});
window.postMessage({type:'keiper-title-ping', id:pingId}, location.origin);
setTimeout(() => { if (!available) extensionStatus.textContent = 'Instale ou atualize a extensão para pesquisar no Mercado Livre'; }, 1500);
