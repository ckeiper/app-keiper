"""Exercise production action routes with synthetic data; no database or ML API."""
import contextlib
import sys
from datetime import date,datetime,timedelta
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from flask import Flask
from catalog_preview import page,dest
from intervention_routes import register_interventions
from listing_interventions import compare,BR

DAY=date(2026,10,12);TODAY=DAY+timedelta(days=8);ITEM='MLB100'
records=[dict(id=i,conexao_id=1,item_id=ITEM,event_date=DAY,kind='conteudo',note='Foto principal atualizada para mostrar a medida. Registro '+str(i),created_at=int(datetime(2026,10,12,15,tzinfo=BR).timestamp()),void_at=None) for i in range(12,0,-1)]
orders=[];items=[];visits=[];covered=[]
for i in range(-7,8):
    day=DAY+timedelta(days=i);covered.append(day.isoformat())
    value=100 if i<0 else 200
    orders.append(dict(conexao_id=1,pedido_id=str(i),status='paid',total=value,moeda='BRL',criado_em=day.isoformat()+'T12:00:00-03:00',pagamentos_json=[{'status':'approved'}],unidades=1))
    items.append(dict(conexao_id=1,pedido_id=str(i),item_id=ITEM,quantidade=1,preco_unitario=value))
    visits.append(dict(dia=day,visitas=100))
comparison=compare(ITEM,DAY,orders,items,covered,visits,TODAY)
comparison['other_actions']=11
app=Flask(__name__);app.secret_key='synthetic-preview-only'
def query(conn,sql,params):
    if 'JOIN anuncios' in sql:return [dict(cliente='Loja de demonstração',titulo='Produto de demonstração')]
    if 'COUNT(*)' in sql:return [dict(n=len(records))]
    if 'WHERE id=%s' in sql:return [r for r in records if r['id']==params[0]]
    return records[params[-1]:params[-1]+10]
register_interventions(app,lambda fn:fn,lambda cid:cid==1,lambda:contextlib.nullcontext(None),query,lambda *args:None,page,today=lambda:TODAY)
client=app.test_client()
with client.session_transaction() as s:s.update(usuario_id=1,tipo='admin')
for name,path in [('interventions-history',''),('interventions-page2','?pagina=2')]:
    with patch('intervention_routes.load_comparison',return_value=comparison):
        response=client.get('/anuncios/1/MLB100/acoes'+path)
    assert response.status_code==200
    (dest/(name+'.html')).write_text(response.text,encoding='utf-8')
records.clear()
response=client.get('/anuncios/1/MLB100/acoes')
assert response.status_code==200
(dest/'interventions-empty.html').write_text(response.text,encoding='utf-8')
print('Synthetic action history previews rendered.')
