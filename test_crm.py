import datetime as dt
import io
import json
import os
import unittest
from unittest.mock import Mock, patch
from flask import Flask
from werkzeug.datastructures import FileStorage
import crm


class CRMUnitTests(unittest.TestCase):
    def test_only_explicit_fields_and_valid_dates(self):
        text = ('Clinton: Olá João, meu telefone é (19) 99999-1234.\n'
                'Nome do lead: João Silva\nEmpresa: Loja A\nE-mail: joao@example.com\n'
                'WhatsApp: (19) 98888-7777\nFaturamento: R$ 50 mil\n'
                'Data da reunião: 18/10/2026\nFollow-up: quinta\n'
                'Dificuldades: poucos pedidos na Shopee\nObjetivo: vender mais')
        data = crm.basic_extract(text)
        self.assertEqual(data['nome'], 'João Silva')
        self.assertEqual(data['celular'], '(19) 98888-7777')
        self.assertEqual(data['data_reuniao'], '2026-10-18')
        self.assertEqual(data['data_followup'], '')
        self.assertEqual(data['marketplaces'], 'Shopee')
        self.assertEqual(crm.basic_extract('Clinton: meu email é consultor@example.com')['email'],'')

    def test_no_key_uses_honest_basic_mode(self):
        with patch('crm.requests.post') as post:
            data, summary, warning, suggestion = crm.extract('Nome: João')
        post.assert_not_called()
        self.assertEqual(data['nome'],'João')
        self.assertIn('básico',warning)
        self.assertEqual(summary,'')
        self.assertEqual(suggestion,'')

    def test_ai_schema_and_failure_preserve_basic_fields(self):
        result = {k:'' for k in crm.FIELDS}
        result.update(nome='João', resumo='Loja em expansão.', sugestao='Sugerir contato em 3 dias.', data_followup='amanhã')
        response=Mock()
        response.json.return_value={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result)}}]}
        with patch('crm.requests.post',return_value=response) as post:
            data, summary, warning, suggestion=crm.extract('Nome: João','sk-test')
        self.assertEqual(data['data_followup'],'')
        self.assertEqual(summary,'Loja em expansão.')
        self.assertIn('3 dias',suggestion)
        self.assertFalse(post.call_args.kwargs['json']['store'])
        self.assertTrue(post.call_args.kwargs['json']['response_format']['json_schema']['strict'])
        self.assertEqual(post.call_args.kwargs['timeout'],(4,20))
        response.json.return_value={'choices':[{'finish_reason':'length','message':{'content':'{}'}}]}
        with patch('crm.requests.post',return_value=response):
            data,_,warning,_=crm.extract('Nome: Ana','sk-test')
        self.assertEqual(data['nome'],'Ana')
        self.assertIn('não respondeu',warning)

    def test_upload_limits_and_validation(self):
        self.assertEqual(crm.read_transcript(FileStorage(io.BytesIO(b'Nome: Joao'),filename='a.txt')),'Nome: Joao')
        for content,filename in [(b'x','a.exe'),(b'x'*(crm.MAX_BYTES+1),'a.txt'),(b'\x00','a.txt')]:
            with self.assertRaises(ValueError):
                crm.read_transcript(FileStorage(io.BytesIO(content),filename=filename))
        with self.assertRaises(ValueError): crm.read_transcript(None,'x'*(crm.MAX_TEXT+1))
        for data in ({}, {'nome':'Ana','email':'ruim'}, {'nome':'Ana','data_followup':'2026-02-30'}, {'nome':'Ana','etapa':'invalido'}):
            with self.assertRaises(ValueError): crm.validate(data)
        self.assertEqual(crm.whatsapp('(19) 99999-1234'),'https://wa.me/5519999991234')


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'), 'isolated PostgreSQL URL not configured')
class CRMIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg2
        from psycopg2.extras import RealDictCursor
        cls.bank=staticmethod(lambda:psycopg2.connect(os.environ['KEIPER_TEST_DATABASE_URL']))
        def query(conn,sql,params=()):
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql,params or ()); return cur.fetchall()
        def execute(conn,sql,params=()):
            cur=conn.cursor();cur.execute(sql,params or ());return cur
        cls.query=staticmethod(query);cls.execute=staticmethod(execute)
        with cls.bank() as conn: crm.init_crm_schema(conn,execute)
        cls.app=Flask('crm_tests');cls.app.secret_key='isolated-crm-test-secret'
        cls.app.config['TESTING']=True
        crm.register_crm(cls.app,cls.bank,query,execute,lambda title,body:body)

    def setUp(self):
        self.client=self.app.test_client()
        with self.client.session_transaction() as s:
            s['usuario_id']=-98765;s['tipo']='admin';s['crm_csrf']='test-csrf'
        self.ids=[]

    def tearDown(self):
        with self.bank() as conn:
            self.execute(conn,'DELETE FROM crm_rascunhos WHERE usuario_id=-98765')
            for lead_id in self.ids:
                self.execute(conn,'DELETE FROM crm_historico WHERE lead_id=%s',(lead_id,))
                self.execute(conn,'DELETE FROM crm_leads WHERE id=%s',(lead_id,))

    def post(self,path,**data):
        return self.client.post(path,data=dict(csrf_token='test-csrf',**data))

    def create(self,**data):
        response=self.post('/crm/novo',nome='CRM Test <script>alert(1)</script>',**data)
        self.assertEqual(response.status_code,302)
        lead_id=int(response.location.rsplit('/',1)[-1]);self.ids.append(lead_id)
        return lead_id

    def get_lead(self,lead_id):
        with self.bank() as conn:
            return self.query(conn,'SELECT * FROM crm_leads WHERE id=%s',(lead_id,))[0]

    def test_access_control_csrf_and_escaping(self):
        anon=self.app.test_client()
        for url in ['/crm','/crm/resumo','/crm/novo','/crm/importar','/crm/configuracao','/crm/revisar/nope']:
            self.assertEqual(anon.get(url).status_code,302)
        with anon.session_transaction() as s: s['usuario_id']=99;s['tipo']='cliente'
        for url in ['/crm','/crm/resumo','/crm/novo','/crm/importar','/crm/configuracao']:
            self.assertEqual(anon.get(url).status_code,403)
        self.assertEqual(self.client.post('/crm/novo',data={'nome':'No csrf'}).status_code,400)
        self.assertEqual(self.client.post('/crm/novo',data={'csrf_token':'ç'}).status_code,400)
        lead_id=self.create(email='crm-test@example.com')
        view=self.client.get('/crm/'+str(lead_id)).text
        self.assertIn('&lt;script&gt;',view);self.assertNotIn('<script>alert(1)</script>',view)
        self.assertEqual(self.client.get('/crm').headers['Cache-Control'],'no-store')

    def test_contact_updates_followup_and_optimistic_lock(self):
        lead_id=self.create(data_followup='2020-01-01',proxima_acao='Retomar')
        r=self.post(f'/crm/{lead_id}/contato',versao='1',resultado='Respondeu',proxima_acao='Enviar proposta',data_followup='2026-12-10')
        self.assertEqual(r.status_code,302)
        self.assertEqual(str(self.get_lead(lead_id)['data_followup']),'2026-12-10')
        r=self.post(f'/crm/{lead_id}/contato',versao='1',resultado='Duplicado')
        self.assertEqual(r.status_code,400)
        self.assertEqual(str(self.get_lead(lead_id)['data_followup']),'2026-12-10')
        self.post(f'/crm/{lead_id}/contato',versao='2',resultado='Concluído')
        self.assertIsNone(self.get_lead(lead_id)['data_followup'])
        with self.bank() as conn:
            self.assertEqual(self.query(conn,"SELECT COUNT(*) n FROM crm_historico WHERE lead_id=%s AND tipo='Contato realizado'",(lead_id,))[0]['n'],2)

    def test_draft_review_preserves_original_and_does_not_duplicate(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':''}):
            r=self.post('/crm/importar',texto='Nome: Lead importado\nEmpresa: Teste\nE-mail: import@example.com',data_reuniao='2026-10-18')
        self.assertEqual(r.status_code,302)
        review=r.location
        self.assertIn('Lead importado',self.client.get(review).text)
        with self.bank() as conn:
            self.assertEqual(self.query(conn,"SELECT COUNT(*) n FROM crm_leads WHERE nome='Lead importado'")[0]['n'],0)
        r=self.post(review,nome='Lead importado',email='import@example.com',resumo='Síntese revisada',data_reuniao='2026-10-18')
        self.assertEqual(r.status_code,302)
        lead_id=int(r.location.rsplit('/',1)[-1]);self.ids.append(lead_id)
        self.assertEqual(self.post(review,nome='Duplicado').status_code,404)
        with self.bank() as conn:
            row=self.query(conn,'SELECT * FROM crm_historico WHERE lead_id=%s',(lead_id,))[0]
        self.assertIn('Nome: Lead importado',row['transcricao'])
        self.assertEqual(row['texto'],'Síntese revisada')
        self.assertEqual(str(row['data_reuniao']),'2026-10-18')

    def test_new_meeting_preserves_existing_fields_and_conflicts(self):
        lead_id=self.create(email='existing@example.com',empresa='Loja antiga')
        r=self.post(f'/crm/importar?lead={lead_id}',texto='Objetivo: Expandir para Shopee')
        review=r.location
        view=self.client.get(review).text
        self.assertIn('existing@example.com',view);self.assertIn('Loja antiga',view)
        self.post(f'/crm/{lead_id}',nome='Alterado',empresa='Loja atual',versao='1')
        r=self.post(review,nome='Antigo',versao='1')
        self.assertIn('cadastro mudou',r.text)
        self.assertEqual(self.get_lead(lead_id)['nome'],'Alterado')

    def test_filters_summary_closed_and_missing_dates(self):
        a=self.create(data_followup='2020-01-01',empresa='Filtro exclusivo')
        b=self.create(data_followup='2020-01-01',etapa='Perdido')
        c=self.create(data_followup=crm.today().isoformat())
        view=self.client.get('/crm/resumo').text
        self.assertIn(f'/crm/{a}',view);self.assertIn(f'/crm/{c}',view)
        self.assertNotIn(f'/crm/{b}\"',view)
        view=self.client.get('/crm?q=Filtro+exclusivo').text
        self.assertIn('Filtro exclusivo',view)
        self.assertNotIn(f'/crm/{b}\"',view)
        self.assertEqual(self.client.get('/crm/999999999').status_code,404)

    def test_settings_encrypt_and_do_not_expose_key(self):
        token='sk-very-secret-test-key'
        response=self.post('/crm/configuracao',api_key=token)
        self.assertNotIn(token,response.text)
        with self.bank() as conn:
            row=self.query(conn,"SELECT valor FROM crm_config WHERE chave='openai_key'")[0]
        self.assertNotIn(token,row['valor'])
        self.post('/crm/configuracao',remove='1')
