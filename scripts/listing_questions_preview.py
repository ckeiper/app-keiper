"""Question report with isolated synthetic fixtures only."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from listing_questions import model,render
from test_listing_questions import row
NOW=1793337000
for mode in ('empty','ready','limited','page2','fresh','unknown','partial'):
    rows=[] if mode=='empty' else [row(i,texto='Pergunta de teste '+str(i%3)+'?',status='ANSWERED' if i%2 else 'UNANSWERED',resposta='Resposta coletada de demonstração.' if i%2 else None) for i in range(1001 if mode=='limited' else 23)]
    if mode in ('fresh','partial'):
        for r in rows:r.update(atualizado_em=NOW,consulta_estado='read',status_confirmado_em=NOW,vendedor_confirmado='7',excluida_do_anuncio=False,em_espera=False)
        rows[0]['excluida_do_anuncio']=True
    data=model(rows,dict(pagina='2' if mode=='page2' else '1'),NOW,7)
    if mode in ('fresh','partial'):
        data['coverage']=dict(vendedor_id='7',consultado_em=NOW,estado='read' if mode=='fresh' else 'partial',lidas=50,total_informado=50 if mode=='fresh' else 300,paginas=1,revisadas=2,indisponiveis=0 if mode=='fresh' else 1)
    (dest/('listing-questions-'+mode+'.html')).write_text(page('Perguntas do anúncio',1,'Loja fictícia','anuncios','<p>Dados fictícios de teste.</p>'+render(1,'MLB123',dict(titulo='Produto de demonstração'),data)))
