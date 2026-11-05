"""Question report with isolated synthetic fixtures only."""
import sys
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from listing_questions import model,render
from test_listing_questions import row
NOW=1793337000
for mode in ('empty','ready','limited','page2','fresh','unknown','partial','queue','queue-page2','queue-empty','search','search-page2','search-empty','search-escaped'):
    rows=[] if mode=='empty' else [row(i,texto='Pergunta de teste '+str(i%3)+'?',status='ANSWERED' if i%2 else 'UNANSWERED',resposta='Resposta coletada de demonstração.' if i%2 else None) for i in range(1001 if mode=='limited' else 23)]
    if mode in ('fresh','partial','queue','queue-page2','queue-empty'):
        for r in rows:r.update(atualizado_em=NOW,consulta_estado='read',status_confirmado_em=NOW,vendedor_confirmado='7',excluida_do_anuncio=False,em_espera=False)
        rows[0]['excluida_do_anuncio']=True
    if mode.startswith('queue'):
        for i,r in enumerate(rows):r['data']=datetime.fromtimestamp(NOW-i*3600,timezone.utc).isoformat()
        rows[2]['data']='invalid'
        if mode=='queue-empty':
            for r in rows:r['em_espera']=True
    if mode.startswith('search'):
        for i,r in enumerate(rows):r['resposta']='A tensão é 220 V.' if i%2==0 else None
    args=dict(status='pending' if mode.startswith('queue') else 'all',pagina='2' if mode in ('page2','queue-page2') else '1')
    if mode.startswith('search'):args.update(q='TENSAO' if mode in ('search','search-page2') else '<script>searchAttack()</script>' if mode=='search-escaped' else 'inexistente',pagina='2' if mode=='search-page2' else '1')
    data=model(rows,args,NOW,7)
    if mode in ('fresh','partial'):
        data['coverage']=dict(vendedor_id='7',consultado_em=NOW,estado='read' if mode=='fresh' else 'partial',lidas=50,total_informado=50 if mode=='fresh' else 300,paginas=1,revisadas=2,indisponiveis=0 if mode=='fresh' else 1)
    (dest/('listing-questions-'+mode+'.html')).write_text(page('Perguntas do anúncio',1,'Loja fictícia','anuncios','<p>Dados fictícios de teste.</p>'+render(1,'MLB123',dict(titulo='Produto de demonstração'),data)),encoding='utf-8')
