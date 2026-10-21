import contextlib
import os
import time
import unittest
from datetime import date,timedelta
from functools import wraps
from unittest.mock import Mock,patch
from flask import Flask,session,redirect
from listing_interventions import validate,compare,load_comparison,comparison_html
from intervention_routes import register_interventions

DAY=date(2026,10,12)
TODAY=DAY+timedelta(days=8)
ITEM='MLB100'


def sample():
    orders=[];items=[];visits=[];covered=[]
    for i in range(-7,8):
        day=DAY+timedelta(days=i)
        value=100 if i<0 else 200 if i>0 else 9999
        covered.append(day.isoformat())
        orders.append(dict(conexao_id=1,pedido_id=str(i),status='paid',total=value,moeda='BRL',criado_em=day.isoformat()+'T12:00:00-03:00',pagamentos_json=[{'status':'approved'}],unidades=1))
        items.append(dict(conexao_id=1,pedido_id=str(i),item_id=ITEM,quantidade=1,preco_unitario=value))
        visits.append(dict(dia=day,visitas=100 if i<0 else 200))
    return orders,items,covered,visits


def form(**extra):
    return dict(kind='conteudo',note='Foto principal substituída para mostrar a medida.',event_date=DAY.isoformat(),submission_key='a'*32,**extra)


class InterventionMetricsTests(unittest.TestCase):
    def test_excludes_action_day_and_compares_two_closed_weeks(self):
        result=compare(ITEM,DAY,*sample(),TODAY)
        self.assertTrue(result['ready'])
        self.assertEqual(result['delta'],700)
        before,after=result['periods']
        self.assertEqual(before['sales']['orders'],7)
        self.assertEqual(after['sales']['gross_items'],1400)
        self.assertEqual(before['visits'],700)
        self.assertEqual(after['visits'],1400)
        self.assertEqual(after['ratio'],.5)
        self.assertEqual(after['start'],DAY+timedelta(days=1))
        self.assertEqual(before['end'],DAY-timedelta(days=1))

    def test_last_after_day_is_not_closed_until_next_brazilian_day(self):
        result=compare(ITEM,DAY,*sample(),DAY+timedelta(days=7))
        self.assertFalse(result['ready'])
        self.assertEqual(result['closed_after'],6)
        self.assertIsNone(result['delta'])
        self.assertIsNone(result['periods'][1]['sales']['orders'])
        self.assertEqual(result['periods'][1]['visits_days'],6)
        self.assertIsNone(result['periods'][1]['visits'])

    def test_partial_visits_and_unverified_sales_do_not_become_zero(self):
        orders,items,covered,visits=sample()
        result=compare(ITEM,DAY,orders,items,covered,visits[:-1],TODAY,pending=True)
        self.assertIsNone(result['delta'])
        self.assertIsNone(result['periods'][1]['ratio'])
        self.assertIsNone(result['periods'][1]['visits'])
        self.assertEqual(result['periods'][1]['visits_days'],6)
        result=compare(ITEM,DAY,orders,items,covered[:-1],visits,TODAY)
        self.assertIsNone(result['delta'])

    def test_verified_zero_is_valid_but_no_percent_from_zero_baseline(self):
        orders,items,covered,visits=sample()
        result=compare(ITEM,DAY,[],[],covered,visits,TODAY)
        self.assertEqual(result['delta'],0)
        self.assertIsNone(result['percent'])
        self.assertEqual(result['periods'][1]['ratio'],0)

    def test_validation_rejects_future_old_dates_invalid_kind_and_replay_key(self):
        self.assertEqual(validate(form(),TODAY)[0],DAY)
        cases=[dict(event_date=(TODAY+timedelta(days=1)).isoformat()),dict(event_date=(TODAY-timedelta(days=366)).isoformat()),dict(kind='unknown'),dict(note='curto'),dict(note='x'*1501),dict(submission_key='bad'),dict(event_date='invalid')]
        for change in cases:
            data=form();data.update(change)
            with self.assertRaises(ValueError):validate(data,TODAY)

    def test_one_comparison_uses_six_store_scoped_reads_and_counts_overlap(self):
        query=Mock(side_effect=[[],[],[],[],[dict(pending=False)],[dict(n=3)]])
        result=load_comparison(None,query,42,ITEM,DAY,TODAY)
        self.assertEqual(query.call_count,6)
        self.assertEqual(result['other_actions'],2)
        for call in query.call_args_list:
            self.assertIn('conexao_id=%s',call.args[1])
            self.assertEqual(call.args[2][0],42)
        self.assertIn('item_id=%s',query.call_args_list[3].args[1])

    def test_comparison_discloses_manual_record_overlap_and_causal_limits(self):
        result=compare(ITEM,DAY,*sample(),TODAY);result['other_actions']=2
        output=comparison_html(result,dict(event_date=DAY))
        self.assertIn('2 outro(s)',output)
        self.assertIn('não confirma execução no Mercado Livre',output)
        self.assertIn('sem atribuir causalidade',output)
        self.assertIn('12/10/2026',output)


