"""Actionable, deterministic queue of verified listing revenue declines.

No inferred root causes, no synthetic sales, no additional database reads.
"""
from decimal import Decimal
from html import escape

from sales_decline import investigate

LABELS = {
    'full': ('Full zerado observado', 'Checar estoque Full e reposição por variação'),
    'preco': ('Preço próprio alterado', 'Revisar preço final e promoções'),
    'eficiencia': ('Eficiência de visitas caiu', 'Conferir preço final, frete, prazo e concorrência'),
    'trafego': ('Visitas diminuíram', 'Investigar exposição e posição no catálogo'),
    'ads_loja': ('Ads da loja reduziu', 'Confirmar campanha vinculada; Ads é contexto da loja'),
}


def prioritize(ranking, evidence_by_item=None, limit=6):
    analysis = investigate(ranking)
    if not analysis['available']:
        return {'available':False, 'reason':analysis.get('reason') or 'Dados não verificados.', 'items':[], 'total':0}
    evidence_by_item = evidence_by_item or {}
    results = []
    for record in analysis['rows']:
        item_id = str(record['item_id'])
        evidence = evidence_by_item.get(item_id) or {}
        codes = set(evidence.get('codes') or [])
        reasons = [LABELS[k][0] for k in ('full','preco','eficiencia','trafego','ads_loja') if k in codes]
        first = next((key for key in ('full','preco','eficiencia','trafego','ads_loja') if key in codes),None)
        # Order primarily by VERIFIED loss size, not heuristic "severity" guesses.
        results.append(dict(item_id=item_id, loss=record['loss'],
                            pct=record['percent'], share=record['share'],
                            codes=codes, reasons=reasons[:3],
                            action=LABELS[first][1] if first else 'Analisar visitas, Full, preço e histórico de alterações.',
                            coverage=evidence.get('visits_days'),
                            expected=evidence.get('expected')))
    results.sort(key=lambda r:(-r['loss'],r['item_id']))
    return dict(available=True, items=results[:limit], total=len(results),
                loss=analysis['lost'])


STYLE = """<style>
.kp-queue{margin:16px 0 24px;padding:23px;border-radius:18px;background:linear-gradient(135deg,#142943,#1d4269);color:#f7fbff;box-shadow:0 12px 32px #102b4420}
.kp-queue h2{color:#fff;font-size:22px;margin:0 0 6px;letter-spacing:-.4px}
.kp-queue p{color:#c6d5e8;font-size:12px;line-height:1.6;margin:7px 0}
.kp-queue .kp-kicker{font-size:10px;font-weight:850;letter-spacing:1.5px;color:#85c8ec}
.kp-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(255px,1fr));gap:12px;margin-top:17px}
.kp-item{display:block;min-width:0;text-decoration:none!important;background:#fff;color:#243651!important;border:1px solid #dce5f1;border-radius:12px;padding:17px;transition:transform .15s,box-shadow .15s}
.kp-item:hover{transform:translateY(-2px);box-shadow:0 10px 20px #08162935}
.kp-item:focus-visible{outline:3px solid #81b9ff}
.kp-title{display:block;font-size:13px;font-weight:800;overflow-wrap:anywhere;color:#223957}
.kp-loss{font-size:23px;font-weight:850;letter-spacing:-.6px;color:#bb4654;margin:9px 0 6px}
.kp-pill{display:inline-block;background:#f2f5fa;border-radius:6px;font-size:10px;font-weight:700;color:#51647d;padding:5px 7px;margin:3px 4px 3px 0}
.kp-item p{font-size:11px;color:#586c86;line-height:1.6}
.kp-foot{display:block;font-size:11px;font-weight:750;color:#35629b;margin-top:11px}
.kp-footer{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-top:14px}
.kp-footer a{color:#9fd7ff!important;font-size:12px;font-weight:750}
@media(max-width:600px){.kp-queue{padding:17px;border-radius:15px}.kp-grid{grid-template-columns:1fr}.kp-queue h2{font-size:20px}}
</style>"""


def render(result, listings, cid, days=7, compact=False):
    out=STYLE+'<section class="kp-queue" aria-label="Anúncios que precisam de atenção">'
    out+='<span class="kp-kicker">INTELIGÊNCIA KEIPER · PRIORIDADES</span><h2>Anúncios que precisam de atenção</h2>'
    out+='<p>Ordem automática pela maior perda bruta verificada em %s dias encerrados, comparados aos %s anteriores. Não é diagnóstico causal.</p>' % (days,days)
    if not result['available']:
        return out+'<p>Fila indisponível: '+escape(result['reason'])+'. Aguardando cobertura verificada; dados ausentes não são zero.</p></section>'
    if not result['items']:
        return out+'<p>Não foram identificados anúncios com perda de faturamento verificada neste recorte.</p></section>'
    names={str(x['item_id']):str(x.get('titulo') or x['item_id']) for x in listings}
    out+='<div class="kp-grid">'
    rows=result['items'][:3] if compact else result['items']
    for i,r in enumerate(rows):
        url='/diagnostico/%s/%s' % (int(cid),r['item_id'])
        out+='<a class="kp-item" href="'+escape(url,quote=True)+'"><span class="kp-title">'+str(i+1)+'. '+escape(names.get(r['item_id'],r['item_id']))+'</span>'
        out+='<div class="kp-loss">− R$ '+format(r['loss'],',.2f').replace(',','_').replace('.',',').replace('_','.')+'</div>'
        out+='<span class="kp-pill">%+.1f%% no faturamento</span>' % r['pct']
        for reason in r['reasons']:
            out+='<span class="kp-pill">'+escape(reason)+'</span>'
        out+='<p><b>Por onde começar:</b> '+escape(r['action'])+'</p>'
        if r['coverage'] is not None and r['coverage'] < r['expected']:
            out+='<p>Cobertura de visitas: %s/%s dias; sinais adicionais podem estar ausentes.</p>' % (r['coverage'],r['expected'])
        out+='<span class="kp-foot">Abrir investigação ↗</span></a>'
    out+='</div><div class="kp-footer"><p>'+str(result['total'])+' anúncios com perda verificada · soma das perdas: R$ '+format(result['loss'],',.2f').replace(',','_').replace('.',',').replace('_','.')+'</p>'
    out+='<a href="/ranking-anuncios/%s?dias=%s">Ver todas as prioridades →</a></div></section>' % (int(cid),int(days))
    return out
