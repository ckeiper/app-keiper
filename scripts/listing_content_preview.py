"""Synthetic isolated content review screens."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from listing_content_view import render
from listing_content import CRITERIA
for mode in ('empty','reviewed','error','page2'):
    data=dict(latest={},history=[],total=0,page=1,pages=1);values={};message=''
    if mode!='empty':
        rows=[dict(id=i+1,criterion=code,verdict='revise' if i%2 else 'approved',note='Conferência manual de teste: revisar medidas e compatibilidade antes de alterar a oferta.',created_at=1792980000,created_by=1) for i,code in enumerate(CRITERIA)]
        data.update(latest={r['criterion']:r for r in rows},history=rows[:3] if mode=='page2' else rows,total=13,page=2 if mode=='page2' else 1,pages=2)
    if mode=='error':values=dict(criterion='principal',expected=0,submission_key='synthetic-form-key-1234',verdict='revise',note='Rever a evidência informada.');message='Este critério mudou em outra aba. Recarregue a página.'
    (dest/('listing-content-'+mode+'.html')).write_text(page('Revisão de conteúdo',1,'Loja de teste','anuncios','<p>Dados fictícios de teste.</p>'+render(1,'MLB123',dict(titulo='Produto de demonstração',fotos=4,clips=None),data,'token',values,message)))
