"""Question report with isolated synthetic fixtures only."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from listing_questions import model,render
from test_listing_questions import row
for mode in ('empty','ready','limited','page2'):
    rows=[] if mode=='empty' else [row(i,texto='Pergunta de teste '+str(i%3)+'?',status='ANSWERED' if i%2 else 'UNANSWERED',resposta='Resposta coletada de demonstração.' if i%2 else None) for i in range(1001 if mode=='limited' else 23)]
    data=model(rows,dict(pagina='2' if mode=='page2' else '1'))
    (dest/('listing-questions-'+mode+'.html')).write_text(page('Perguntas do anúncio',1,'Loja fictícia','anuncios','<p>Dados fictícios de teste.</p>'+render(1,'MLB123',dict(titulo='Produto de demonstração'),data)))
