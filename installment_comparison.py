"""Manual per-order fee scenarios; never marketplace quotes or historical evidence."""
import re
import secrets
from datetime import date, datetime
from zoneinfo import ZoneInfo
from decimal import Decimal, ROUND_HALF_UP
from html import escape
from flask import request, session
from profitability_scenarios import number
from profitability_view import CSS
from freight_comparison import format_brl

COMMON = {'product': 'Custo dos produtos no pedido (R$)', 'taxes': 'Impostos no pedido (R$)',
          'shipping': 'Frete do vendedor no pedido (R$)', 'ads': 'Publicidade no pedido (R$)',
          'adjustments': 'Outros custos e ajustes no pedido (R$)'}
SCENARIO = {'gross': 'Valor bruto dos itens no pedido (R$)',
            'fee': 'Tarifa total do marketplace, já incluindo financiamento (R$)',
            'financing': 'Parcela da tarifa total referente ao financiamento (R$)'}


def simulate(form, today=None):
    today = today or datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    common = {k: number(form.get(k), label) for k, label in COMMON.items()}
    if form.get('assumptions') != 'yes':
        raise ValueError('Confirme a conferência das premissas e a inclusão do financiamento na tarifa total.')
    rows = []
    for i in range(3):
        keys = ['label', 'installments', 'source', 'source_date', *SCENARIO]
        values = {k: str(form.get(f'{k}_{i}') or '').strip() for k in keys}
        if i == 2 and not any(values.values()):
            continue
        if not 3 <= len(values['label']) <= 80 or not 10 <= len(values['source']) <= 300:
            raise ValueError('Cada opção precisa de nome (3–80 caracteres) e referência dos valores (10–300 caracteres).')
        if not re.fullmatch(r'[1-9]|[1-3][0-9]|4[0-8]', values['installments']):
            raise ValueError('Informe de 1 a 48 parcelas inteiras por opção.')
        try:
            source_date = date.fromisoformat(values['source_date'])
        except ValueError:
            raise ValueError('Informe a data de referência de cada opção.') from None
        if source_date > today:
            raise ValueError('A data de referência não pode estar no futuro.')
        money = {k: number(values[k], label) for k, label in SCENARIO.items()}
        if money['gross'] <= 0:
            raise ValueError('O bruto do pedido deve ser maior que zero.')
        if money['financing'] > money['fee']:
            raise ValueError('O financiamento é parte da tarifa total e não pode excedê-la.')
        # Financing is informational only: it is already included in the total fee.
        costs = sum(common.values()) + money['fee']
        contribution = money['gross'] - costs
        rows.append(dict(money, label=values['label'], installments=int(values['installments']),
                         source=values['source'], source_date=source_date, costs=costs,
                         contribution=contribution, margin=contribution*100/money['gross']))
    baseline = rows[0]['contribution']
    for row in rows:
        row['delta'] = row['contribution'] - baseline
    return dict(common=common, rows=rows)


