"""Manual listing action records and conservative before/after comparisons."""
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from html import escape
from zoneinfo import ZoneInfo
from listing_sales import listing_sales_summary
from investigation_evidence import window, change, date_key
from sales_drivers import money

BR = ZoneInfo('America/Sao_Paulo')
KINDS = {'preco':'Preço / promoção','full':'Estoque / Full','entrega':'Frete / prazo',
         'conteudo':'Título / fotos / conteúdo','ads':'Publicidade','outro':'Outra ação'}


def init_schema(conn, execute):
    execute(conn, '''CREATE TABLE IF NOT EXISTS listing_interventions (
        id BIGSERIAL PRIMARY KEY,
        conexao_id INTEGER NOT NULL REFERENCES conexoes(id) ON DELETE CASCADE,
        item_id TEXT NOT NULL, event_date DATE NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN ('preco','full','entrega','conteudo','ads','outro')),
        note TEXT NOT NULL CHECK(char_length(note) BETWEEN 10 AND 1500),
        created_at BIGINT NOT NULL, created_by INTEGER NOT NULL,
        submission_key VARCHAR(64) NOT NULL,
        void_at BIGINT, void_by INTEGER,
        UNIQUE(conexao_id,submission_key))''')
    execute(conn, '''CREATE INDEX IF NOT EXISTS listing_interventions_item_date
        ON listing_interventions(conexao_id,item_id,event_date DESC,id DESC)''')


def validate(form, today):
    kind = form.get('kind','')
    note = form.get('note','').strip()
    try:
        day = date.fromisoformat(form.get('event_date',''))
    except (ValueError,TypeError):
        raise ValueError('Informe uma data válida para a ação.')
    if not today-timedelta(days=365) <= day <= today:
        raise ValueError('Use uma data dos últimos 365 dias, sem incluir o futuro.')
    if kind not in KINDS:
        raise ValueError('Selecione o tipo de ação.')
    if not 10 <= len(note) <= 1500 or '\x00' in note:
        raise ValueError('Descreva a ação com 10 a 1.500 caracteres.')
    key = form.get('submission_key','')
    if not re.fullmatch(r'[A-Za-z0-9_-]{20,64}',key):
        raise ValueError('Formulário inválido. Recarregue a página.')
    return day,kind,note,key


def compare(item_id, action_day, orders, items, covered, visits, today, pending=False):
    periods = [(action_day-timedelta(days=7),action_day-timedelta(days=1)),
               (action_day+timedelta(days=1),action_day+timedelta(days=7))]
    result = dict(periods=[],ready=today>periods[1][1],closed_after=max(0,min(7,(today-action_day).days-1)))
    for start,end in periods:
        dates = [(start+timedelta(days=i)).isoformat() for i in range(7)]
        closed_visits=[row for row in visits if date_key(row.get('dia')) and date_key(row.get('dia')) < today.isoformat()]
        traffic = window(closed_visits,dates,['visitas'],'dia')
        closed = end < today
        sales = listing_sales_summary(orders,items,covered,item_id,end=end,days=7)
        if pending or not closed:
            sales.update(orders=None,units=None,gross_items=None,ticket=None,
                         reason='Há pedidos não verificados.' if pending else 'Período ainda não encerrado.')
        total_visits = traffic['totals']['visitas'] if traffic['complete'] and closed else None
        ratio = Decimal(sales['orders'])*100/total_visits if sales['orders'] is not None and total_visits and total_visits>0 else None
        result['periods'].append(dict(start=start,end=end,sales=sales,visits=total_visits,
                                      visits_days=traffic['covered'],ratio=ratio))
    before,after = result['periods']
    result['delta'] = (after['sales']['gross_items']-before['sales']['gross_items']
                       if before['sales']['gross_items'] is not None and after['sales']['gross_items'] is not None else None)
    result['percent'] = change(after['sales']['gross_items'],before['sales']['gross_items']) if result['delta'] is not None else None
    return result


def load_comparison(conn, query, cid, item_id, action_day, today):
    # One comparison per page, never one set of queries per history row. Use the
    # established store-wide classifier so broken item mapping cannot hide sales.
    orders = query(conn, '''SELECT conexao_id,pedido_id,status,total,moeda,criado_em,
        pagamentos_json,unidades,vendas_dia_coleta FROM pedidos
        WHERE conexao_id=%s AND vendas_verificado_em IS NOT NULL''',(cid,))
    items = query(conn, '''SELECT pi.conexao_id,pi.pedido_id,pi.item_id,pi.quantidade,pi.preco_unitario
        FROM pedidos_itens pi JOIN pedidos p ON p.conexao_id=pi.conexao_id AND p.pedido_id=pi.pedido_id
        WHERE pi.conexao_id=%s AND p.vendas_verificado_em IS NOT NULL''',(cid,))
    start,end = (action_day-timedelta(days=7)).isoformat(),(action_day+timedelta(days=7)).isoformat()
    coverage = query(conn,'SELECT dia FROM vendas_cobertura WHERE conexao_id=%s AND dia BETWEEN %s AND %s',(cid,start,end))
    traffic = query(conn,'SELECT dia,visitas FROM item_visits_daily WHERE conexao_id=%s AND item_id=%s AND dia BETWEEN %s AND %s',(cid,item_id,start,end))
    pending = query(conn,'SELECT EXISTS(SELECT 1 FROM pedidos WHERE conexao_id=%s AND vendas_verificado_em IS NULL) AS pending',(cid,))[0]['pending']
    overlaps = query(conn,'''SELECT COUNT(*) AS n FROM listing_interventions
        WHERE conexao_id=%s AND item_id=%s AND void_at IS NULL AND event_date BETWEEN %s AND %s''',(cid,item_id,start,end))[0]['n']
    result=compare(item_id,action_day,orders,items,[r['dia'] for r in coverage],traffic,today,pending)
    result['other_actions']=max(0,overlaps-1)
    return result


