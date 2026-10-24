"""Store-scoped catalog presentation and filtering from saved snapshots only."""
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from html import escape
from urllib.parse import urlencode

from competitor_routes import tabs
from listing_details import active_promotions, effective_promotion, read_json, render_promotions, render_weight_column
from listing_health import diagnose_listing
from management_design import STYLE, metric_card, product
from sales_metrics import SAO_PAULO
from sales_view import fmt

STATUS={'':'Todos os status','active':'Ativos','paused':'Pausados','closed':'Encerrados'}
READING={'':'Todas as leituras','recente':'Catálogo lido há até 6 horas','antiga':'Leitura com mais de 6 horas','desconhecida':'Data ausente ou inválida'}
STOCK={'':'Todo estoque','zero':'Zerado','baixo':'1 a 3 unidades','disponivel':'Com estoque','desconhecido':'Não verificado'}
CAMPAIGNS={'':'Todas as consultas de campanhas','valida':'Campanhas: consulta válida','pendente':'Campanhas: conferir consulta','inaplicavel':'Campanhas: não aplicáveis'}
PROMO={'':'Todas as condições','sim':'Com promoção registrada','nao':'Sem promoção registrada'}
LOGISTICS={'':'Toda logística','full':'Full','outros':'Outras modalidades','desconhecido':'Não verificada'}
FOCUS={'':'Todos os anúncios','atencao':'Revisar status ou estoque','fotos':'Menos de 5 fotos','sem_clip':'Sem clip registrado','sem_custo':'Sem custo cadastrado'}
SORT={'vendidos':'Mais vendidos no histórico','titulo':'Título A–Z','estoque':'Menor estoque','preco':'Maior preço exibido','recentes':'Atualização mais recente'}


def number(value):
    if isinstance(value,bool): return None
    try:
        n=Decimal(str(value))
        return n if n.is_finite() and n>=0 else None
    except (InvalidOperation,ValueError,TypeError): return None


def quantity(value):
    n=number(value)
    return n if n is not None and n==n.to_integral_value() else None


def displayed_price(row):
    offer=effective_promotion(read_json(row.get('promocoes_json'),{}))
    return number(offer['price'] if offer else row.get('preco'))


def campaign_reading(row,now):
    snapshot=read_json(row.get('promocoes_json'),{})
    if not isinstance(snapshot,dict):return 'pendente'
    stamp=snapshot.get('checked_at')
    if type(stamp) not in (int,float) or not 0<stamp<=now or now-stamp>7200:return 'pendente'
    if snapshot.get('not_applicable'):
        return 'inaplicavel' if row.get('status') in ('closed','under_review') else 'pendente'
    if snapshot.get('error') or not isinstance(snapshot.get('promotions'),list):return 'pendente'
    if any(not isinstance(p,dict) for p in snapshot['promotions']):return 'pendente'
    return 'valida'


def promotion(row):
    snapshot=read_json(row.get('promocoes_json'),{})
    return bool(active_promotions(snapshot) or effective_promotion(snapshot))


def logistics(row,now):
    snapshot=read_json(row.get('full_metadata_json'),{})
    if not isinstance(snapshot,dict): return 'desconhecido'
    stamp=snapshot.get('collected_at')
    if type(stamp) is not int or not 0<=now-stamp<=6*3600: return 'desconhecido'
    return {'fulfillment':'full','other':'outros'}.get(snapshot.get('logistics'),'desconhecido')


def freshness(row,now):
    stamp=number(row.get('atualizado_em'))
    if stamp is None or stamp<=0 or stamp!=stamp.to_integral_value() or stamp>now:
        return 'desconhecida'
    return 'recente' if now-stamp<=6*3600 else 'antiga'


