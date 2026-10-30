"""Synthetic previews only; never sends a participation."""
from catalog_preview import page, dest
from promo_participation import candidate_table, confirmation_form
items=[dict(id='MLB1',status='candidate',original_price=100,suggested_discounted_price=80)]
pages={'candidates':candidate_table(1,'PROMO1',items,{'MLB1':'Produto teste'}),
       'empty':candidate_table(1,'PROMO1',[],{}),
       'confirm':confirmation_form(1,'PROMO1','MLB1',80,22,20,100)}
for name,body in pages.items():
    (dest/('promotion-participation-'+name+'.html')).write_text(page('Promoções',1,'Loja de teste','promocoes',body),encoding='utf-8')