def render(cid, item_id, title, csrf, values=None, result=None, error=''):
    values = values or {}
    esc = lambda v: escape(str(v), quote=True)
    out = CSS + '<div class="pf installment-comparison"><header class="pf-hero"><span class="pf-eyebrow">Anúncios 2.0 · Premissas manuais</span><h2>Comparar tarifas e parcelamento</h2><p>'+esc(title or item_id)+' · '+esc(item_id)+'</p><a href="/anuncios/'+str(cid)+'/'+esc(item_id)+'/rentabilidade">← Rentabilidade do anúncio</a><p>Compare dois ou três pedidos hipotéticos com a mesma composição de produtos. Os valores são informados pelo administrador; a referência declarada não é verificada automaticamente.</p></header>'
    if error:
        out += '<p class="pf-alert" role="alert">'+esc(error)+'</p>'
    out += '<section class="pf-card"><h3>Custos comuns ao mesmo pedido</h3><p>Preencha todos os custos totais do pedido, inclusive zero. Use a mesma quantidade, composição de produtos e base tributária nas opções. Se impostos ou outros custos mudarem, compare em simulações separadas. A primeira opção será a referência aritmética.</p><form method="post"><input type="hidden" name="_csrf" value="'+esc(csrf)+'">'
    def field(key, label, kind='text', maximum=9, required=True):
        return '<label>'+label+'<input name="'+key+'" type="'+kind+'" maxlength="'+str(maximum)+'"'+(' required' if required else '')+(' inputmode="decimal"' if maximum == 9 else '')+' value="'+esc(values.get(key, ''))+'"></label>'
    for key, label in COMMON.items():
        out += field(key, label)
    out += '<div class="ic-options">'
    for i in range(3):
        suffix = '_'+str(i)
        out += '<fieldset><legend>Opção '+str(i+1)+(' · opcional, deixe toda em branco' if i == 2 else ' · obrigatória')+'</legend>'
        out += field('label'+suffix, 'Nome da opção', maximum=80, required=i < 2)
        out += field('installments'+suffix, 'Quantidade de parcelas · apenas identificação', maximum=2, required=i < 2)
        for key, label in SCENARIO.items():
            out += field(key+suffix, label, required=i < 2)
        out += field('source'+suffix, 'Referência da tarifa e do financiamento · documento ou simulação consultada', maximum=300, required=i < 2)
        out += field('source_date'+suffix, 'Data da referência', kind='date', maximum=10, required=i < 2)
        out += '</fieldset>'
    out += '</div><label><input type="checkbox" name="assumptions" value="yes" required'+(' checked' if values.get('assumptions') == 'yes' else '')+'>Conferi os custos e a mesma composição do pedido. O financiamento já está incluído na tarifa total e não será somado novamente.</label><p><button>Comparar opções</button></p></form></section>'
    if result:
        out += '<section class="pf-card" id="installment-results"><h3>Contribuição simulada por opção</h3><div class="pf-table" tabindex="0" role="region" aria-label="Comparação de parcelamento"><table style="min-width:960px"><caption>Valores por pedido, em R$ · role a tabela no celular</caption><thead><tr><th>Opção</th><th>Parcelas</th><th>Bruto</th><th>Tarifa total</th><th>Financiamento incluído</th><th>Custos totais</th><th>Contribuição</th><th>Margem</th><th>Diferença para opção 1</th></tr></thead><tbody>'
        for row in result['rows']:
            out += '<tr><td>'+esc(row['label'])+'</td><td>'+str(row['installments'])+'</td>'
            for key in ('gross', 'fee', 'financing', 'costs', 'contribution'):
                out += '<td>'+format_brl(row[key])+'</td>'
            out += '<td>'+format(row['margin'].quantize(Decimal('.01'), rounding=ROUND_HALF_UP), '.2f').replace('.', ',')+'%</td><td>'+format_brl(row['delta'])+'</td></tr>'
        out += '</tbody></table></div><details><summary>Conferir premissas e referências declaradas</summary>'
        for key, label in COMMON.items():
            out += '<p>'+label+': '+format_brl(result['common'][key])+'.</p>'
        for row in result['rows']:
            out += '<p>'+esc(row['label'])+' · '+row['source_date'].strftime('%d/%m/%Y')+' · '+esc(row['source'])+'</p>'
        out += '</details></section>'
    out += '<section class="pf-card"><h3>Como interpretar</h3><p>Contribuição = bruto − custos comuns − tarifa total. Financiamento é uma parte informativa da tarifa total. Valores monetários são informados a centavos; a margem exibida é arredondada a duas casas.</p><p>Não calcula a prestação do comprador, juros, valor presente ou calendário de recebimentos. A quantidade de parcelas identifica a opção, sem certificar disponibilidade ou elegibilidade. Não estima aumento de vendas nem recomenda automaticamente uma opção.</p><p>Esta simulação não consulta a API, não salva custos históricos e não altera o anúncio. Não substitui a cobrança oficial; contribuição não é lucro líquido nem repasse bancário. Despesas fixas não incluídas.</p></section></div>'
    return out + '<style>.ic-options{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.ic-options fieldset{min-width:0;border:1px solid #34516e;border-radius:12px;padding:16px}.ic-options legend{color:#eff5ff}.installment-comparison label{display:block;margin:12px 0}.installment-comparison input{max-width:100%;box-sizing:border-box}.installment-comparison fieldset label,.installment-comparison td{overflow-wrap:anywhere}@media(max-width:900px){.ic-options{grid-template-columns:1fr}}</style>'


def register(app, login_required, can_view, bank, query, shop_page):
    @app.route('/anuncios/<int:cid>/<item_id>/parcelamento', methods=['GET', 'POST'])
    @login_required
    def listing_installment_comparison(cid, item_id):
        if session.get('tipo') != 'admin' or not can_view(cid):
            return 'Acesso restrito ao administrador.', 403
        if not re.fullmatch(r'MLB[0-9]{1,20}', item_id):
            return 'Anúncio não encontrado.', 404
        with bank() as conn:
            shops = query(conn, '''SELECT c.cliente,a.titulo FROM conexoes c JOIN anuncios a
                ON a.conexao_id=c.id WHERE c.id=%s AND a.item_id=%s''', (cid, item_id))
        if not shops:
            return 'Anúncio não encontrado nesta loja.', 404
        token = session.setdefault('_csrf', secrets.token_urlsafe(32))
        result = None
        error = ''
        status = 200
        if request.method == 'POST':
            try:
                result = simulate(request.form)
            except ValueError as exc:
                error, status = str(exc), 400
        return shop_page('Comparar tarifas e parcelamento', cid, shops[0]['cliente'], 'anuncios',
                         render(cid, item_id, shops[0]['titulo'], token,
                                request.form if request.method == 'POST' else None, result, error)), status