def filter_catalog(rows,args,now=None):
    now=int(time.time()) if now is None else now
    query=str(args.get('busca','')).strip()[:200].casefold()
    result=[]
    for row in rows:
        if args.get('leitura') in READING and args.get('leitura') and freshness(row,now)!=args['leitura']:continue
        if args.get('campanhas') in CAMPAIGNS and args.get('campanhas') and campaign_reading(row,now)!=args['campanhas']:continue
        status=str(row.get('status') or '').lower()
        stock=quantity(row.get('quantidade'))
        if query and query not in ' '.join(str(row.get(k) or '') for k in ('titulo','item_id','sku')).casefold(): continue
        if args.get('status') in STATUS and args.get('status') and status!=args['status']: continue
        f=args.get('estoque')
        if f=='zero' and stock!=0: continue
        if f=='baixo' and not (stock is not None and 0<stock<=3): continue
        if f=='disponivel' and not (stock is not None and stock>0): continue
        if f=='desconhecido' and stock is not None: continue
        f=args.get('promocao')
        if f in ('sim','nao') and promotion(row)!=(f=='sim'): continue
        f=args.get('logistica')
        if f in LOGISTICS and f and logistics(row,now)!=f: continue
        f=args.get('foco')
        if f=='atencao' and not (status=='paused' or stock==0): continue
        if f=='fotos' and not (quantity(row.get('fotos')) is not None and quantity(row.get('fotos'))<5): continue
        if f=='sem_clip' and quantity(row.get('clips'))!=0: continue
        if f=='sem_custo' and number(row.get('custo')) not in (None,0): continue
        result.append(row)
    order=args.get('ordem','vendidos')
    def key(row):
        if order=='titulo': return (str(row.get('titulo') or '').casefold(),str(row['item_id']))
        field={'estoque':'quantidade','preco':'preco','recentes':'atualizado_em'}.get(order,'vendidos')
        n=displayed_price(row) if field=='preco' else quantity(row.get(field)) if field in ('quantidade','vendidos') else number(row.get(field))
        return (n is None,n if field=='quantidade' and n is not None else -(n or 0),str(row['item_id']))
    return sorted(result,key=key)


def select(name,label,options,args):
    return "<label>"+label+"<select name='"+name+"'>"+''.join("<option value='"+escape(k,quote=True)+"'"+(' selected' if args.get(name,'')==k else '')+'>'+escape(v)+'</option>' for k,v in options.items())+'</select></label>'


def badge(label,tone='neutral'):
    return "<span class='catalog-badge catalog-"+tone+"'>"+escape(label)+'</span>'


