"""On-demand official diagnostics for the verified thumbnail; never edits a listing."""
import hmac
import re
import secrets
from datetime import datetime,timezone
from html import escape
from uuid import uuid4
from zoneinfo import ZoneInfo
import requests
from flask import request,session
from listing_content_snapshot import read,ContentUnavailable
from profitability_view import CSS

RATE_LIMIT_MESSAGE='Limite de consultas atingido. Aguarde antes de tentar novamente.'
LABELS={'white_background':'Fundo da imagem','minimum_size':'Tamanho da imagem','text_logo':'Textos ou logotipos','watermark':'Marca d’água'}


def normalize(payload,expected_id):
    if not isinstance(payload,dict) or payload.get('id')!=expected_id:
        raise ContentUnavailable('Resposta do diagnóstico não corresponde à consulta.')
    rows=payload.get('diagnostics')
    if not isinstance(rows,list) or not 1<=len(rows)<=10 or any(not isinstance(row,dict) for row in rows):
        raise ContentUnavailable('Diagnóstico da imagem não verificável na resposta.')
    selected=[row for row in rows if row.get('picture_type')=='thumbnail']
    if len(selected)!=1:raise ContentUnavailable('Diagnóstico da imagem principal ausente ou ambíguo.')
    row=selected[0];detections=row.get('detections');action=row.get('action')
    if (action not in ('empty','diagnostic') or not isinstance(detections,list) or len(detections)>20
            or (action=='empty' and detections) or (action=='diagnostic' and not detections)):
        raise ContentUnavailable('Ação e sinais do diagnóstico não verificáveis.')
    findings=[];seen=set()
    for detection in detections:
        if not isinstance(detection,dict) or detection.get('name') not in LABELS or detection['name'] in seen:
            raise ContentUnavailable('A API retornou sinais não reconhecidos ou repetidos; confira a imagem no Mercado Livre.')
        seen.add(detection['name']);wordings=detection.get('wordings')
        if not isinstance(wordings,list) or not 1<=len(wordings)<=10:
            raise ContentUnavailable('Orientações do diagnóstico não verificáveis.')
        messages=[]
        for wording in wordings:
            if (not isinstance(wording,dict) or wording.get('kind')!='REMEDY_SHORT'
                    or not isinstance(wording.get('value'),str) or not wording['value'].strip() or len(wording['value'])>2000):
                raise ContentUnavailable('Orientações do diagnóstico não verificáveis.')
            messages.append(wording['value'])
        findings.append(dict(name=detection['name'],messages=messages))
    return dict(action=action,findings=findings)


def inspect(token,seller_id,item_id,request_get,request_post,now=None):
    result=dict(state='unknown',checked_at=now or datetime.now(timezone.utc))
    if (not isinstance(token,str) or not token or type(seller_id) is bool or not re.fullmatch(r'[1-9][0-9]{0,19}',str(seller_id))
            or not isinstance(item_id,str) or not re.fullmatch(r'MLB[0-9]{1,20}',item_id)):
        return dict(result,message='Conexão ou anúncio não verificável.')
    try:
        account=read(token,'/users/me',request_get)
        if str(account.get('id'))!=str(seller_id):raise ContentUnavailable('A autorização não corresponde à conta desta loja.')
        item=read(token,'/items/'+item_id,request_get)
        if item.get('id')!=item_id or str(item.get('seller_id'))!=str(seller_id) or item.get('site_id')!='MLB':
            raise ContentUnavailable('O anúncio não corresponde à conta desta loja.')
        category=item.get('category_id');picture=item.get('thumbnail_id');pictures=item.get('pictures')
        valid_picture=lambda value:isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,200}',value)
        if (not isinstance(category,str) or not re.fullmatch(r'MLB[0-9]{1,20}',category)
                or not valid_picture(picture) or not isinstance(pictures,list) or not 1<=len(pictures)<=1000):
            raise ContentUnavailable('Categoria ou imagem principal não verificável. Nenhuma ausência foi presumida.')
        ids=[row.get('id') if isinstance(row,dict) else None for row in pictures]
        if any(not valid_picture(value) for value in ids) or len(set(ids))!=len(ids) or picture not in ids:
            raise ContentUnavailable('A imagem principal não corresponde a uma foto verificável do anúncio.')
        context=dict(category_id=category,picture_type='thumbnail')
        title=item.get('title')
        if isinstance(title,str) and title.strip() and len(title)<=1000:context['title']=title
        diagnostic_id=str(uuid4())
        response=request_post('https://api.mercadolibre.com/moderations/pictures/diagnostic',
            headers={'Authorization':'Bearer '+token},json=dict(id=diagnostic_id,picture_id=picture,context=context),
            timeout=(3,8),allow_redirects=False)
        if response.status_code==429:raise ContentUnavailable(RATE_LIMIT_MESSAGE)
        if response.status_code!=200:raise ContentUnavailable('Diagnóstico indisponível no Mercado Livre. Nenhuma aprovação ou ausência foi presumida.')
        data=normalize(response.json(),diagnostic_id)
        return dict(result,**data,state='read',picture_id=picture,category=category,diagnostic_id=diagnostic_id,catalog=item.get('catalog_listing') is True)
    except ContentUnavailable as exc:return dict(result,message=str(exc))
    except (requests.RequestException,ValueError,TypeError):
        return dict(result,message='Falha de rede ou resposta inválida. A imagem não foi verificada.')