class InterventionRouteTests(unittest.TestCase):
    def setUp(self):
        self.app=Flask(__name__);self.app.secret_key='test';self.app.testing=True
        self.query=Mock(side_effect=self.read)
        self.execute=Mock()
        self.rows=[];self.total=0
        def login(fn):
            @wraps(fn)
            def guarded(*args,**kwargs):
                return fn(*args,**kwargs) if session.get('usuario_id') else redirect('/login')
            return guarded
        register_interventions(self.app,login,lambda cid:session.get('tipo')=='admin' or session.get('conexao_id')==cid,lambda:contextlib.nullcontext(None),self.query,self.execute,lambda *args:args[-1],today=lambda:TODAY)
        self.client=self.app.test_client();self.path='/anuncios/1/'+ITEM+'/acoes'
        with self.client.session_transaction() as s:s.update(usuario_id=1,tipo='admin',intervention_csrf='test-csrf')

    def read(self,conn,sql,params):
        if 'JOIN anuncios' in sql:return [dict(cliente='Loja',titulo='Produto')]
        if 'COUNT(*)' in sql:return [dict(n=self.total)]
        if 'UPDATE listing_interventions' in sql:return []
        return self.rows

    def test_permissions_and_csrf_fail_before_reads_or_writes(self):
        self.assertEqual(self.app.test_client().get(self.path).status_code,302)
        with self.client.session_transaction() as s:s.update(tipo='cliente',conexao_id=2)
        self.assertEqual(self.client.get(self.path).status_code,403)
        with self.client.session_transaction() as s:s.update(conexao_id=1)
        self.assertEqual(self.client.post(self.path,data=form(csrf_token='test-csrf')).status_code,403)
        with self.client.session_transaction() as s:s.update(tipo='admin')
        self.assertEqual(self.client.post(self.path,data=form(csrf_token='wrong')).status_code,400)
        self.query.assert_not_called();self.execute.assert_not_called()

    def test_create_uses_bound_store_item_and_preserves_note_as_data(self):
        data=form(csrf_token='test-csrf');data['note']='<script>literal note</script>'
        with patch('requests.get',side_effect=AssertionError('No API on action registration')):
            response=self.client.post(self.path,data=data)
        self.assertEqual(response.status_code,303)
        params=self.execute.call_args.args[2]
        self.assertEqual(params[:2],(1,ITEM))
        self.assertEqual(params[4],data['note'])
        self.assertIn('ON CONFLICT',self.execute.call_args.args[1])

    def test_foreign_record_cannot_be_voided(self):
        response=self.client.post(self.path,data=dict(operation='void',action_id='999',csrf_token='test-csrf'))
        self.assertEqual(response.status_code,404)
        call=self.query.call_args
        self.assertIn('item_id=%s',call.args[1]);self.assertIn('conexao_id=%s',call.args[1])
        self.assertEqual(call.args[2][-2:],(1,ITEM))

    def test_invalid_form_stays_visible_escaped_and_does_not_write(self):
        data=form(csrf_token='test-csrf');data.update(event_date='bad',note='<script>bad</script>')
        response=self.client.post(self.path,data=data)
        self.assertEqual(response.status_code,400)
        self.assertIn('&lt;script&gt;bad&lt;/script&gt;',response.text)
        self.execute.assert_not_called()

    def test_pagination_limits_history_to_ten_and_clamps_page(self):
        self.total=31
        response=self.client.get(self.path+'?pagina=999')
        self.assertEqual(response.status_code,200)
        self.assertIn('Página 4 de 4',response.text)
        self.assertIn('LIMIT 10 OFFSET %s',self.query.call_args.args[1])
        self.assertEqual(self.query.call_args.args[2],(1,ITEM,30))


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class InterventionDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
        import main
        cls.m=main
        if main.scheduler.running:main.scheduler.shutdown(wait=False)
        main.iniciar_banco()
        main.app.testing=True

    def setUp(self):
        with self.m.banco() as conn:
            self.cid=self.m.consultar(conn,"INSERT INTO conexoes(cliente) VALUES('Action Test') RETURNING id")[0]['id']
            self.m.executar(conn,'INSERT INTO anuncios(conexao_id,item_id,titulo) VALUES(%s,%s,%s)',(self.cid,ITEM,'Teste'))
        self.client=self.m.app.test_client()
        with self.client.session_transaction() as s:s.update(usuario_id=1,tipo='admin',intervention_csrf='test-csrf')
        self.path=f'/anuncios/{self.cid}/{ITEM}/acoes'

    def tearDown(self):
        with self.m.banco() as conn:
            self.m.executar(conn,'DELETE FROM anuncios WHERE conexao_id=%s',(self.cid,))
            self.m.executar(conn,'DELETE FROM conexoes WHERE id=%s',(self.cid,))

    def test_idempotence_void_preserves_audit_and_get_has_no_network(self):
        from sales_metrics import reporting_today
        data=form(csrf_token='test-csrf');data['event_date']=reporting_today().isoformat()
        for _ in range(2):self.assertEqual(self.client.post(self.path,data=data).status_code,303)
        with self.m.banco() as conn:
            rows=self.m.consultar(conn,'SELECT * FROM listing_interventions WHERE conexao_id=%s',(self.cid,))
        self.assertEqual(len(rows),1)
        aid=rows[0]['id']
        with patch('requests.get',side_effect=AssertionError('No API during report')):
            response=self.client.get(self.path+'?acao='+str(aid))
        self.assertEqual(response.status_code,200)
        self.assertIn('Aguardando os 7 dias seguintes',response.text)
        self.assertEqual(self.client.post(self.path,data=dict(operation='void',action_id=aid,csrf_token='test-csrf')).status_code,303)
        with self.m.banco() as conn:rows=self.m.consultar(conn,'SELECT * FROM listing_interventions WHERE conexao_id=%s',(self.cid,))
        self.assertEqual(len(rows),1);self.assertIsNotNone(rows[0]['void_at'])
        self.assertIn('Registro desconsiderado',self.client.get(self.path+'?acao='+str(aid)).text)

    def test_customer_cannot_create_and_other_listing_cannot_read_record(self):
        from sales_metrics import reporting_today
        data=form(csrf_token='test-csrf');data['event_date']=reporting_today().isoformat()
        self.client.post(self.path,data=data)
        with self.m.banco() as conn:
            aid=self.m.consultar(conn,'SELECT id FROM listing_interventions WHERE conexao_id=%s',(self.cid,))[0]['id']
            self.m.executar(conn,'INSERT INTO anuncios(conexao_id,item_id) VALUES(%s,%s)',(self.cid,'MLB200'))
        other=self.path.replace(ITEM,'MLB200')
        self.assertEqual(self.client.get(other+'?acao='+str(aid)).status_code,404)
        self.assertEqual(self.client.post(other,data=dict(operation='void',action_id=aid,csrf_token='test-csrf')).status_code,404)
        with self.client.session_transaction() as s:s.update(tipo='cliente',conexao_id=self.cid)
        self.assertEqual(self.client.post(self.path,data=data).status_code,403)
        self.assertNotIn('Registrar ação realizada',self.client.get(self.path).text)

if __name__=='__main__':unittest.main()