CSS="""<style>
.catalog-header{display:flex;justify-content:space-between;align-items:center;gap:20px;flex-wrap:wrap;margin:16px 0 22px}.catalog-header h2{font-size:27px;margin:5px 0}.catalog-header p{margin:0}.catalog-header a{white-space:nowrap}.catalog-summary .stat:nth-child(2) .mgmt-metric-icon{background:#e4f6ee;color:#218665}.catalog-summary .stat:nth-child(3) .mgmt-metric-icon{background:#ffebe7;color:#bb604f}.catalog-summary .stat:nth-child(4) .mgmt-metric-icon{background:#fff2db;color:#a5762e}.catalog-summary .stat:first-child{background:linear-gradient(125deg,#5062d9,#7a60df)}.catalog-summary .stat:first-child :is(.num,.lab,small){color:white!important}.catalog-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:20px 0}.catalog-table{width:100%;min-width:920px;border-collapse:collapse}.catalog-table th{background:#f6f8fc;color:#8390a5;font-size:10px;text-transform:uppercase;letter-spacing:.5px;text-align:left;padding:14px}.catalog-table td{padding:18px 14px;vertical-align:top;border-bottom:1px solid #e9edf5;font-size:12px;line-height:1.7;color:#485773}.catalog-table td:first-child{width:34%;min-width:260px}.catalog-table tbody tr:hover{background:#fbfcff}.catalog-table .mgmt-product{align-items:flex-start}.catalog-table .mgmt-product strong{font-size:12px;line-height:1.6;font-weight:650}.catalog-table .mgmt-product img,.catalog-table .mgmt-product-placeholder{width:56px;height:56px}.catalog-table small{display:block;color:#8995a8;font-size:10px}.catalog-badge{display:inline-block;border-radius:6px;padding:3px 7px;font-size:10px;white-space:nowrap;margin:2px 4px 2px 0;background:#edf0f7;color:#7b879b}.catalog-green{background:#e4f6ee;color:#218665}.catalog-amber{background:#fff2db;color:#a5762e}.catalog-red{background:#ffebe7;color:#bb604f}.catalog-purple{background:#eeebfc;color:#7560bd}.catalog-price{font-size:17px;color:#2b3955;font-weight:750;font-variant-numeric:tabular-nums}.catalog-details{margin-top:12px}.catalog-details summary{color:#7771c0!important;font-size:11px!important}.catalog-details dl{display:grid;grid-template-columns:1fr 1fr;gap:7px 14px;background:#f6f8fc;border-radius:9px;padding:12px;font-size:10px}.catalog-details dt{color:#7c879e}.catalog-details dd{margin:0;overflow-wrap:anywhere}.catalog-table .tag{font-size:10px}.catalog-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:9px}.catalog-actions a{color:#6d6ac8;font-size:10px;text-decoration:none}.catalog-filter{display:flex;align-items:end;gap:10px;flex-wrap:wrap}.catalog-filter label{min-width:130px;display:grid;gap:6px;font-size:10px;color:#7d899e}.catalog-filter label:first-child{flex:2;min-width:200px}.catalog-filter input,.catalog-filter select{width:100%;box-sizing:border-box;border:1px solid #dfe5ef;border-radius:8px;background:white;padding:10px;font:inherit;font-size:12px;color:#40506a;min-height:38px}.catalog-filter :is(input,select,button,a):focus-visible{outline:3px solid #bfc5fc;outline-offset:2px}.catalog-toolbar{display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap;margin:22px 0 12px}.catalog-toolbar h2{margin:0}.catalog-scroll{overflow-x:auto;border:1px solid #e8edf4;border-radius:12px}.catalog-pager{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-top:18px;font-size:11px;color:#8590a3}.catalog-pager a{color:#6967c6}.catalog-empty{padding:48px 20px;text-align:center;background:#f8f9fd;border-radius:12px}.catalog-extra{font-size:11px;margin:20px 0}.catalog-warning{background:#fff7e9;border:1px solid #f2dfbb;padding:12px 16px;border-radius:10px;margin:16px 0}.catalog-refresh .barra-atualizar{margin:0}.catalog-dashboard .catalog-refresh{font-size:11px}.catalog-dashboard .catalog-summary .stat .num{font-size:28px}.catalog-dashboard details[open]{max-width:100%}@media(max-width:820px){.layout:has(.catalog-dashboard)>.menu-lateral{position:fixed;top:0;left:0;bottom:0;z-index:1102;width:min(280px,82vw)!important;max-height:100dvh;border-radius:0;box-sizing:border-box;overflow-y:auto;display:flex;flex-direction:column;transform:translateX(-105%)}body.sidebar-open .layout:has(.catalog-dashboard)>.menu-lateral{transform:translateX(0)}.layout:has(.catalog-dashboard)>.menu-lateral a.item{display:block;width:100%}}@media(max-width:900px){.catalog-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.catalog-filter label{flex:1}}@media(max-width:500px){.catalog-summary{gap:9px}.catalog-filter label{min-width:120px}.catalog-filter label:first-child{flex-basis:100%}.catalog-header h2{font-size:24px}.catalog-dashboard .card{padding:15px}}
body .conteudo .catalog-dashboard{background:#102238;color:#eaf2ff;padding:20px;border-radius:16px}
body .conteudo .catalog-dashboard .card,body .conteudo .catalog-dashboard .stat{background:#142940;border-color:#34516e}
body .conteudo .catalog-dashboard h2,body .conteudo .catalog-dashboard .catalog-price,body .conteudo .catalog-dashboard .mgmt-product strong{color:#eaf2ff}
body .conteudo .catalog-dashboard .muted,body .conteudo .catalog-dashboard p,body .conteudo .catalog-dashboard small,body .conteudo .catalog-dashboard label{color:#bdcce1}
body .conteudo .catalog-dashboard .stat :is(.num,.lab,small){color:#eaf2ff!important}
body .conteudo .catalog-dashboard .catalog-summary .stat:first-child{background:linear-gradient(125deg,#153354,#20567b)}
body .conteudo .catalog-dashboard .catalog-table th,body .conteudo .catalog-dashboard .catalog-table td{background:#142940;color:#eaf2ff;border-color:#34516e}
body .conteudo .catalog-dashboard .catalog-filter input,body .conteudo .catalog-dashboard .catalog-filter select,body .conteudo .catalog-dashboard .catalog-details dl,body .conteudo .catalog-dashboard .catalog-empty{background:#0b192c;color:#eaf2ff;border-color:#426184}
body .conteudo .catalog-dashboard .catalog-details dd,body .conteudo .catalog-dashboard .catalog-details dt{color:#bdcce1}
body .conteudo .catalog-dashboard a,body .conteudo .catalog-dashboard .catalog-details summary{color:#b9e5ff!important}
body .conteudo .catalog-dashboard .catalog-warning{background:#3b3020;color:#ffe3ac;border-color:#836b34}
body .conteudo .catalog-dashboard .catalog-warning p{color:#ffe3ac}
</style>"""


