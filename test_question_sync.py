import contextlib
import unittest
from unittest.mock import Mock
from types import SimpleNamespace
import requests
from question_sync import collect, read
from listing_questions import model, persist

NOW = 1793337000


def question(i=1, **changes):
    row = dict(id=i, seller_id=7, item_id='MLB123', text='Serve neste modelo?', status='UNANSWERED',
               answer=None, date_created='2026-10-30T00:00:00Z', deleted_from_listing=False, hold=False)
    row.update(changes)
    return row


def page(rows, total=None, offset=0):
    return dict(questions=rows, total=len(rows) if total is None else total, limit=50, filters=dict(offset=offset))


def response(data=None, status=200):
    return SimpleNamespace(status_code=status, json=lambda:data)


class QuestionSyncTests(unittest.TestCase):
    def run_sync(self, responses, old=None):
        self.get = Mock(side_effect=responses)
        self.query = Mock(side_effect=[[dict(acquired=True)], old or []])
        self.execute = Mock()
        self.error = Mock()
        return collect(9,'synthetic',7,lambda:contextlib.nullcontext(None),self.query,self.execute,self.get,self.error,NOW)

    def writes(self):
        return [c.args[2] for c in self.execute.call_args_list if 'INSERT INTO perguntas(' in c.args[1]]

    def coverage(self):
        return self.execute.call_args.args[2]

    def test_two_pages_and_two_old_statuses_are_bounded_and_separate(self):
        result = self.run_sync([
            response(page([question(i) for i in range(1,51)], total=120)),
            response(page([question(i) for i in range(51,101)], total=120,offset=50)),
            response(question(1001,status='ANSWERED',answer=dict(text='Sim',status='ACTIVE'))),
            response(question(1002,status='DELETED',deleted_from_listing=True)),
        ], [dict(pergunta_id='1001',item_id='MLB123'),dict(pergunta_id='1002',item_id='MLB123')])
        self.assertTrue(result);self.assertEqual(self.get.call_count,4)
        self.assertEqual(self.get.call_args_list[1].kwargs['params']['offset'],50)
        self.assertTrue(all(c.kwargs['timeout']==(3,8) and c.kwargs['allow_redirects'] is False for c in self.get.call_args_list))
        self.assertEqual(len(self.writes()),102)
        self.assertEqual(self.writes()[-2][4],'ANSWERED')
        self.assertEqual(self.writes()[-1][4],'DELETED')
        self.assertEqual(self.coverage()[3:9],('partial',2,100,120,2,0))
        self.assertEqual(self.query.call_args.args[2],(9,NOW-21600,2))
        self.assertIn('consulta_em ASC NULLS FIRST',self.query.call_args.args[1])

    def test_404_is_unknown_and_never_inferred_deleted(self):
        self.assertTrue(self.run_sync([response(page([])),response(status=404)], [dict(pergunta_id='2',item_id='MLB123')]))
        self.assertEqual(self.writes(),[])
        update=next(c for c in self.execute.call_args_list if 'UPDATE perguntas SET' in c.args[1])
        self.assertNotIn('status=',update.args[1]);self.assertNotIn('DELETED',update.args[1])
        self.assertEqual(update.args[2],(NOW,'HTTP 404',9,'2'))
        self.assertEqual(self.coverage()[8],1)

    def test_429_stops_all_further_requests_and_preserves_valid_first_page(self):
        self.assertFalse(self.run_sync([response(page([question(i) for i in range(1,51)],total=300)),response(status=429)]))
        self.assertEqual(self.get.call_count,2);self.assertEqual(self.query.call_count,1)
        self.assertEqual(len(self.writes()),50)
        self.assertEqual(self.coverage()[3:7],('partial',1,50,300))
        self.error.assert_called_once_with(9,'perguntas','HTTP 429')

    def test_wrong_seller_or_malformed_batch_cannot_partially_write(self):
        for invalid in (question(2,seller_id=8),question(2,answer=[]),question(2,deleted_from_listing='false'),question(True)):
            self.assertFalse(self.run_sync([response(page([question(),invalid]))]))
            self.assertEqual(self.writes(),[]);self.assertEqual(self.get.call_count,1)
            self.assertEqual(self.coverage()[3],'unknown')
        payload=page([question()]);payload['questions'][0]['from']={'email':'private@example.invalid'}
        self.assertTrue(self.run_sync([response(payload)]))
        self.assertNotIn('private@example.invalid',str(self.execute.call_args_list))

    def test_total_or_offsets_missing_and_shifting_pages_never_certify_coverage(self):
        self.assertTrue(self.run_sync([response(dict(questions=[question()])),response(dict(questions=[]))]))
        self.assertEqual(self.coverage()[3],'partial')
        self.assertTrue(self.run_sync([
            response(page([question(i) for i in range(1,51)],total=100)),
            response(page([question(i) for i in range(50,100)],total=100,offset=50)),
        ]))
        self.assertEqual(self.coverage()[3:7],('partial',2,99,100))

    def test_mismatched_detail_binding_preserves_last_record(self):
        self.assertFalse(self.run_sync([response(page([])),response(question(99))], [dict(pergunta_id='2',item_id='MLB123')]))
        self.assertEqual(self.writes(),[])
        self.assertEqual(self.coverage()[8],1)
        self.assertEqual(self.get.call_count,2)

    def test_busy_lock_and_invalid_connection_do_not_call_marketplace(self):
        get=Mock();query=Mock(return_value=[dict(acquired=False)]);execute=Mock()
        self.assertTrue(collect(9,'synthetic',7,lambda:contextlib.nullcontext(None),query,execute,get,Mock(),NOW))
        get.assert_not_called();execute.assert_not_called()
        self.assertFalse(collect(9,'synthetic',True,Mock(),Mock(),Mock(),get,Mock(),NOW))
        get.assert_not_called()

    def test_transport_network_error_has_no_raw_payload_or_token(self):
        with self.assertRaisesRegex(ValueError,'Rede ou resposta'):
            read('synthetic','/questions/1',{},Mock(side_effect=requests.Timeout('do not leak raw error')))

    def test_recent_pending_excludes_stale_hidden_held_wrong_store_and_unknown(self):
        def row(i,**kw):
            return dict(dict(pergunta_id=str(i),texto='Pergunta',status='UNANSWERED',consulta_estado='read',
                status_confirmado_em=NOW,vendedor_confirmado='7',excluida_do_anuncio=False,em_espera=False),**kw)
        rows=[row(1),row(2,status='BANNED'),row(3,status='DELETED'),row(4,status='ANSWERED'),
              row(5,consulta_estado='unknown'),row(6,status_confirmado_em=NOW-21601),
              row(7,status_confirmado_em=NOW+1),row(8,vendedor_confirmado='8'),
              row(9,excluida_do_anuncio=True),row(10,em_espera=True),row(11,em_espera=None)]
        data=model(rows,{},NOW,7)
        self.assertEqual(data['pending'],1);self.assertEqual(data['recent']['ANSWERED'],1)
        self.assertEqual(data['unknown'],4)
        self.assertEqual(model(rows,{},NOW,8)['pending'],1)

    def test_canonical_duplicate_ids_and_absent_fields_are_rejected_before_write(self):
        execute=Mock()
        with self.assertRaises(ValueError):
            persist(None,execute,9,dict(questions=[question(1),question('01')]),NOW,7)
        execute.assert_not_called()
        bad=question();del bad['text']
        with self.assertRaises(ValueError):persist(None,execute,9,dict(questions=[bad]),NOW,7)
        execute.assert_not_called()

