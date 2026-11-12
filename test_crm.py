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
    def test_gemini_notes_without_key_fill_explicit_facts_not_consultant_dialogue(self):
        text = ('nov. 4, 2026\nReunião Lead Exemplo\n'
                'convidado clinton@keiperconsultoria.com.br lead@example.com\n'
                'Registros da reunião Transcrição\n\nResumo\n'
                'Dificuldades operacionais\nEstoque indisponível no canal.\n\n'
                'Objetivos\nAmpliar o catálogo.\n\nPróximas etapas\n'
                '* [Lead Exemplo] Analisar proposta com sócio.\n\nDetalhes\n'
                'Equipe e logística: Dois funcionários na expedição.\n\n'
                'Reunião Lead Exemplo - Transcrição\n00:00:01\n'
                'Clinton: Nome: Consultor\nEmpresa: Não extrair do diálogo\n')
        with patch('crm.requests.post') as post:
            data, summary, warning, _ = crm.extract(text)
        post.assert_not_called()
        self.assertEqual(data['nome'], 'Lead Exemplo')
        self.assertEqual(data['email'], 'lead@example.com')
        self.assertEqual(data['empresa'], '')
        self.assertEqual(data['data_reuniao'], '2026-11-04')
        self.assertIn('Estoque indisponível', data['dificuldades'])
        self.assertIn('Ampliar', data['objetivos'])
        self.assertIn('Dois funcionários', data['estrutura'])
        self.assertIn('sócio', data['proxima_acao'])
        self.assertEqual(data['data_followup'], '')
        self.assertIn('Dificuldades', summary)
        self.assertIn('não foi interpretada', warning)

    def test_gemini_does_not_guess_client_email_from_multiple_guests(self):
        data = crm.basic_extract('Reunião Exemplo\nconvidado a@example.com b@example.com\nResumo\nTexto')
        self.assertEqual(data['email'], '')

    def test_gemini_automatic_meet_title_is_not_a_client_name(self):
        data, summary, _, _ = crm.extract('nov. 4, 2026\n'
            'Reunião em 4 de nov. de 2026 às 15:31 GMT-03:00\n'
            'Resumo\nDiagnóstico\nAnálise de vendas.\n\nPróximas etapas\n'
            '[Cliente] Enviar métricas de conversão.')
        self.assertEqual(data['nome'], '')
        self.assertEqual(data['data_reuniao'], '2026-11-04')
        self.assertIn('Enviar métricas', data['proxima_acao'])
        self.assertIn('Análise de vendas', summary)

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
        self.assertEqual(crm.contact_phone('+55 (19) 99999-1234'),'19999991234')
        self.assertEqual(crm.contact_phone('(19) 3333-1234'),'1933331234')
        self.assertEqual(crm.whatsapp('+55 (19) 99999-1234'),'https://wa.me/5519999991234')


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

    def test_meet_ingests_once_without_browser_session_and_preserves_sales_stage(self):
        from crm_meet import TOKEN_KEY
        from web_security import install_security
        import hashlib
        lead_id=self.create(email='crm-meet@example.com',etapa='Em negociação',
                            data_followup='2026-11-18',proxima_acao='Retomar')
        token='A'*43
        doc='documento_teste_meet_12345678'
        data={'document_id':doc,'title':'Reuniao CRM - 2026/11/11 15:32 GMT-03:00 - Anotações do Gemini',
              'text':'11 nov 2026\nReuniao CRM\nconvidado crm-meet@example.com\nTranscrição original preservada.'}
        url='/crm/integracao/meet'
        # Use a separate app to verify the full middleware plus the production handler.
        app=Flask('meet_test');app.secret_key='isolated-meet-test-key'
        install_security(app)
        crm.register_crm(app,self.bank,self.query,self.execute,lambda title,body:body)
        client=app.test_client()
        self.assertEqual(client.post(url,json=data).status_code,401)
        with self.bank() as conn:
            self.execute(conn,'INSERT INTO crm_config(chave,valor) VALUES(%s,%s)',
                         (TOKEN_KEY,hashlib.sha256(token.encode()).hexdigest()))
        try:
            headers={'Authorization':'Bearer '+token}
            bad=dict(data,title=data['title'].replace('Reuniao','Consultoria'))
            self.assertEqual(client.post(url,json=bad,headers=headers).status_code,422)
            bad=dict(data,text=data['text'].replace('crm-meet@example.com','outro@example.com'))
            self.assertEqual(client.post(url,json=bad,headers=headers).status_code,409)
            self.assertEqual(client.post(url,json=data,headers=headers).json['status'],'imported')
            self.assertEqual(client.post(url,json=data,headers=headers).json['status'],'already_imported')
            lead=self.get_lead(lead_id)
            self.assertEqual(lead['etapa'],'Em negociação')
            self.assertEqual(lead['dados']['data_followup'],'2026-11-18')
            self.assertEqual(lead['dados']['data_reuniao'],'2026-11-11')
            with self.bank() as conn:
                rows=self.query(conn,"SELECT transcricao,texto FROM crm_historico WHERE lead_id=%s AND tipo='Reunião importada'",(lead_id,))
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['transcricao'],data['text'])
            self.assertIn(doc,rows[0]['texto'])
        finally:
            with self.bank() as conn:
                self.execute(conn,'DELETE FROM crm_meet_imports WHERE document_id=%s',(doc,))
                self.execute(conn,'DELETE FROM crm_config WHERE chave=%s',(TOKEN_KEY,))

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

    def test_reprocess_saved_source_requires_review_and_preserves_single_meeting(self):
        lead_id = self.create(email='saved@example.com', etapa='Em negociação')
        with self.bank() as conn:
            item_id = self.query(conn, """INSERT INTO crm_historico
                (lead_id,tipo,texto,transcricao,data_reuniao)
                VALUES(%s,'Reunião importada','',%s,'2026-11-04') RETURNING id""",
                (lead_id, 'Nome: Lead teste\nObjetivo: Ampliar catálogo'))[0]['id']
        path = f'/crm/{lead_id}/historico/{item_id}/reprocessar'
        self.assertEqual(self.client.post(path).status_code, 400)
        self.assertEqual(self.post(f'/crm/{lead_id}/historico/0/reprocessar').status_code, 404)
        with patch('crm.extract', wraps=crm.extract):
            response = self.post(path)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.get_lead(lead_id)['versao'], 1)
        view = self.client.get(response.location).text
        self.assertIn('Ampliar catálogo', view)
        self.assertIn('saved@example.com', view)
        result = self.post(response.location, nome='Lead teste', email='saved@example.com',
                           etapa='Em negociação', objetivos='Ampliar catálogo', resumo='Revisado')
        self.assertEqual(result.status_code, 302)
        with self.bank() as conn:
            rows = self.query(conn, 'SELECT * FROM crm_historico WHERE lead_id=%s', (lead_id,))
        self.assertEqual(sum(bool(r['transcricao']) for r in rows), 1)
        self.assertTrue(any(r['tipo'] == 'Transcrição reprocessada' for r in rows))
        self.assertEqual(self.get_lead(lead_id)['etapa'], 'Em negociação')

    def test_link_matching_phone_preserves_draft_edits_and_requires_review(self):
        lead_id=self.create(celular='+55 (19) 98888-7766',empresa='Empresa preservada',etapa='Em negociação')
        r=self.post('/crm/importar',texto='WhatsApp: (19) 98888-7766\nObjetivo: Crescer na Shopee')
        review=r.location
        self.assertIn('Usar este cadastro',self.client.get(review).text)
        r=self.post(review+'/vincular',lead_id=str(lead_id),celular='(19) 98888-7766',
                    objetivos='Objetivo revisado',resumo='Síntese editada')
        self.assertEqual(r.status_code,302)
        self.assertEqual(self.get_lead(lead_id)['versao'],1)
        view=self.client.get(review).text
        self.assertIn('Empresa preservada',view)
        self.assertIn('Objetivo revisado',view)
        self.assertIn('Síntese editada',view)
        self.assertIn('selected>Em negociação',view)
        self.assertEqual(self.post(review+'/vincular',lead_id=str(lead_id)).status_code,409)
        r=self.post(review,nome='Lead existente',empresa='Empresa preservada',
                    objetivos='Objetivo revisado',resumo='Síntese editada',etapa='Em negociação')
        self.assertEqual(r.location,f'/crm/{lead_id}')
        self.assertEqual(self.get_lead(lead_id)['versao'],2)
        with self.bank() as conn:
            rows=self.query(conn,"SELECT * FROM crm_historico WHERE lead_id=%s AND tipo='Reunião importada'",(lead_id,))
        self.assertEqual(len(rows),1)
        self.assertIn('WhatsApp: (19)',rows[0]['transcricao'])

    def test_link_draft_rejects_invalid_owner_and_missing_csrf(self):
        lead_id=self.create(email='link@example.com')
        review=self.post('/crm/importar',texto='E-mail: link@example.com').location
        self.assertEqual(self.client.post(review+'/vincular',data={'lead_id':lead_id}).status_code,400)
        self.assertEqual(self.post(review+'/vincular',lead_id='invalid').status_code,400)
        other=self.app.test_client()
        with other.session_transaction() as s:
            s.update(usuario_id=-98766,tipo='admin',crm_csrf='other-csrf')
        self.assertEqual(other.post(review+'/vincular',data={'lead_id':lead_id,'csrf_token':'other-csrf'}).status_code,404)

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