def render_catalog(cid,rows,args,refresh='',errors=(),admin=False,freight=None,now=None):
    now=int(time.time()) if now is None else now
    filtered=filter_catalog(rows,args,now)
    try: size=int(args.get('por_pagina','20'));size=size if size in (10,20,50,100) else 20
    except (TypeError,ValueError): size=20
    pages=max(1,(len(filtered)+size-1)//size)
    try: page=max(1,min(pages,int(args.get('pagina','1'))))
    except (TypeError,ValueError): page=1
    visible=filtered[(page-1)*size:page*size]
    path='/anuncios/'+str(cid)
    body=STYLE.replace('.mgmt-dashboard','.catalog-dashboard')+CSS+"<div class='catalog-dashboard'>"+tabs(cid,'anuncios')
    body+="<header class='catalog-header'><div><span class='mgmt-eyebrow'>Gestão do catálogo</span><h2>Anúncios</h2><p>Encontre o produto. Identifique o ponto de atenção. Aja.</p></div><a class='btn-acoes' href='/ranking-anuncios/"+str(cid)+"'>Analisar vendas por anúncio →</a></header><div class='catalog-refresh'>"+refresh+'</div>'
    counts=[('Anúncios cadastrados',len(rows),'Visão de todo o catálogo'),('Anúncios ativos',sum(str(a.get('status') or '').lower()=='active' for a in rows),'Status na última sincronização'),('Estoque zerado',sum(quantity(a.get('quantidade'))==0 for a in rows),'Estoque desconhecido não entra na contagem'),('Em promoção',sum(promotion(a) for a in rows),'Promoções identificadas na última coleta')]
    body+="<div class='catalog-summary'>"+''.join(metric_card(k,str(v),note) for k,v,note in counts)+'</div>'
    stale=sum(freshness(a,now)!='recente' for a in rows)
    if stale: body+="<div class='catalog-warning'>"+str(stale)+' anúncios com leitura antiga ou sem data confirmada. Atualize os dados antes de decidir sobre estoque e preço.</div>'
    body+="<section class='card'><form class='catalog-filter' method='get'><label>Buscar produto<input name='busca' maxlength='200' placeholder='Título, código MLB ou SKU' value='"+escape(str(args.get('busca',''))[:200],quote=True)+"'></label>"
    for name,label,options in [('status','Status',STATUS),('leitura','Atualização do catálogo',READING),('estoque','Estoque',STOCK),('promocao','Promoção',PROMO),('campanhas','Consulta de campanhas',CAMPAIGNS),('logistica','Logística',LOGISTICS),('foco','Ponto de atenção',FOCUS),('ordem','Ordenar por',SORT),('por_pagina','Por página',{str(n):str(n) for n in (10,20,50,100)})]:
        body+=select(name,label,options,dict(args,por_pagina=str(size),ordem=args.get('ordem','vendidos')))
    body+="<button class='btn-acoes'>Aplicar filtros</button><a href='"+path+"'>Limpar filtros</a></form><div class='catalog-toolbar'><h2>Seu catálogo</h2><span class='muted'>"+str(len(filtered))+' de '+str(len(rows))+" anúncios · venda acumulada no histórico</span></div>"
    if not visible:
        body+="<div class='catalog-empty'><h2>"+('Nenhum anúncio para estes filtros' if rows else 'Seu catálogo ainda não foi sincronizado')+"</h2><p>"+('Ajuste os filtros ou limpe a busca para ver outros produtos.' if rows else 'Use Atualizar agora para carregar os anúncios da loja.')+'</p></div>'
    else:
        body+="<div class='catalog-scroll'><table class='catalog-table'><thead><tr><th>Produto</th><th>Preço e promoção</th><th>Status e estoque</th><th>Conteúdo</th><th>Histórico</th></tr></thead><tbody>"
        for row in visible:
            item=str(row['item_id']);diag='/diagnostico/'+str(cid)+'/'+item
            body+='<tr><td>'+product({'listing':row},cid,True)+"<small>"+escape(item)+(' · SKU '+escape(str(row['sku'])) if row.get('sku') else '')+'</small>'
            actions=diagnose_listing(row);signal=actions[0]
            tone={'alta':'red','media':'amber','ok':'green'}.get(signal['priority'],'purple')
            body+=badge(signal['title'],tone)+"<div class='catalog-actions'><a href='"+escape(diag,quote=True)+"'>Ver diagnóstico →</a><a href='/full/"+str(cid)+"?"+escape(urlencode({'item_id':item}),quote=True)+"'>Full e vendas</a></div>"
            body+="<details class='catalog-details'><summary>Pesos, tags e frete</summary><dl><dt>Peso cadastrado · PACKAGE_WEIGHT</dt><dd>"+render_weight_column(row.get('pesos_json'),'PACKAGE_WEIGHT')+'</dd><dt>Peso logístico · SELLER_PACKAGE_WEIGHT</dt><dd>'+render_weight_column(row.get('pesos_json'),'SELLER_PACKAGE_WEIGHT')+'</dd><dt>Declarado pelo vendedor</dt><dd>Consulte o peso logístico acima</dd>'
            expected=freight(row.get('preco'),row.get('peso')) if freight else None
            body+='<dt>Frete esperado</dt><dd>'+escape(fmt(expected,True))+'</dd><dt>Custo cadastrado</dt><dd>'+escape(fmt(number(row.get('custo')),True))+'</dd><dt>Tags coletadas</dt><dd>'
            tags=read_json(row.get('tags'),[])
            body+=escape(', '.join(str(t) for t in tags) if isinstance(tags,list) and tags else 'Sem tags registradas')+'</dd></dl></details></td>'
            offer=effective_promotion(read_json(row.get('promocoes_json'),{}))
            campaign_state=campaign_reading(row,now)
            body+="<td><div class='catalog-price'>"+escape(fmt(displayed_price(row),True))+"</div>"+("<small><s>"+escape(fmt(offer['original'],True))+"</s> · Promoção confirmada</small>" if offer else "<small>Preço do anúncio na última coleta</small>")+"<details class='catalog-details'><summary>"+('Promoção registrada' if promotion(row) else 'Consultar promoções')+'</summary>'+render_promotions(row.get('promocoes_json'))+'</details>'+badge(CAMPAIGNS[campaign_state], 'green' if campaign_state=='valida' else 'amber')
            if admin: body+="<a class='muted' href='/diagnostico/anuncios/"+str(cid)+'/'+escape(item,quote=True)+"'>Diagnosticar preço na API</a>"
            body+='</td><td>'
            status=str(row.get('status') or '')
            body+=badge({'active':'Ativo','paused':'Pausado','closed':'Encerrado'}.get(status.lower(),status or 'Não verificado'),'green' if status.lower()=='active' else 'amber')
            stock=quantity(row.get('quantidade'))
            body+='<div>'+badge(str(int(stock))+' disponíveis' if stock is not None else 'Estoque não verificado','red' if stock==0 else 'neutral')+'</div>'
            kind=logistics(row,now)
            body+=badge({'full':'Full','outros':'Outras modalidades','desconhecido':'Logística não verificada'}[kind],'green' if kind=='full' else 'neutral')+'</td><td>'
            photos=quantity(row.get('fotos'));clips=quantity(row.get('clips'))
            body+=badge(str(int(photos))+' fotos' if photos is not None else 'Fotos não verificadas','amber' if photos is not None and photos<5 else 'neutral')+'<br>'+badge(str(int(clips))+' clips' if clips is not None else 'Clips não verificados')+'</td><td><b>'+escape(fmt(quantity(row.get('vendidos')),False))+'</b><small>vendidos acumulados<br>Não corresponde ao período atual</small>'
            stamp=number(row.get('atualizado_em'))
            try: date=datetime.fromtimestamp(float(stamp),SAO_PAULO).strftime('%d/%m/%Y %H:%M') if stamp else 'Não confirmada'
            except (ValueError,OverflowError,OSError): date='Não confirmada'
            state=freshness(row,now)
            body+='<small>Leitura: '+date+'</small>'+badge({'recente':'Catálogo: leitura recente','antiga':'Catálogo: leitura antiga','desconhecida':'Catálogo: data não confirmada'}[state], 'green' if state=='recente' else 'amber')+'</td></tr>'
        body+='</tbody></table></div>'
    body+="<nav class='catalog-pager' aria-label='Paginação dos anúncios'><span>"+f'Mostrando {(page-1)*size+1 if filtered else 0}–{min(page*size,len(filtered))} de {len(filtered)} anúncios · Página {page} de {pages}'+'</span>'
    for label,target in [('← Anterior',page-1),('Próxima →',page+1)]:
        if 1<=target<=pages:
            params={k:str(args[k]) for k in ('busca','status','estoque','promocao','logistica','foco','ordem','leitura','campanhas') if args.get(k)}
            params.update(por_pagina=str(size),pagina=str(target))
            body+="<a href='"+escape(path+'?'+urlencode(params),quote=True)+"'>"+label+'</a>'
    body+='</nav></section><p class="muted">Consulta válida de campanhas não garante promoção ativa ou preço vencedor. O preço vencedor pode estar confirmado mesmo com pendência na consulta de campanhas. Leitura recente do catálogo não confirma a atualização de promoções ou Full, que têm fontes e datas próprias. Fotos abaixo de 5 são uma sugestão editorial, não uma regra do Mercado Livre. Full identifica a modalidade logística coletada; não comprova estoque no centro de distribuição. Frete esperado é uma estimativa pela tabela existente, não uma cotação.</p>'
    warnings=[e for e in errors if e.get('categoria')!='financeiro']
    if warnings: body+="<details class='catalog-warning'><summary>Avisos da sincronização · "+str(len(warnings))+'</summary>'+''.join('<p>'+escape(str(e.get('categoria') or ''))+': '+escape(str(e.get('mensagem') or ''))+'</p>' for e in warnings)+'</details>'
    return body+'''<div id='catalog-loading' hidden role='status'>Carregando anúncios…</div><script>
    (function(){var form=document.querySelector('.catalog-filter');if(!form)return;
    form.addEventListener('submit',function(event){if(form.getAttribute('aria-busy')==='true'){event.preventDefault();return;}form.setAttribute('aria-busy','true');document.getElementById('catalog-loading').hidden=false;});
    window.addEventListener('pageshow',function(){form.removeAttribute('aria-busy');document.getElementById('catalog-loading').hidden=true;});})();
    </script><style>#catalog-loading:not([hidden]){position:fixed;right:20px;bottom:20px;border-radius:10px;background:#6265dc;color:white;padding:14px 20px;z-index:20}</style></div>'''
