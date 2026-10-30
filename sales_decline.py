"""Explain verified revenue losses without claiming unobserved causes."""
from datetime import timedelta
from decimal import Decimal
from html import escape
from urllib.parse import urlencode


def investigate(ranking):
    if not ranking.get('available'):
        return dict(available=False, reason=ranking.get('reason'), rows=[])
    rows = ranking['rows']
    lost = sum((max(Decimal(0), m['previous_value'] - m['value']) for m in rows.values()), Decimal(0))
    gained = sum((max(Decimal(0), m['value'] - m['previous_value']) for m in rows.values()), Decimal(0))
    result = []
    for item_id, m in rows.items():
        loss = m['previous_value'] - m['value']
        if loss <= 0:
            continue
        before_units, units = m['previous_units'], m['units']
        before_price = m['previous_value'] / before_units
        # Exact additive decomposition: old price * volume change plus
        # current volume * price change. Price is realized unit value, not
        # today's listing price; variation mix can explain its change.
        volume_effect = (units - before_units) * before_price
        price_effect = m['value'] - units * before_price
        evidence = ['Unidades: %s → %s.' % (before_units, units)]
        if units:
            evidence.append('Valor médio vendido por unidade: R$ %.2f → R$ %.2f; pode refletir mix de variações ou descontos.' % (before_price, m['value'] / units))
        else:
            evidence.append('Nenhuma venda verificada no período atual.')
        result.append(dict(item_id=item_id, loss=loss,
                           percent=-loss * 100 / m['previous_value'],
                           share=loss * 100 / lost, current=m['value'], previous=m['previous_value'],
                           volume_effect=volume_effect, price_effect=price_effect,
                           evidence=evidence,
                           hypothesis=('Menor volume vendido' if volume_effect < 0 else 'Menor valor médio por unidade'),
                           action='Cruzar visitas e conversão; revisar Full, estoque por variação, preço final, prazo e Ads nas datas da queda.'))
    result.sort(key=lambda r: (-r['loss'], r['item_id']))
    return dict(available=True, rows=result, lost=lost, gained=gained, net=lost-gained,
                current=sum((m['value'] for m in rows.values()), Decimal(0)),
                previous=sum((m['previous_value'] for m in rows.values()), Decimal(0)))


CSS = """<style>
.decline{margin:18px 0;color:#243651}.decline-head{padding:22px;background:linear-gradient(120deg,#182d4d,#225769);color:white;border-radius:15px}.decline-head h3{color:white;margin:0 0 8px}.decline-head p{color:#d6e8ee;margin:5px 0;font-size:12px}.decline-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px;margin:14px 0}.decline-item{display:block;padding:19px;border:1px solid #e1e8f2;border-top:3px solid #dc7770;border-radius:13px;background:white;text-decoration:none!important;color:#243651!important;overflow-wrap:anywhere}.decline-item:hover{border-color:#329b9b;box-shadow:0 8px 20px #183b5418}.decline-item:focus-visible{outline:3px solid #329b9b}.decline-item strong{display:block;font-size:22px;margin:12px 0;color:#b24640}.decline-item p{font-size:12px;line-height:1.6}.decline-tools{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:14px 0}.decline-tools input,.decline-tools select{padding:8px;border:1px solid #dbe3ef;border-radius:8px}.decline-meta{font-size:12px;color:#64758e}
</style>"""


