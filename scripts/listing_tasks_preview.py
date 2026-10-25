"""Synthetic task screens; never writes tasks or contacts another service."""
import sys
from pathlib import Path
from datetime import timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from listing_task_view import render
from test_listing_tasks import model,task,DAY

for mode in ('open','empty','history','error','page2'):
    data=model();values={};message=''
    data['rows']=[task(id=i,title='Conferir oferta e estoque '+str(i),description='Revisar a fonte coletada antes de alterar o anúncio.') for i in range(1,11)]
    data['total']=15
    if mode=='empty':data.update(rows=[],total=0,counts=[],pages=1)
    if mode=='page2':data.update(rows=data['rows'][:5],page=2)
    if mode=='error':
        values=dict(title='Revisar fotos',responsible='Equipe responsável',due_date=DAY.isoformat(),description='Conferir imagens.');message='A tarefa foi atualizada em outra aba. Confira o status atual antes de tentar novamente.'
    if mode=='history':
        data['history']=task(status='done',version=2)
        data['events']=[dict(from_status='open',to_status='done',created_at=1792933200,created_by=1,version=2),dict(from_status=None,to_status='open',created_at=1792929600,created_by=1,version=1)]
    body='<p>Dados fictícios para teste.</p>'+render(1,'MLB123',dict(titulo='Produto de demonstração'),data,DAY,'synthetic-token',values=values,message=message)
    (dest/('listing-tasks-'+mode+'.html')).write_text(page('Tarefas do anúncio',1,'Loja de demonstração','anuncios',body),encoding='utf-8')
print('Synthetic listing task previews rendered.')
