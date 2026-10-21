import os
import time
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from functools import wraps
from types import SimpleNamespace
from unittest.mock import Mock, patch

from flask import Flask, session, redirect
from competitor_monitor import (item_from_link, observe, slot_at, next_slot,
                                SLOT_SECONDS, collect_due, init_competitor_schema)
from competitor_routes import BR, register_competitors

ITEM = 'MLB1234567890'


def response(payload, status=200):
    return SimpleNamespace(status_code=status, json=lambda: payload)


def item(full='fulfillment', **extra):
    return dict(id=ITEM, seller_id=123, title='Concorrente <script>', status='active',
                shipping={'logistic_type':full}, **extra)


class CompetitorTests(unittest.TestCase):
    def test_links_pin_seller_offer_not_catalog_winner(self):
        for link in [ITEM, 'MLB-1234567890',
                     'https://produto.mercadolivre.com.br/MLB-1234567890-produto-_JM',
                     'https://www.mercadolivre.com.br/produto/p/MLB99999999?wid='+ITEM,
                     'https://www.mercadolivre.com.br/produto/up/MLBU99999?pdp_filters=item_id%3A'+ITEM]:
            self.assertEqual(item_from_link(link),ITEM)
        for link in ['https://evil.com/?wid='+ITEM, 'https://www.mercadolivre.com.br.evil.com/'+ITEM,
                     'https://www.mercadolivre.com.br@evil.com/'+ITEM,
                     'https://www.mercadolivre.com.br/p/MLB99999999',
                     'https://www.mercadolivre.com.br/up/MLBU99999999',
                     'http://127.0.0.1/'+ITEM, 'javascript:alert(1)',
                     'https://www.mercadolivre.com.br:bad/?wid='+ITEM,
                     'https://www.mercadolivre.com.br/?wid='+ITEM+'&wid=MLB9999999999',
                     'https://produto.mercadolivre.com.br/MLB-1234567890-title?wid=MLB9999999999']:
            with self.subTest(link=link), self.assertRaises(ValueError):
                item_from_link(link)

    def test_actual_sale_price_including_promotion_and_return_to_normal(self):
        for amount in ('99.90','120.00'):
            getter=Mock(side_effect=[response(item(price=120)),
                                    response({'amount':amount,'regular_amount':120,'currency_id':'BRL'})])
            result=observe(ITEM,None,'never-persist-token',getter)
            self.assertEqual(result['price'],Decimal(amount))
            self.assertIs(result['full'],True)
            self.assertEqual(result['error'],'')
            self.assertEqual(getter.call_args.kwargs['params'],{'context':'channel_marketplace','quantity':1})
            self.assertFalse(getter.call_args.kwargs['allow_redirects'])
            self.assertEqual(getter.call_args.kwargs['timeout'],(3,7))

    def test_price_failure_keeps_full_without_using_items_old_price(self):
        getter=Mock(side_effect=[response(item(price=120)),response({},403)])
        result=observe(ITEM,None,'test',getter)
        self.assertIsNone(result['price'])
        self.assertIs(result['full'],True)
        self.assertIn('403',result['error'])
        self.assertNotIn('test',result['error'])
        for value in (None,'NaN','Infinity',-1,0,True):
            getter=Mock(side_effect=[response(item()),response({'amount':value,'currency_id':'BRL'})])
            self.assertIsNone(observe(ITEM,None,'token',getter)['price'])

    def test_net_prices_include_tax_and_other_currency_is_unknown(self):
        for sale, expected in [({'amount':80,'amount_tax_inclusion_type':'net','amount_with_taxes':100,'currency_id':'BRL'},Decimal('100')),
                               ({'amount':80,'amount_tax_inclusion_type':'net','currency_id':'BRL'},None),
                               ({'amount':80,'currency_id':'USD'},None)]:
            getter=Mock(side_effect=[response(item()),response(sale)])
            self.assertEqual(observe(ITEM,None,'token',getter)['price'],expected)

    def test_unknown_full_is_not_false_and_non_full_is_explicit(self):
        for logistic, expected in [(None,None),('new_future_type',None),('cross_docking',False),('drop_off',False)]:
            getter=Mock(side_effect=[response(item(logistic)),response({'amount':100,'currency_id':'BRL'})])
            self.assertIs(observe(ITEM,None,'token',getter)['full'],expected)

    def test_identity_mismatch_blocks_price_and_full(self):
        for payload in [dict(item(),id='MLB999999999'),dict(item(),seller_id=999),dict(item(),seller_id=None)]:
            getter=Mock(return_value=response(payload))
            result=observe(ITEM,123,'token',getter)
            self.assertIsNone(result['price']);self.assertIsNone(result['full'])
            self.assertEqual(getter.call_count,1)
        getter=Mock(side_effect=TimeoutError('token-sensitive'))
        result=observe(ITEM,None,'token-sensitive',getter)
        self.assertNotIn('token-sensitive',result['error'])

    def test_inactive_item_cannot_report_a_buyable_price(self):
        getter=Mock(return_value=response(dict(item(),status='paused',price=100)))
        result=observe(ITEM,None,'token',getter)
        self.assertIsNone(result['price'])
        self.assertEqual(getter.call_count,1)

    def test_ten_slots_per_brazilian_calendar_day(self):
        start=int(datetime(2026,10,20,tzinfo=BR).timestamp())
        self.assertEqual(len({slot_at(start+i*60) for i in range(24*60)}),10)
        self.assertEqual(next_slot(start),start+SLOT_SECONDS)
        self.assertEqual(slot_at(start-1)+1,slot_at(start))
        times=[datetime.fromtimestamp(start+i*SLOT_SECONDS,BR).strftime('%H:%M') for i in range(10)]
        self.assertEqual(times,['00:00','02:24','04:48','07:12','09:36','12:00','14:24','16:48','19:12','21:36'])
        self.assertEqual(slot_at(start+86400)-slot_at(start),10)


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'), 'isolated PostgreSQL not configured')
class CompetitorIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
        import main
        cls.m=main
        if main.scheduler.running:
            main.scheduler.shutdown(wait=False)
        main.app.config['TESTING']=True

    def setUp(self):
        self.ids=[]
        with self.m.banco() as conn:
            for name in ('Competitor A','Competitor B'):
                row=self.m.consultar(conn,"INSERT INTO conexoes(cliente,status,access_token,expires_at) VALUES(%s,'ativa','test-token',%s) RETURNING id",(name,int(time.time())+86400))[0]
                self.ids.append(row['id'])
        self.client=self.m.app.test_client()
        with self.client.session_transaction() as s:
            s.update(usuario_id=1,tipo='cliente',conexao_id=self.ids[0],competitor_csrf='csrf-test')
        self.path=f'/anuncios/{self.ids[0]}/concorrencia'

    def tearDown(self):
        with self.m.banco() as conn:
            self.m.executar(conn,'DELETE FROM conexoes WHERE id=ANY(%s)',(self.ids,))

    def add(self,cid=None,label='Competitor <script>'):
        with self.m.banco() as conn:
            return self.m.consultar(conn,'''INSERT INTO competitor_targets(conexao_id,item_id,label,created_at)
                VALUES(%s,%s,%s,%s) RETURNING id''',(cid or self.ids[0],ITEM,label,int(time.time())))[0]['id']

    def target(self,target_id):
        with self.m.banco() as conn:
            return self.m.consultar(conn,'SELECT * FROM competitor_targets WHERE id=%s',(target_id,))[0]

    def run_collection(self,stamp,price='100',full='fulfillment',failed=False):
        getter=Mock(side_effect=[response(item(full)),response({},403) if failed else response({'amount':price,'currency_id':'BRL'})])
        collect_due(self.m.banco,self.m.consultar,self.m.executar,getter,clock=lambda:stamp)
        return getter

    def test_access_control_csrf_and_store_scoping(self):
        own=self.add();other=self.add(self.ids[1],label='SECRET FOREIGN')
        self.assertEqual(self.m.app.test_client().get(self.path).status_code,302)
        self.assertEqual(self.client.get(f'/anuncios/{self.ids[1]}/concorrencia').status_code,403)
        self.assertEqual(self.client.get(self.path+'/'+str(other)).status_code,404)
        self.assertEqual(self.client.post(self.path,data={'link':ITEM}).status_code,400)
        self.assertEqual(self.client.post(self.path,data={'link':ITEM,'csrf_token':'ç'}).status_code,400)
        self.assertEqual(self.client.post(self.path+f'/{other}/estado',data={'ativo':'0','csrf_token':'csrf-test'}).status_code,404)
        with patch.object(self.m.requests,'get',side_effect=AssertionError('GET report must be cached')):
            result=self.client.get(self.path)
        self.assertEqual(result.status_code,200)
        self.assertIn('Competitor &lt;script&gt;',result.text)
        self.assertNotIn('SECRET FOREIGN',result.text)
        self.assertIn('Concorrência',self.client.get('/anuncios/'+str(self.ids[0])).text)

    def test_registration_idempotence_pause_resume_and_invalid_link(self):
        for _ in range(2):
            self.assertEqual(self.client.post(self.path,data={'link':ITEM,'nome':'Loja','csrf_token':'csrf-test'}).status_code,303)
        with self.m.banco() as conn:
            rows=self.m.consultar(conn,'SELECT * FROM competitor_targets WHERE conexao_id=%s',(self.ids[0],))
        self.assertEqual(len(rows),1)
        tid=rows[0]['id']
        self.assertEqual(self.client.post(self.path+f'/{tid}/estado',data={'ativo':'0','csrf_token':'csrf-test'}).status_code,303)
        self.assertFalse(self.target(tid)['active'])
        self.assertEqual(self.client.post(self.path+f'/{tid}/estado',data={'ativo':'1','csrf_token':'csrf-test'}).status_code,303)
        self.assertTrue(self.target(tid)['active'])
        self.assertEqual(self.client.post(self.path,data={'link':'http://127.0.0.1/','csrf_token':'csrf-test'}).status_code,400)

    def test_slot_dedup_price_promotion_full_changes_and_failure(self):
        tid=self.add()
        now=int(time.time())
        self.run_collection(now)
        first=self.target(tid)
        self.assertEqual(first['price'],Decimal('100'))
        self.assertIsNone(first['price_changed_at'])
        getter=Mock(side_effect=AssertionError('duplicate same-slot call'))
        self.assertEqual(collect_due(self.m.banco,self.m.consultar,self.m.executar,getter,clock=lambda:now),0)
        getter.assert_not_called()
        self.run_collection(now+SLOT_SECONDS,price='80',full='cross_docking')
        after=self.target(tid)
        self.assertEqual(after['price'],Decimal('80'))
        self.assertEqual(after['previous_price'],Decimal('100'))
        self.assertFalse(after['full_state'])
        self.assertTrue(after['previous_full'])
        self.run_collection(now+2*SLOT_SECONDS,failed=True)
        failed=self.target(tid)
        self.assertEqual(failed['price'],Decimal('80'))
        self.assertEqual(failed['price_at'],after['price_at'])
        self.assertTrue(failed['full_state'])  # Partial success can still update Full.
        self.assertIn('403',failed['error'])
        self.run_collection(now+3*SLOT_SECONDS,price='100')
        end=self.target(tid)
        self.assertEqual(end['price'],Decimal('100'))
        self.assertEqual(end['previous_price'],Decimal('80'))
        with self.m.banco() as conn:
            history=self.m.consultar(conn,'SELECT * FROM competitor_observations WHERE target_id=%s ORDER BY slot',(tid,))
        self.assertEqual(len(history),4)
        self.assertFalse(history[0]['price_changed'])
        self.assertTrue(history[1]['price_changed'])
        self.assertTrue(history[1]['full_changed'])
        self.assertIsNone(history[2]['price'])
        self.assertFalse(history[2]['price_changed'])
        self.assertTrue(history[3]['price_changed'])

    def test_worker_claims_respect_locks_and_paused_targets(self):
        tid=self.add()
        locked=self.m.banco()
        try:
            self.m.consultar(locked,'SELECT id FROM competitor_targets WHERE id=%s FOR UPDATE',(tid,))
            getter=Mock(side_effect=AssertionError('locked target'))
            self.assertEqual(collect_due(self.m.banco,self.m.consultar,self.m.executar,getter),0)
            getter.assert_not_called()
        finally:
            locked.rollback();locked.close()
        with self.m.banco() as conn:
            self.m.executar(conn,'UPDATE competitor_targets SET active=FALSE WHERE id=%s',(tid,))
        getter=Mock(side_effect=AssertionError('paused target'))
        self.assertEqual(collect_due(self.m.banco,self.m.consultar,self.m.executar,getter),0)
        getter.assert_not_called()

    def test_pagination_filters_and_history(self):
        tid=self.add()
        with self.m.banco() as conn:
            for i in range(26):
                self.m.executar(conn,'''INSERT INTO competitor_targets(conexao_id,item_id,label,created_at,price,previous_price,full_state)
                    VALUES(%s,%s,%s,%s,80,100,FALSE)''',(self.ids[0],'MLB'+str(7000000000+i),'Only page '+str(i),i))
            self.m.executar(conn,'''INSERT INTO competitor_observations(target_id,slot,observed_at,price,previous_price,price_changed,full_changed)
                VALUES(%s,1,%s,80,100,TRUE,FALSE)''',(tid,int(time.time())))
        body=self.client.get(self.path).text
        self.assertIn('Página 1 de 2 · 27 registros',body)
        self.assertIn('Página 2 de 2 · 27 registros',self.client.get(self.path+'?pagina=2').text)
        self.assertIn('26 registros',self.client.get(self.path+'?preco=queda&full=nao').text)
        self.assertIn('1 registros',self.client.get(self.path+'?busca=Competitor').text)
        self.assertIn('0 registros',self.client.get(self.path+'?busca=%25').text)
        history=self.client.get(self.path+f'/{tid}?alteracoes=1').text
        self.assertIn('R$ 80,00',history)
        self.assertIn('−R$ 20,00',history)


    def test_link_to_own_listing_is_tenant_checked_and_preserved(self):
        own,foreign='MLB1111111111','MLB2222222222'
        try:
            with self.m.banco() as conn:
                self.m.executar(conn,'INSERT INTO anuncios(conexao_id,item_id) VALUES (%s,%s),(%s,%s)',(self.ids[0],own,self.ids[1],foreign))
            rejected=self.client.post(self.path,data={'link':ITEM,'meu_anuncio':foreign,'csrf_token':'csrf-test'})
            self.assertEqual(rejected.status_code,400)
            accepted=self.client.post(self.path,data={'link':ITEM,'meu_anuncio':own,'csrf_token':'csrf-test'})
            self.assertEqual(accepted.status_code,303)
            self.assertEqual(self.client.post(self.path,data={'link':ITEM,'csrf_token':'csrf-test'}).status_code,303)
            with self.m.banco() as conn:
                rows=self.m.consultar(conn,'SELECT own_item_id FROM competitor_targets WHERE conexao_id=%s',(self.ids[0],))
            self.assertEqual(rows[0]['own_item_id'],own)
            self.assertEqual(self.client.post(self.path,data={'link':ITEM,'meu_anuncio':ITEM,'csrf_token':'csrf-test'}).status_code,400)
        finally:
            with self.m.banco() as conn:
                self.m.executar(conn,'DELETE FROM anuncios WHERE conexao_id=ANY(%s)',(self.ids,))

    def test_offer_history_persists_and_reads_only_linked_store_evidence(self):
        from offer_history import record,load
        from datetime import date
        stamp=int(datetime(2026,10,19,12,tzinfo=BR).timestamp())
        snap={'sale_price':{'checked_at':stamp,'data':{'amount':80,'regular_amount':100,'currency_id':'BRL','metadata':{'promotion_id':'x'}}}}
        with self.m.banco() as conn:
            for cid in self.ids:
                record(conn,self.m.executar,cid,'MLB1111111111',snap)
            record(conn,self.m.executar,self.ids[0],'MLB1111111111',snap)
            data=load(conn,self.m.consultar,self.ids[0],'MLB1111111111',date(2026,10,20))
        self.assertEqual(len(data['own']),1)
        self.assertEqual(data['own'][0]['price'],Decimal('80'))
        self.assertTrue(data['own'][0]['promotion'])
        self.assertEqual(data['targets'],[])
