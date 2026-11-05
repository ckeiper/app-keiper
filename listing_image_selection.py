"""Verify selectable image roles from a freshly authenticated owned listing."""
import re
from listing_content_snapshot import read,ContentUnavailable

ROLES={'thumbnail':'Principal do anúncio','variation_thumbnail':'Principal de variação','other':'Secundária'}


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
    rows=[dict(id=p,role='thumbnail' if p==main else 'variation_thumbnail' if p in primary_variations else 'other',position=i+1) for i,p in enumerate(ids)]
    return item,rows
