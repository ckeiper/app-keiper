import os,time,unittest
from unittest.mock import Mock
from sales_geography import init_schema,sync
from sales_geography_view import load
from sales_metrics import reporting_today

@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class GeographyDatabaseTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
    os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
    import main
    cls.m=main
    if main.scheduler.running:main.scheduler.shutdown(wait=False)
 def test_persistence_idempotence_and_store_isolation(self):
    m=self.m;ids=[];today=reporting_today().isoformat()
    try:
        with m.banco() as conn:
            init_schema(conn,m.executar);init_schema(conn,m.executar)
            for name in ('Map A','Map B'):
                cid=m.consultar(conn,"INSERT INTO conexoes(cliente,status) VALUES(%s,'ativa') RETURNING id",(name,))[0]['id'];ids.append(cid)
                m.executar(conn,'''INSERT INTO pedidos(conexao_id,pedido_id,status,total,moeda,criado_em,pagamentos_json,unidades,vendas_verificado_em)
                    VALUES(%s,'123','paid',100,'BRL',%s,'[{"status":"approved"}]',1,1)''',(cid,today+'T12:00:00-03:00'))
                m.executar(conn,'INSERT INTO vendas_cobertura(conexao_id,dia,atualizado_em) VALUES(%s,%s,1)',(cid,today))
        from test_sales_geography import shipment
        get=Mock(side_effect=[Mock(status_code=200,json=lambda:dict(id=9)),Mock(status_code=200,json=lambda:[shipment()])])
        sync(ids[0],'test',9,m.banco,m.consultar,m.executar,get,now=int(time.time()))
        a=load(m.banco,m.consultar,ids[0],dict(periodo='personalizado',inicio=today,fim=today))[-1]
        b=load(m.banco,m.consultar,ids[1],dict(periodo='personalizado',inicio=today,fim=today))[-1]
        self.assertEqual((a['known'],b['known'],b['missing']['orders']),(1,0,1))
        get=Mock(return_value=Mock(status_code=200,json=lambda:dict(id=9)))
        sync(ids[0],'test',9,m.banco,m.consultar,m.executar,get,now=int(time.time())+1)
        self.assertEqual(get.call_count,1)
    finally:
        with m.banco() as conn:
            for table in ('vendas_destinos','vendas_cobertura','pedidos','conexoes'):
                field='id' if table=='conexoes' else 'conexao_id'
                m.executar(conn,'DELETE FROM '+table+' WHERE '+field+'=ANY(%s)',(ids,))
