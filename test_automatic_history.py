import json
import os
import time
import unittest
from unittest.mock import Mock,patch
from automatic_history import listing_values,full_values,record,detail_html

ITEM='MLB100'


class AutomaticHistoryTests(unittest.TestCase):
    def test_snapshot_identity_missing_fields_and_same_count_photo_replacement(self):
        item=dict(seller_id=7,title='Produto',status='active',available_quantity=0,
                  pictures=[dict(id='A'),dict(id='B')],shipping=dict(logistic_type='fulfillment',free_shipping=False))
        values=listing_values(item,7)
        self.assertEqual(values['fotos'],['A','B'])
        self.assertEqual(values['disponibilidade'],'zerado')
        self.assertIs(values['frete_gratis'],False)
        item['pictures']=[dict(id='B'),dict(id='C')]
        self.assertNotEqual(listing_values(item,7)['fotos'],values['fotos'])
        self.assertTrue(all(v is None for v in listing_values(item,8).values()))
        self.assertIsNone(listing_values(dict(seller_id=7),7)['fotos'])
        self.assertIsNone(listing_values(dict(seller_id=7,available_quantity=True),7)['disponibilidade'])

    def test_unknown_full_never_becomes_zero(self):
        self.assertIsNone(full_values(dict(state='unknown',logistics='fulfillment'))['full'])
        self.assertIsNone(full_values(dict(state='empty',logistics='other'))['full'])
        self.assertEqual(full_values(dict(state='empty',logistics='fulfillment'))['full'],'empty')

    def test_record_is_one_parameterized_call_and_known_fields_only(self):
        execute=Mock();record(None,execute,42,ITEM,'listing',100,dict(titulo='<script>',unknown='ignored'))
        self.assertEqual(execute.call_count,1)
        self.assertEqual(execute.call_args.args[2][:4],(42,ITEM,'listing',100))
        payload=json.loads(execute.call_args.args[2][4])
        self.assertEqual(payload['titulo']['value'],'<script>')
        self.assertNotIn('unknown',payload)

    def test_price_hook_uses_confirmed_final_price_and_unknown_is_null(self):
        from offer_history import record as offer
        execute=Mock()
        offer(None,execute,42,ITEM,dict(sale_price=dict(checked_at=100,data=dict(amount=80,currency_id='BRL'))))
        calls=[c for c in execute.call_args_list if 'record_listing_changes' in c.args[1]]
        self.assertEqual(json.loads(calls[0].args[2][-1])['preco_final']['value'],'80.00')
        execute.reset_mock()
        offer(None,execute,42,ITEM,dict(sale_price=dict(checked_at=200,error='HTTP 403',data={})))
        call=next(c for c in execute.call_args_list if 'record_listing_changes' in c.args[1])
        self.assertIsNone(json.loads(call.args[2][-1])['preco_final']['value'])

    def test_automatic_detail_is_escaped_and_discloses_observation_time(self):
        output=detail_html(dict(source='automatic',field='titulo',before_value='<script>',after_value='Novo título',previous_at=100,created_at=200))
        self.assertIn('&lt;script&gt;',output)
        self.assertNotIn('<script>',output)
        self.assertIn('não identifica o horário exato nem o autor',output)


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class AutomaticHistoryDatabaseTests(unittest.TestCase):
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
            self.cid=self.m.consultar(conn,"INSERT INTO conexoes(cliente) VALUES('Automatic History Test') RETURNING id")[0]['id']
            self.m.executar(conn,'INSERT INTO anuncios(conexao_id,item_id,titulo) VALUES(%s,%s,%s)',(self.cid,ITEM,'Produto'))
        self.stamp=int(time.time())-7200

    def tearDown(self):
        with self.m.banco() as conn:
            self.m.executar(conn,'DELETE FROM anuncios WHERE conexao_id=%s',(self.cid,))
            self.m.executar(conn,'DELETE FROM full_observations WHERE conexao_id=%s',(self.cid,))
            self.m.executar(conn,'DELETE FROM conexoes WHERE id=%s',(self.cid,))

    def observe(self,values,offset=0,stream='listing'):
        with self.m.banco() as conn:record(conn,self.m.executar,self.cid,ITEM,stream,self.stamp+offset,values)

    def events(self):
        with self.m.banco() as conn:return self.m.consultar(conn,'SELECT * FROM listing_change_events WHERE conexao_id=%s ORDER BY id',(self.cid,))

    def test_first_read_stability_change_and_replay_are_distinct(self):
        self.observe(dict(titulo='Antes',fotos=['A','B']))
        self.observe(dict(titulo='Antes',fotos=['A','B']),10)
        self.assertEqual(self.events(),[])
        self.observe(dict(titulo='Depois',fotos=['B','A']),20)
        self.observe(dict(titulo='Depois',fotos=['B','A']),20)
        self.observe(dict(titulo='Stale',fotos=[]),15)
        rows=self.events();self.assertEqual(len(rows),2)
        title=next(r for r in rows if r['field']=='titulo')
        self.assertEqual(title['before_value'],'Antes');self.assertEqual(title['after_value'],'Depois')
        self.assertEqual(title['previous_at'],self.stamp+10)

    def test_unknown_breaks_comparison_and_streams_stay_independent(self):
        self.observe(dict(full='available'),stream='full')
        self.observe(dict(full=None),10,stream='full')
        self.observe(dict(full='empty'),20,stream='full')
        self.assertEqual(self.events(),[])
        self.observe(dict(full='available'),30,stream='full')
        self.observe(dict(preco_final='80.00'),stream='price')
        self.observe(dict(preco_final='100.00'),40,stream='price')
        self.assertEqual(len(self.events()),2)
        self.assertEqual({r['stream'] for r in self.events()},{'full','price'})

    def test_new_events_flow_into_page_and_automatic_entries_have_no_void_form(self):
        self.observe(dict(titulo='Antes'))
        self.observe(dict(titulo='Depois'),10)
        client=self.m.app.test_client()
        with client.session_transaction() as s:s.update(usuario_id=1,tipo='admin')
        path=f'/anuncios/{self.cid}/{ITEM}/acoes'
        with patch('requests.get',side_effect=AssertionError('History must not call ML')):
            response=client.get(path)
        self.assertEqual(response.status_code,200)
        self.assertIn('Histórico automático do anúncio',response.text)
        self.assertIn('Depois',response.text)
        self.assertNotIn('Desconsiderar registro',response.text)
        aid=self.events()[0]['id']
        self.assertEqual(client.get(path+f'?acao={aid}&origem=automatic').status_code,200)
        self.assertEqual(client.get(path+f'?acao={aid}&origem=manual').status_code,404)
        with client.session_transaction() as s:s.update(tipo='cliente',conexao_id=self.cid+1)
        self.assertEqual(client.get(path).status_code,403)

    def test_existing_price_observations_seed_reference_without_rewriting_it(self):
        from automatic_history import seed_existing
        from offer_history import record as offer
        with self.m.banco() as conn:
            for offset,price in [(0,80),(60,100)]:
                self.m.executar(conn,'''INSERT INTO listing_offer_observations
                    (conexao_id,item_id,observed_at,price,confirmed) VALUES(%s,%s,%s,%s,TRUE)''',
                    (self.cid,ITEM,self.stamp+offset,price))
            seed_existing(conn,self.m.executar)
            seed_existing(conn,self.m.executar)
            ref=self.m.consultar(conn,"SELECT * FROM listing_change_baselines WHERE conexao_id=%s AND item_id=%s AND stream='price'",(self.cid,ITEM))[0]
            self.assertEqual(ref['payload']['preco_final']['value'],'100.00')
            offer(conn,self.m.executar,self.cid,ITEM,dict(sale_price=dict(checked_at=self.stamp+120,data=dict(amount=120,currency_id='BRL'))))
        change=next(r for r in self.events() if r['observed_at']==self.stamp+120)
        self.assertEqual(change['before_value'],'100.00');self.assertEqual(change['after_value'],'120.00')

    def test_price_collector_hook_persists_events_in_same_transaction(self):
        from offer_history import record as offer
        for offset,value in [(0,80),(60,100)]:
            with self.m.banco() as conn:
                offer(conn,self.m.executar,self.cid,ITEM,dict(sale_price=dict(checked_at=self.stamp+offset,data=dict(amount=value,currency_id='BRL'))))
        rows=self.events();self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['before_value'],'80.00');self.assertEqual(rows[0]['after_value'],'100.00')

if __name__=='__main__':unittest.main()
