"""Descriptive revenue contributions; never infer a missing baseline as zero."""
from decimal import Decimal
from html import escape


def contributions(rows):
    complete=bool(rows) and all(r['sales'] is not None and r.get('previous_sales') is not None for r in rows)
    baseline=sum((r['previous_sales'] for r in rows),Decimal(0)) if complete else None
    result=[]
    for r in rows:
        delta=r['sales']-r['previous_sales'] if r['sales'] is not None and r.get('previous_sales') is not None else None
        result.append(dict(**r,delta=delta,points=delta/baseline*100 if delta is not None and baseline else None))
    return dict(rows=result,delta=sum((r['delta'] for r in result),Decimal(0)) if complete else None)


def render(model):
    from portfolio_view import money,help_tip
    data=contributions(model['rows']);esc=lambda x:escape(str(x),quote=True)
    signed=lambda x:'Não disponível' if x is None else ('+' if x>0 else '−' if x<0 else '')+money(abs(x))
    scale=max([abs(r['delta']) for r in data['rows'] if r['delta'] is not None]+[Decimal(1)])
    out='<section class="pf-card portfolio-impact"><h3>Contribuição por cliente'+help_tip('Contribuição por cliente','Diferença de faturamento em relação ao período anterior de igual duração, com as mesmas lojas selecionadas. Pontos percentuais usam o faturamento anterior completo da carteira como base; não representam a variação percentual da loja. Barras comparam o valor absoluto das diferenças. Ausência de dados não vira zero. Não indica causa da mudança.')+'</h3>'
    out+='<div class="portfolio-impact-total">Variação da carteira <strong>'+esc(signed(data['delta']))+'</strong></div><div class="portfolio-impact-grid">'
    for r in data['rows']:
        state='up' if r['delta'] is not None and r['delta']>0 else 'down' if r['delta'] is not None and r['delta']<0 else 'flat'
        symbol={'up':'↗','down':'↘','flat':'→'}[state] if r['delta'] is not None else '?'
        url='/vendas/'+str(r['id'])+'?periodo=personalizado&amp;inicio='+str(model['start'])+'&amp;fim='+str(model['end'])
        out+='<a class="portfolio-impact-client" href="'+url+'"><span>'+esc(r['name'])+'</span><strong class="portfolio-change-'+state+'">'+symbol+' '+esc(signed(r['delta']))+'</strong>'
        if r['points'] is not None:out+='<small>'+esc(f"{r['points']:+.2f}".replace('.',','))+' p.p. na carteira</small>'
        width=0 if r['delta'] is None else float(abs(r['delta'])/scale*100)
        out+='<span class="portfolio-impact-track" aria-hidden="true"><span class="portfolio-impact-bar portfolio-impact-'+state+'" style="width:'+f'{width:.3f}'+'%"></span></span></a>'
    return out+'</div></section>'+STYLE


STYLE='''<style>.portfolio-impact-total{display:flex;gap:12px;flex-wrap:wrap;align-items:baseline;margin-bottom:18px}.portfolio-impact-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.portfolio .portfolio-impact-client{display:flex;flex-direction:column;gap:9px;min-width:0;padding:16px;border:1px solid #7892aa66;border-radius:12px;color:inherit;text-decoration:none;background:#142940}.portfolio-impact-client:is(:hover,:focus-visible){outline:2px solid #4a9ccc;outline-offset:2px}.portfolio-impact-client :is(span,strong,small){overflow-wrap:anywhere}.portfolio-impact-track{display:block;height:5px;background:#7892aa33;border-radius:4px;overflow:hidden}.portfolio-impact-bar{display:block;height:100%;background:#7892aa}.portfolio-impact-up{background:#80f0b7}.portfolio-impact-down{background:#ffb1b8}html[data-theme=light] body .portfolio .portfolio-impact-client{background:#fff!important}html[data-theme=light] body .portfolio .portfolio-impact-up{background:#087447}html[data-theme=light] body .portfolio .portfolio-impact-down{background:#b22539}@media(max-width:600px){.portfolio-impact-grid{grid-template-columns:1fr}}@layer keiper-appearance{html[data-theme=light] body .portfolio .portfolio-change-up{color:#087447!important}html[data-theme=light] body .portfolio .portfolio-change-down{color:#b22539!important}html[data-theme=light] body .portfolio .portfolio-change-flat{color:#52657c!important}}.portfolio .portfolio-change-flat{color:#9bacc1}</style>'''
