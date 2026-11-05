"""Verify selectable image roles from a freshly authenticated owned listing."""
import re
from urllib.parse import urlsplit
from html import escape
from listing_content_snapshot import read,ContentUnavailable

ROLES={'thumbnail':'Principal do anúncio','variation_thumbnail':'Principal de variação','other':'Secundária'}


def preview_url(value):
    if not isinstance(value,str) or len(value)>2048 or any(ord(c)<=32 for c in value):return None
    try:
        u=urlsplit(value)
        if (u.scheme!='https' or u.hostname!='http2.mlstatic.com' or u.username is not None
                or u.password is not None or u.port not in (None,443) or not u.path.startswith('/')
                or u.query or u.fragment):return None
    except ValueError:return None
    return value


def gallery(choices):
    esc=lambda value:escape(str(value),quote=True)
    out='<fieldset class="id-photo-choices"><legend>Selecione uma foto para consultar</legend><div class="id-photo-grid">'
    for p in choices:
        label='Foto '+str(p['position'])
        out+='<label class="id-photo-card"><input type="radio" name="selected_picture" required value="'+esc(p['id'])+'"><span class="id-photo-preview">'
        url=preview_url(p.get('preview_url'))
        if url:out+='<img src="'+esc(url)+'" alt="'+esc(label)+'" loading="lazy" decoding="async" referrerpolicy="no-referrer">'
        else:out+='<span class="id-photo-missing">Prévia indisponível</span>'
        out+='</span><strong>'+esc(label)+'</strong><span>'+esc(ROLES[p['role']])+'</span><span class="id-picked">Selecionada</span></label>'
    return out+'</div></fieldset>'


GALLERY_STYLE='''<style>.id-photo-choices{min-width:0;margin:0;padding:0;border:0}.id-photo-choices legend{padding:0;margin-bottom:12px}.id-photo-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,170px),1fr));gap:12px}.image-diagnostic .id-photo-card{display:flex;flex-direction:column;gap:8px;min-width:0;padding:12px;border:2px solid #7892aa;border-radius:12px;cursor:pointer;overflow-wrap:anywhere}.id-photo-card:focus-within{outline:3px solid #d09a42;outline-offset:2px}.id-photo-card:has(input:checked){border-color:#65b9ff;background:#143a5b}.id-photo-card input{align-self:flex-start;width:20px!important;height:20px;margin:0;accent-color:#247bc1}.id-photo-preview{display:flex;align-items:center;justify-content:center;aspect-ratio:4/3;min-width:0;background:#fff;color:#243e59;border-radius:8px;overflow:hidden}.id-photo-preview img{display:block;width:100%;height:100%;object-fit:contain}.id-photo-missing{padding:10px;text-align:center}.id-picked{display:none;font-weight:700}.id-photo-card:has(input:checked) .id-picked{display:inline}html[data-theme=light] body .id-photo-card:has(input:checked){background:#e6f0fd!important;border-color:#24659b!important;color:#172d47!important}</style>'''


def load(token,seller,item_id,get):
    if (not isinstance(token,str) or not token or type(seller) is bool
            or not re.fullmatch(r'[1-9][0-9]{0,19}',str(seller))
            or not isinstance(item_id,str) or not re.fullmatch(r'MLB[0-9]{1,20}',item_id)):
        raise ContentUnavailable('Conexão ou anúncio não verificável.')
    account=read(token,'/users/me',get)
    if str(account.get('id'))!=str(seller):raise ContentUnavailable('A autorização não corresponde à conta desta loja.')
    item=read(token,'/items/'+item_id,get)
    if item.get('id')!=item_id or str(item.get('seller_id'))!=str(seller) or item.get('site_id')!='MLB':
        raise ContentUnavailable('O anúncio não corresponde à conta desta loja.')
    valid=lambda value:isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,200}',value)
    pictures=item.get('pictures');variations=item.get('variations');main=item.get('thumbnail_id');category=item.get('category_id')
    if (not isinstance(pictures,list) or not 1<=len(pictures)<=1000 or not valid(main)
            or not isinstance(variations,list) or len(variations)>100
            or not isinstance(category,str) or not re.fullmatch(r'MLB[0-9]{1,20}',category)):
        raise ContentUnavailable('Fotos, categoria ou variações não verificáveis para seleção.')
    ids=[p.get('id') if isinstance(p,dict) else None for p in pictures]
    if any(not valid(p) for p in ids) or len(set(ids))!=len(ids) or main not in ids:
        raise ContentUnavailable('Fotos do anúncio não verificáveis para seleção.')
    primary_variations=set();seen=set();known=set(ids)
    for variation in variations:
        if not isinstance(variation,dict):raise ContentUnavailable('Variações não verificáveis.')
        vid=variation.get('id');vp=variation.get('picture_ids')
        if (type(vid) is bool or not re.fullmatch(r'[1-9][0-9]{0,19}',str(vid)) or str(vid) in seen
                or not isinstance(vp,list) or not 1<=len(vp)<=1000
                or any(not valid(p) or p not in known for p in vp) or len(set(vp))!=len(vp)):
            raise ContentUnavailable('Fotos das variações não verificáveis para seleção.')
        seen.add(str(vid));primary_variations.add(vp[0])
    rows=[dict(id=p,role='thumbnail' if p==main else 'variation_thumbnail' if p in primary_variations else 'other',position=i+1,preview_url=preview_url(pictures[i].get('secure_url'))) for i,p in enumerate(ids)]
    return item,rows
