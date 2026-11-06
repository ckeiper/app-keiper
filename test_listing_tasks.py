import contextlib
from datetime import date,timedelta
from html import unescape
import os
import unittest
from unittest.mock import Mock,patch
from flask import Flask,session
from listing_tasks import validate,create,transition,load,MissingTask,StaleTask,init_schema
from listing_task_routes import register_tasks
from listing_task_view import render
from web_security import install_security

DAY=date(2026,10,25)
def form(key='k'*32):
    return dict(operation='create',title='Conferir estoque Full',responsible='Equipe da loja',due_date=DAY.isoformat(),description='Conferir a leitura antes de agir.',submission_key=key)
def task(**changes):
    row=dict(id=1,title='Conferir estoque Full',responsible='Equipe da loja',due_date=DAY-timedelta(days=1),description='<script>',status='open',version=1)
    row.update(changes);return row

def model():
    return dict(rows=[task()],counts=[dict(status='open',n=1,overdue=1)],status='open',total=1,page=1,pages=2,history=None,events=[],event_page=1,event_pages=1)

class ListingTaskTests(unittest.TestCase):
    def test_validation_dates_fields_and_submission_key(self):
        self.assertEqual(validate(form(),DAY)['due_date'],DAY)
        for changes in [dict(title='a'),dict(responsible=''),dict(description='x'*1501),dict(title='bad\x00name'),dict(due_date='bad'),dict(due_date=(DAY+timedelta(days=367)).isoformat()),dict(submission_key='bad')]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):validate(dict(form(),**changes),DAY)
        self.assertEqual(validate(dict(form(),due_date=(DAY+timedelta(days=366)).isoformat()),DAY)['due_date'],DAY+timedelta(days=366))

    def test_create_deduplicates_same_payload_and_rejects_different_payload(self):
        values=validate(form(),DAY);execute=Mock();query=Mock(return_value=[dict(id=3)])
        self.assertEqual(create(None,query,execute,7,'MLB1',values,1,now=123),3)
        self.assertEqual(execute.call_count,1);self.assertIn('listing_task_events',execute.call_args.args[1])
        old=dict(values,id=3);query=Mock(side_effect=[[],[old]]);execute.reset_mock()
        self.assertEqual(create(None,query,execute,7,'MLB1',values,1),3);execute.assert_not_called()
        query=Mock(side_effect=[[],[dict(old,title='Outra tarefa')]])
        with self.assertRaises(ValueError):create(None,query,execute,7,'MLB1',values,1)

    def test_transition_scope_version_conflict_and_audit(self):
        execute=Mock();query=Mock(return_value=[dict(version=2)])
        transition(None,query,execute,7,'MLB1',3,1,'open','done',1,now=123)
        self.assertIn('conexao_id=%s AND item_id=%s AND version=%s AND status=%s',query.call_args.args[1])
        self.assertEqual(execute.call_args.args[2],(3,7,'MLB1',2,'open','done',123,1))
        execute.reset_mock()
        with self.assertRaises(StaleTask):transition(None,Mock(side_effect=[[],[dict(id=3)]]),execute,7,'MLB1',3,1,'open','done',1)
        with self.assertRaises(MissingTask):transition(None,Mock(side_effect=[[],[]]),execute,7,'MLB1',3,1,'open','done',1)
        with self.assertRaises(ValueError):transition(None,query,execute,7,'MLB1',3,1,'done','cancelled',1)
        execute.assert_not_called()

    def test_load_filters_bound_reads_and_selected_history_scope(self):
        query=Mock(side_effect=[[],[dict(n=15)],[task()],[task()],[dict(n=21)],[]])
        result=load(None,query,7,'MLB1',dict(status='overdue',pagina='999',tarefa='1',historico_pagina='999'),DAY)
        self.assertEqual(result['page'],2);self.assertEqual(result['event_page'],3)
        for call in query.call_args_list:self.assertIn('conexao_id=%s AND item_id=%s',call.args[1])
        self.assertIn('LIMIT 10 OFFSET',query.call_args_list[2].args[1]);self.assertIn('LIMIT 10 OFFSET',query.call_args_list[-1].args[1])

    def test_render_escaping_csrf_due_status_and_pagination(self):
        text=render(7,'MLB1',dict(titulo='<script>'),model(),DAY,'token')
        self.assertNotIn('<script>',text);self.assertIn('&lt;script&gt;',text)
        self.assertIn('Atrasada',text);self.assertIn('name="_csrf" value="token"',text)
        self.assertIn('version" value="1"',text);self.assertIn('pagina=2',text)
        self.assertIn('não altera o anúncio',text)

    def test_admin_scope_and_csrf_block_before_any_read(self):
        app=Flask(__name__);app.secret_key='isolated'
        query=Mock();execute=Mock()
        register_tasks(app,lambda f:f,lambda cid:cid==7,lambda:contextlib.nullcontext(None),query,execute,lambda *a:a[-1],today=lambda:DAY)
        client=app.test_client()
        with client.session_transaction() as state:state.update(tipo='cliente',usuario_id=1)
        self.assertEqual(client.get('/anuncios/7/MLB1/tarefas').status_code,403)
        with client.session_transaction() as state:state.update(tipo='admin',usuario_id=1)
        self.assertEqual(client.get('/anuncios/8/MLB1/tarefas').status_code,403)
        self.assertEqual(client.post('/anuncios/7/MLB1/tarefas',data=form()).status_code,400)
        query.assert_not_called();execute.assert_not_called()

    def test_security_middleware_rejects_cross_origin(self):
        app=Flask(__name__);app.secret_key='isolated';install_security(app)
        query=Mock();register_tasks(app,lambda f:f,lambda cid:True,lambda:contextlib.nullcontext(None),query,Mock(),lambda *a:a[-1])
        client=app.test_client()
        with client.session_transaction() as state:state.update(tipo='admin',usuario_id=1,_csrf='token')
        response=client.post('/anuncios/7/MLB1/tarefas',data=dict(form(),_csrf='token'),headers={'Origin':'https://foreign.invalid'})
        self.assertEqual(response.status_code,400);query.assert_not_called()

    def test_question_draft_is_scoped_bounded_and_requires_manual_fields(self):
        from listing_tasks import question_draft
        query=Mock(return_value=[dict(pergunta_id='123',texto='<script>Questão</script>'+'x'*2000)])
        draft=question_draft(None,query,7,'MLB1','123')
        self.assertEqual(query.call_args.args[2],(7,'MLB1','123'))
        self.assertIn('conexao_id=%s AND item_id=%s AND pergunta_id=%s',query.call_args.args[1])
        self.assertEqual(set(draft),{'title','description'})
        self.assertLessEqual(len(draft['description']),1500);self.assertIn('trecho abreviado',draft['description'])
        self.assertIn('Pergunta #123 do anúncio MLB1',draft['description'])
        self.assertEqual(validate(dict(form(),**draft),DAY)['title'],'Revisar pergunta #123')
        text=render(7,'MLB1',{},model(),DAY,'token',values=draft)
        self.assertIn('id="lt-criar" open',text);self.assertNotIn('<script>Questão',text)
        self.assertIn('&lt;script&gt;Questão',text);self.assertIn('name="responsible" maxlength="80" required value=""',text)

    def test_question_draft_rejects_invalid_missing_or_unverifiable_source(self):
        from listing_tasks import question_draft,MissingQuestion
        for qid in ('','0','01','-1','1;SELECT','<script>','9'*21,True,1,None):
            query=Mock()
            with self.assertRaises(ValueError):question_draft(None,query,7,'MLB1',qid)
            query.assert_not_called()
        for rows in ([],[dict(pergunta_id='124',texto='Texto')],[dict(pergunta_id='123',texto=None)],
                     [dict(pergunta_id='123',texto=' ')],[dict(pergunta_id='123',texto='x'*20001)],
                     [dict(pergunta_id='123',texto='bad\x00text')],[dict(pergunta_id='123',texto='A')]*2):
            with self.assertRaises(MissingQuestion):question_draft(None,Mock(return_value=rows),7,'MLB1','123')

    def test_get_question_draft_does_not_create_task_and_keeps_access_controls(self):
        app=Flask(__name__);app.secret_key='draft';query=Mock();execute=Mock()
        register_tasks(app,lambda f:f,lambda cid:cid==7,lambda:contextlib.nullcontext(None),query,execute,lambda *a:a[-1],today=lambda:DAY)
        client=app.test_client();url='/anuncios/7/MLB1/tarefas?pergunta=123'
        self.assertEqual(client.get(url).status_code,403);query.assert_not_called()
        with client.session_transaction() as state:state.update(tipo='admin',usuario_id=1,_csrf='token')
        self.assertEqual(client.get(url.replace('/7/','/8/')).status_code,403);query.assert_not_called()
        query.side_effect=[[dict(cliente='Loja')],[dict(pergunta_id='123',texto='Qual a medida interna?')]]
        with patch('listing_task_routes.load',return_value=model()),patch('listing_task_routes.create',side_effect=AssertionError('GET write')):
            response=client.get(url)
        text=response.get_data(as_text=True);self.assertEqual(response.status_code,200)
        self.assertIn('Nenhuma tarefa foi criada',text);self.assertIn('Qual a medida interna?',text)
        self.assertEqual(query.call_count,2);self.assertTrue(all(call.args[1].lstrip().startswith('SELECT') for call in query.call_args_list))
        self.assertEqual(execute.call_count,1);self.assertIn('READ ONLY',execute.call_args.args[1])
        query.side_effect=[[dict(cliente='Loja')],[]]
        self.assertEqual(client.get(url).status_code,404)
        query.side_effect=[[dict(cliente='Loja')]]
        self.assertEqual(client.get(url.replace('123','bad')).status_code,400)

    def test_question_parameter_never_overwrites_posted_review_or_bypasses_csrf(self):
        app=Flask(__name__);app.secret_key='draft';query=Mock(return_value=[dict(cliente='Loja')])
        register_tasks(app,lambda f:f,lambda cid:True,lambda:contextlib.nullcontext(None),query,Mock(),lambda *a:a[-1],today=lambda:DAY)
        client=app.test_client();url='/anuncios/7/MLB1/tarefas?pergunta=123'
        with client.session_transaction() as state:state.update(tipo='admin',usuario_id=1,_csrf='token')
        self.assertEqual(client.post(url,data=form()).status_code,400);query.assert_not_called()
        with patch('listing_task_routes.question_draft',side_effect=AssertionError('POST source read')),patch('listing_task_routes.create',return_value=9) as create_task:
            response=client.post(url,data=dict(form(),_csrf='token',title='Escopo revisado por mim',description='Descrição revisada'))
        self.assertEqual(response.status_code,303);self.assertNotIn('pergunta=',response.headers['Location'])
        self.assertEqual(create_task.call_args.args[5]['title'],'Escopo revisado por mim')
        self.assertEqual(create_task.call_args.args[5]['description'],'Descrição revisada')
        with patch('listing_task_routes.question_draft',side_effect=AssertionError('POST source read')),patch('listing_task_routes.load',return_value=model()),patch('listing_task_routes.create') as create_task:
            response=client.post(url,data=dict(form(),_csrf='token',responsible='',description='Meu rascunho editado'))
        self.assertEqual(response.status_code,400);create_task.assert_not_called()
        self.assertIn('Meu rascunho editado',response.get_data(as_text=True))