CSS = """<style>
.interventions{color:#253a56;min-width:0;max-width:100%}.interventions .iv-head{padding:24px;background:linear-gradient(115deg,#1b304f,#306779);border-radius:16px;color:#fff;margin-bottom:18px}.iv-head h2{color:#fff;margin:0 0 10px}.iv-head p{font-size:12px;line-height:1.6;color:#d8e7f0}.interventions a.iv-btn,.interventions button{display:inline-block;text-decoration:none;border:1px solid #d4dfed;border-radius:8px;background:#fff;color:#2d5180;padding:9px 12px;font-size:12px;cursor:pointer}.interventions button.iv-primary{background:#3458c8;color:#fff;border-color:#3458c8}.iv-form{display:grid;grid-template-columns:1fr 1fr;gap:13px}.iv-form label{display:grid;gap:6px;font-size:12px;min-width:0}.iv-form .iv-wide{grid-column:1/-1}.iv-form input,.iv-form select,.iv-form textarea{box-sizing:border-box;width:100%;padding:10px;border:1px solid #d6e0ec;border-radius:8px;font:inherit;min-width:0}.iv-form textarea{min-height:95px;resize:vertical}.iv-card{border:1px solid #dde6f0;background:#fff;border-radius:13px;padding:19px;margin:13px 0;min-width:0;overflow-wrap:anywhere}.iv-note{white-space:pre-wrap;font-size:13px;line-height:1.6}.iv-meta{font-size:11px;color:#6b7e95;line-height:1.65}.iv-tools{display:flex;gap:10px;flex-wrap:wrap;align-items:center}.iv-scroll{overflow-x:auto;max-width:100%}.iv-table{width:100%;min-width:440px;border-collapse:collapse;font-size:12px}.iv-table th,.iv-table td{padding:10px;text-align:left;border-bottom:1px solid #e6edf5}.iv-status{padding:12px;border-radius:9px;background:#edf4ff;font-size:12px;line-height:1.6}.iv-status.warn{background:#fff3df;color:#865c25}.iv-card h3{margin:0 0 12px;font-size:16px}.iv-void{opacity:.7}.iv-scroll-hint{font-size:11px;color:#6b7e95}@media(max-width:600px){.iv-form{grid-template-columns:1fr}.iv-head,.iv-card{padding:15px}}
</style>"""


def comparison_html(result, record):
    out="<section class='iv-card' aria-label='Comparação da ação'><h3>Antes e depois da ação informada</h3>"
    if not result['ready']:
        out+="<p class='iv-status warn'>Aguardando os 7 dias seguintes encerrados: %s/7 completos.</p>" % result['closed_after']
    if result['delta'] is not None:
        out+="<p class='iv-status'>Variação do valor bruto dos itens: <b>"+money(result['delta'],True)+'</b>'
        out+=' · '+(('%+.1f%%' % result['percent']).replace('.',',') if result['percent'] is not None else 'sem base percentual anterior')+'</p>'
    else:
        out+="<p class='iv-meta'>Variação de vendas indisponível até que ambos os períodos tenham dias encerrados e vendas verificadas.</p>"
    out+="<p class='iv-scroll-hint'>Deslize a tabela no celular para conferir os dois períodos.</p><div class='iv-scroll'><table class='iv-table'><thead><tr><th>Indicador</th><th>7 dias anteriores</th><th>7 dias seguintes</th></tr></thead><tbody>"
    before,after=result['periods']
    out+='<tr><th>Datas</th>'+''.join('<td>'+p['start'].strftime('%d/%m')+' a '+p['end'].strftime('%d/%m/%Y')+'</td>' for p in (before,after))+'</tr>'
    for label,key,kind in [('Pedidos pagos','orders','count'),('Unidades','units','count'),('Valor bruto dos itens','gross_items','money'),('Visitas','visits','count'),('Pedidos ÷ visitas','ratio','percent')]:
        out+='<tr><th>'+label+'</th>'
        for p in (before,after):
            value=p.get(key) if key in ('visits','ratio') else p['sales'][key]
            text='Indisponível' if value is None else money(value) if kind=='money' else (('%.2f%%' % value).replace('.',',') if kind=='percent' else str(int(value)))
            out+='<td>'+text+'</td>'
        out+='</tr>'
    out+='</tbody></table></div>'
    for label,p in [('Antes',before),('Depois',after)]:
        out+='<p class="iv-meta">'+label+': visitas válidas em %s/7 dias.' % p['visits_days']
        if p['sales']['reason']:
            out+=' Vendas: '+escape(p['sales']['reason'])
        out+='</p>'
    out+='<p class="iv-meta">O dia '+record['event_date'].strftime('%d/%m/%Y')+' fica fora da comparação. Registro manual; não confirma execução no Mercado Livre. Valor bruto dos itens deste anúncio, sem rateio de frete, taxas ou cupons. Pedidos/visitas não é a conversão oficial.</p>'
    if result['other_actions']:
        out+="<p class='iv-status warn'>%s outra(s) ação(ões) registrada(s) neste intervalo. Os resultados se sobrepõem.</p>" % result['other_actions']
    return out+'<p class="iv-meta">Comparação observacional, sem atribuir causalidade à ação. Demanda, sazonalidade, concorrência e alterações não registradas também podem explicar a variação.</p></section>'