def render(cid,item_id,title,csrf,result=None):
    esc=lambda value:escape(str(value),quote=True)
    path='/anuncios/'+str(int(cid))+'/'+esc(item_id)
    out=CSS+'<div class="pf image-diagnostic"><header class="pf-hero"><span class="pf-eyebrow">Anúncios 2.0 · Imagem principal</span><h2>Diagnóstico oficial da imagem</h2><p>'+esc(title or item_id)+' · '+esc(item_id)+'</p></header><section class="pf-card"><h3>Consultar no Mercado Livre</h3><p>Analisa apenas a imagem identificada como principal no anúncio. Não troca fotos nem altera a publicação.</p><form method="post"><input type="hidden" name="_csrf" value="'+esc(csrf)+'"><button>Consultar imagem principal</button></form></section>'
    if result:
        stamp=result['checked_at'].astimezone(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y às %H:%M:%S · Brasília')
        out+='<section class="pf-card" id="image-diagnostic-result"><h3>Leitura consultada</h3><p>'+esc(stamp)+'</p>'
        if result['state']!='read':out+='<p role="status">Sem diagnóstico verificável. '+esc(result['message'])+'</p>'
        else:
            out+='<p class="id-source">Imagem '+esc(result['picture_id'])+' · categoria '+esc(result['category'])+'</p>'
            if result['catalog']:out+='<p>Publicação de catálogo: confira a gestão das imagens do produto antes de propor uma edição.</p>'
            if result['action']=='empty':out+='<p class="id-empty">Nenhum apontamento retornado para a imagem principal nos critérios desta consulta. Isso não aprova o anúncio nem certifica toda a qualidade visual.</p>'
            else:
                out+='<h4>Apontamentos do Mercado Livre</h4>'
                for finding in result['findings']:
                    out+='<article class="id-finding"><strong>'+LABELS[finding['name']]+'</strong>'+''.join('<p>'+esc(message)+'</p>' for message in finding['messages'])+'</article>'
            out+='<details><summary>Identificador da consulta</summary><p>'+esc(result['diagnostic_id'])+'</p></details>'
        out+='</section>'
    out+='<section class="pf-card"><details><summary>Critérios e cobertura</summary><p>A API pode apontar fundo, tamanho mínimo, textos/logotipos e marcas d’água conforme a categoria. Não aplicamos um tamanho ou fundo obrigatório por conta própria. Não analisa aqui as demais fotos, variações, clips, coerência com o produto ou impacto nas vendas. Uma falha não significa foto incorreta nem ausência de problemas. A leitura não substitui a revisão manual e pode mudar depois.</p></details><a class="id-back" href="'+path+'/conteudo">Voltar ao checklist de conteúdo</a></section></div>'
    return out+'<style>.image-diagnostic{min-width:0}.image-diagnostic :is(p,strong){overflow-wrap:anywhere}.id-finding{padding:14px;border:1px solid #426184;border-left:3px solid #c08d54;border-radius:10px;margin:12px 0}.id-finding p{white-space:pre-wrap}.id-back{display:inline-block;padding:14px;border:1px solid #7892aa;border-radius:10px;margin-top:12px}.image-diagnostic button{white-space:normal;max-width:100%}html[data-theme=light] body .image-diagnostic .pf-hero{background:#e6f0fd!important;color:#193a60!important}</style>'


def register(app,login_required,can_view,bank,query,shop_page,resolve_token,request_get,request_post):
    @app.route('/anuncios/<int:cid>/<item_id>/imagem-principal',methods=['GET','POST'])
    @login_required
    def listing_image_diagnostic(cid,item_id):
        if session.get('tipo')!='admin' or not can_view(cid):return 'Acesso restrito',403
        if not re.fullmatch(r'MLB[0-9]{1,20}',item_id):return 'Anúncio não encontrado',404
        csrf=session.setdefault('_csrf',secrets.token_urlsafe(32))
        if request.method=='POST' and not hmac.compare_digest(csrf.encode(),request.form.get('_csrf','').encode()):return 'Formulário expirado. Recarregue a página.',400
        with bank() as conn:
            shops=query(conn,'''SELECT c.*,a.titulo FROM conexoes c JOIN anuncios a
                ON a.conexao_id=c.id WHERE c.id=%s AND a.item_id=%s''',(cid,item_id))
        if not shops:return 'Anúncio não encontrado nesta loja.',404
        result=inspect(resolve_token(shops[0]),shops[0]['user_id'],item_id,request_get,request_post) if request.method=='POST' else None
        return shop_page('Diagnóstico da imagem principal',cid,shops[0]['cliente'],'anuncios',render(cid,item_id,shops[0]['titulo'],csrf,result),refresh=False)
