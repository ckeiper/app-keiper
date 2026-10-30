"""Exact saved-SKU overlap candidates; no product equivalence inference."""
from datetime import datetime
from html import escape
from urllib.parse import urlencode,quote
from sales_metrics import SAO_PAULO
from listing_calendar import STYLE
from listing_priority_sources import listing_signals

KEY='btrim(sku,chr(32)||chr(9)||chr(10)||chr(13))'


def load(conn,query,cid,args):
    raw=str(args.get('sku','')).strip(' \t\r\n')
    if len(raw)>200 or '\x00' in raw:raise ValueError('O filtro de SKU aceita até 200 caracteres.')
    stats=query(conn,'SELECT COUNT(*) AS total,COUNT(*) FILTER(WHERE sku IS NULL OR '+KEY+"='') AS missing FROM anuncios WHERE conexao_id=%s",(cid,))[0]
    where='conexao_id=%s AND sku IS NOT NULL AND '+KEY+"<>''";params=[cid]
    if raw:where+=' AND '+KEY+'=%s';params.append(raw)
    grouped='SELECT '+KEY+' AS code,COUNT(*) AS n FROM anuncios WHERE '+where+' GROUP BY '+KEY+' HAVING COUNT(*)>1'
    totals=query(conn,'SELECT COUNT(*) AS n,COALESCE(SUM(n),0) AS members FROM ('+grouped+') grouped',tuple(params))[0]
    pages=max(1,(totals['n']+9)//10)
    try:page=max(1,min(pages,int(args.get('pagina','1'))))
    except (TypeError,ValueError):page=1
    groups=query(conn,'SELECT * FROM ('+grouped+') grouped ORDER BY code COLLATE "C" LIMIT 10 OFFSET %s',tuple(params+[(page-1)*10]))
    members=[]
    if groups:
        members=query(conn,'''SELECT * FROM (SELECT item_id,titulo,status,quantidade,atualizado_em,'''+KEY+''' AS code,
            ROW_NUMBER() OVER(PARTITION BY '''+KEY+''' ORDER BY item_id) AS rn FROM anuncios
            WHERE conexao_id=%s AND '''+KEY+'''=ANY(%s)) members WHERE rn<=10 ORDER BY code COLLATE "C",rn''',(cid,[r['code'] for r in groups]))
    return dict(stats=stats,group_total=totals['n'],member_total=totals['members'],groups=groups,members=members,page=page,pages=pages,sku=raw)


def render(cid,data,now):
    esc=lambda v:escape(str(v),quote=True);path=f'/anuncios/{int(cid)}/skus-repetidos'
    out=STYLE+'''<style>.sku-official-entry{display:block;border:1px solid #426184;background:#182e49;border-radius:12px;padding:16px;overflow-wrap:anywhere}.sku-official-entry span{display:block;margin-top:8px}.sku-cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.sku-cards article,.sku-group{background:#182e49;border:1px solid #426184;border-radius:10px;padding:14px;margin:14px 0;overflow-wrap:anywhere}.sku-cards article{display:grid;gap:6px;font-size:12px}.sku-cards strong{font-size:24px}.sku-item{display:block;border:1px solid #426184;border-radius:8px;padding:12px;margin:10px 0;overflow-wrap:anywhere}.sku-item span{display:block;margin-top:6px;font-size:12px}.sku-item:hover{background:#244367}.sku-overlap form label{max-width:100%;flex:1}.sku-overlap input{min-width:0}.sku-overlap code{color:#b9e5ff;white-space:pre-wrap}@media(max-width:700px){.sku-cards{grid-template-columns:repeat(2,minmax(0,1fr))}}</style>'''
    out+='<section class="lc sku-overlap"><h2>SKUs repetidos na loja</h2><a href="/anuncios/'+str(int(cid))+'">Voltar ao catálogo</a><p>Critério: mesmo SKU cadastrado no anúncio, removendo apenas espaços, tabulações e quebras nas extremidades. Maiúsculas, acentos, caracteres e espaços internos são preservados. Não inclui SKUs exclusivos de variações quando ausentes neste campo.</p><p>Um grupo é uma coincidência cadastral para revisão, não prova de produto equivalente, concorrência interna, canibalização ou perda de vendas. Todos os status do catálogo salvo são considerados; confirme as condições atuais antes de decidir.</p><form method="get"><label>SKU exato · opcional<input name="sku" maxlength="200" value="'+esc(data['sku'])+'"></label><button>Filtrar</button><a href="'+path+'">Limpar filtro</a></form>'
    out+='<p><a class="sku-official-entry" href="/anuncios/'+str(int(cid))+'/skus-variacoes"><strong>Conferir SKUs oficiais e variações</strong><span>Leituras oficiais separadas do código interno salvo no catálogo.</span></a></p>'
    out+='<div class="sku-cards">'+''.join('<article><strong>'+str(n)+'</strong><span>'+label+'</span></article>' for n,label in [(data['stats']['total'],'Anúncios no catálogo salvo'),(data['stats']['missing'],'Sem SKU nesse campo'),(data['group_total'],'Grupos repetidos no filtro'),(data['member_total'],'Anúncios desses grupos')])+'</div>'
    out+='<p>Cards de catálogo e ausência de SKU consideram a loja inteira; grupos respeitam o filtro. Dez grupos por página e até dez anúncios por grupo, ordenados por código. Ausência de grupo não comprova ausência de sobreposição.</p>'
    for group in data['groups']:
        out+='<section class="sku-group"><h3>SKU <code>'+esc(group['code'])+'</code></h3><p>'+str(group['n'])+' anúncios com esse SKU salvo.</p>'
        if group['n']>10:out+='<p>Exibidos os primeiros dez anúncios deste grupo. Total acima inclui todos; refine a revisão pelo catálogo.</p>'
        for row in data['members']:
            if row['code']!=group['code']:continue
            signal=listing_signals([row],{},1,now=now)[str(row['item_id'])]
            stamp=row.get('atualizado_em');fresh=type(stamp) is int and 0<stamp<=now and now-stamp<=21600
            status=str(row.get('status') or 'não informado') if fresh else 'não verificado · leitura antiga/ausente'
            try:stamp_label=datetime.fromtimestamp(int(stamp),SAO_PAULO).strftime('%d/%m/%Y %H:%M')
            except (ValueError,TypeError,OverflowError,OSError):stamp_label='não verificada'
            stock=str(int(signal['stock'])) if signal['stock_verified'] else 'não verificado'
            out+='<a class="sku-item" href="/diagnostico/'+str(int(cid))+'/'+quote(str(row['item_id']),safe='')+'"><strong>'+esc(row.get('titulo') or row['item_id'])+'</strong><span>'+esc(row['item_id'])+' · status '+esc(status)+'</span><span>Estoque geral observado: '+stock+' · coleta '+stamp_label+' · Brasília</span></a>'
        out+='</section>'
    if not data['groups']:out+='<p>Nenhum SKU repetido neste filtro do catálogo salvo.</p>'
    out+='<nav aria-label="Paginação de grupos de SKU">Página '+str(data['page'])+' de '+str(data['pages'])
    for label,p in [('Anterior',data['page']-1),('Próxima',data['page']+1)]:
        if 1<=p<=data['pages']:out+=' <a href="'+esc(path+'?'+urlencode(dict(sku=data['sku'],pagina=p)))+'">'+label+'</a>'
    return out+'</nav></section>'


def register_overlap(app,login_required,can_view,bank,query,execute,shop_page):
    from listing_sku_variations import register
    register(app,login_required,can_view,bank,query,execute,shop_page)
    from flask import request,session
    import time
    @app.route('/anuncios/<int:cid>/skus-repetidos',methods=['GET'])
    @login_required
    def listing_saved_sku_overlap(cid):
        if session.get('tipo')!='admin' or not can_view(cid):return 'Acesso restrito',403
        try:
            with bank() as conn:
                execute(conn,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                shops=query(conn,'SELECT cliente FROM conexoes WHERE id=%s',(cid,))
                if not shops:return 'Loja não encontrada',404
                data=load(conn,query,cid,request.args)
        except ValueError as exc:return str(exc),400
        return shop_page('SKUs repetidos',cid,shops[0]['cliente'],'anuncios',render(cid,data,int(time.time())))