def render(ranking, listings, cid, args, end, days=7, item_id=None, observations=None, evidence_by_item=None):
    analysis = investigate(ranking)
    out = CSS + "<section class='decline'><div class='decline-head'><h3>Investigar queda de vendas</h3>"
    out += '<p>%s dias encerrados até %s, comparados aos %s dias anteriores. Valores brutos dos itens.</p></div>' % (days, end.strftime('%d/%m/%Y'), days)
    if not analysis['available']:
        return out + '<p>Diagnóstico indisponível: ' + escape(analysis['reason'] or 'Dados não verificados.') + '</p></section>'
    out += '<p class="decline-meta">Perdas nos anúncios: R$ %.2f · Ganhos em outros anúncios: R$ %.2f · Saldo da perda: R$ %.2f. Participação calculada sobre a soma das perdas, antes das compensações.</p>' % (analysis['lost'], analysis['gained'], analysis['net'])
    names = {str(a['item_id']): str(a.get('titulo') or a['item_id']) for a in listings}
    rows = analysis['rows']
    if item_id is not None:
        rows = [r for r in rows if r['item_id'] == str(item_id)]
    else:
        search = str(args.get('busca_queda') or '').strip()[:100]
        rows = [r for r in rows if search.casefold() in (names.get(r['item_id'], r['item_id'])+' '+r['item_id']).casefold()]
        tools = "<form class='decline-tools' method='get'><input type='hidden' name='dias' value='%s'><label>Buscar anúncio <input name='busca_queda' value='%s'></label>" % (days, escape(search, quote=True))
        if evidence_by_item is not None:
            selected=str(args.get('sinal_queda') or 'todos')
            choices=[('todos','Todos os sinais'),('full','Full zerado observado'),('trafego','Redução de tráfego'),('eficiencia','Menor eficiência das visitas'),('sem_sinais','Sem sinal nas regras')]
            if selected not in dict(choices):
                selected='todos'
            tools+="<label>Sinal para investigar <select name='sinal_queda'>"
            for code,label in choices:
                matched=sum(1 for r in rows if code=='todos' or (not evidence_by_item.get(r['item_id'],{}).get('codes') if code=='sem_sinais' else code in evidence_by_item.get(r['item_id'],{}).get('codes',[])))
                tools+="<option value='%s'%s>%s (%s)</option>" % (code,' selected' if selected==code else '',label,matched)
            tools+='</select></label>'
            if selected!='todos':
                rows=[r for r in rows if (not evidence_by_item.get(r['item_id'],{}).get('codes') if selected=='sem_sinais' else selected in evidence_by_item.get(r['item_id'],{}).get('codes',[]))]
        out+=tools+"<button class='filtro-btn'>Filtrar quedas</button></form>"
    if item_id is not None and observations is not None:
        from listing_full_sales_chart import daily_full_status
        dates = [(end-timedelta(days=2*days-1-i)).isoformat() for i in range(2*days)]
        stock = daily_full_status(observations, dates)
        for label, values in [('Período anterior',stock[:days]),('Período atual',stock[days:])]:
            out += '<p class="decline-meta">%s · Full com estoque: %s dias · Full sem estoque: %s dias · Sem observação confirmada de Full: %s dias. Última observação de cada dia; não mede a duração da ruptura.</p>' % (label, values.count(1),values.count(0),values.count(None))
    count = len(rows)
    pages = max(1, (count+11)//12)
    try:
        page = max(1, min(pages, int(args.get('pagina_queda', 1))))
    except (ValueError, TypeError):
        page = 1
    offset = (page-1)*12
    out += "<p class='decline-meta'>Mostrando %s–%s de %s anúncios com perda de faturamento</p><div class='decline-grid'>" % (offset+1 if count else 0, min(offset+12,count),count)
    for r in rows[offset:offset+12]:
        href = '/diagnostico/%s/%s' % (int(cid), r['item_id'])
        out += "<a class='decline-item' href='%s'><b>%s</b><strong>− R$ %.2f</strong>" % (escape(href,quote=True), escape(names.get(r['item_id'],r['item_id'])),r['loss'])
        out += '<p>R$ %.2f → R$ %.2f (%+.1f%%)<br>%.1f%% das perdas dos anúncios</p>' % (r['previous'],r['current'],r['percent'],r['share'])
        out += '<p><b>Sinal: %s</b><br>%s</p>' % (escape(r['hypothesis']),escape(' '.join(r['evidence'])))
        out += '<p>Efeito de volume: R$ %+.2f<br>Efeito de valor médio/mix: R$ %+.2f</p>' % (r['volume_effect'],r['price_effect'])
        evidence=(evidence_by_item or {}).get(r['item_id'])
        if evidence is not None:
            out+='<p><b>Sinais do anúncio</b><br>'
            out+='<br>'.join(escape(a['title']) for a in evidence['actions']) or 'Nenhum sinal atingiu as regras; confira a cobertura.'
            out+='</p><p>Visitas: %s/%s dias · Full: %s/%s dias conhecidos.</p>' % (evidence['visits_days'],evidence['expected'],evidence['full_days'],evidence['expected'])
            next_action=' '.join(a['action'] for a in evidence['actions']) or r['action']
        else:
            next_action=r['action']
        out += '<p><b>Próxima investigação</b><br>' + escape(next_action) + '</p><p>Causa ainda não confirmada · Vendas verificadas</p></a>'
    if not rows:
        out += '<p>Nenhuma perda de faturamento identificada neste recorte.</p>'
    out += '</div>'
    if item_id is None and pages > 1:
        out += "<nav class='decline-tools' aria-label='Paginação das quedas'>"
        for label,n in [('Anterior',page-1),('Próxima',page+1)]:
            if 1 <= n <= pages:
                params = dict(args)
                params['pagina_queda'] = n
                out += "<a class='filtro' href='?%s'>%s</a>" % (escape(urlencode(params),quote=True),label)
        out += '</nav>'
    return out + '<p class="decline-meta">A decomposição explica a diferença matemática, não sua causa. Visitas, conversão, mudanças de preço e Ads precisam de evidências próprias. Estoque atual não comprova ruptura histórica.</p></section>'