class QuestionRefreshTests(unittest.TestCase):
    def test_refresh_collects_only_questions_with_existing_dispatcher(self):
        from test_section_refresh import production_function
        import section_refresh
        functions={name:Mock(side_effect=AssertionError('unrelated collector')) for name in ('puxar_ads','puxar_anuncios','puxar_pedidos','puxar_envios','puxar_full','puxar_promocoes')}
        functions['puxar_perguntas']=Mock(return_value=True)
        collect=production_function('coletar_secao',dict(functions,banco=lambda:contextlib.nullcontext(None),
            consultar=Mock(return_value=[dict(user_id=7)]),token_atual=lambda c:'synthetic'))
        self.assertEqual(section_refresh.collector_names('perguntas'),('puxar_perguntas',))
        self.assertTrue(collect(9,'perguntas'))
        functions['puxar_perguntas'].assert_called_once_with(9,'synthetic',7)
        for name,fn in functions.items():
            if name!='puxar_perguntas':fn.assert_not_called()

    def test_page_has_one_question_refresh_and_keeps_listing_navigation(self):
        import html
        from flask import Flask
        from listing_questions import render
        from test_listing_details import main_function
        app=Flask(__name__);app.secret_key='isolated'
        page=main_function('pagina_loja',dict(session={'tipo':'admin'},esc=html.escape,CSS='',VISUAL_CSS='',SCRIPT='',img_logo=lambda size:''))
        with app.test_request_context('/'):
            text=page('Perguntas',9,'Loja','anuncios',render(9,'MLB123',{},model([],{},NOW,7)))
        self.assertEqual(text.count("class='k-refresh'"),1)
        self.assertIn("data-endpoint='/atualizacoes/9/perguntas'",text)
        self.assertIn('Atualizar Perguntas',text)
        self.assertNotIn('Atualizar Anúncios',text)
        import re
        self.assertTrue(bool(re.search(r"<a[^>]*href='/anuncios/9'[^>]*aria-current='page'",text)))
