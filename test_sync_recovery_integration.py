import os
import time
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL URL not configured')
class RecoveryIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
        import main
        cls.m=main
        if main.scheduler.running: main.scheduler.shutdown(wait=False)
        main.iniciar_banco()
        main.app.config['TESTING']=True

    def setUp(self):
        m=self.m
        with m.banco() as conn:
            self.cid=m.consultar(conn,"INSERT INTO conexoes(cliente,status,user_id) VALUES('Recovery <shop>','ativa',99) RETURNING id")[0]['id']
        self.client=m.app.test_client()
        with self.client.session_transaction() as session:
            session['usuario_id']=1
            session['tipo']='admin'

    def tearDown(self):
        with self.m.banco() as conn:
            self.m.executar(conn,'DELETE FROM erros WHERE conexao_id=%s',(self.cid,))
            self.m.executar(conn,'DELETE FROM conexoes WHERE id=%s',(self.cid,))

    def test_resolved_error_is_preserved_and_new_error_reopens_it(self):
        m=self.m
        now=int(time.time())
        m.registrar_erro(self.cid,'atualizacao','tuple index out of range')
        with m.banco() as conn:
            m.executar(conn,'UPDATE erros SET quando=%s WHERE conexao_id=%s',(now-60,self.cid))
        m.resolver_erro(self.cid,'atualizacao',now)
        with m.banco() as conn:
            record=m.consultar(conn,'SELECT * FROM erros WHERE conexao_id=%s',(self.cid,))[0]
        self.assertIsNotNone(record['resolvido_em'])
        self.assertEqual(record['mensagem'],'tuple index out of range')
        diag=self.client.get('/diagnostico').get_data(as_text=True)
        self.assertIn('Recovery &lt;shop&gt;',diag)
        self.assertIn('Resolvido em',diag)
        self.assertIn('tuple index out of range',diag)
        m.registrar_erro(self.cid,'atualizacao','new failure')
        m.resolver_erro(self.cid,'atualizacao',now-10)
        with m.banco() as conn:
            self.assertIsNone(m.consultar(conn,'SELECT resolvido_em FROM erros WHERE conexao_id=%s',(self.cid,))[0]['resolvido_em'])

    def test_general_update_is_queued_and_client_cannot_queue_another_shop(self):
        with patch.object(self.m,'enfileirar_atualizacao',return_value=True) as queue, \
             patch.object(self.m,'executar_atualizacao',side_effect=AssertionError('synchronous collection')):
            response=self.client.get('/atualizar?cid='+str(self.cid))
            self.assertEqual(response.status_code,302)
            queue.assert_called_once_with(self.cid)
        with self.client.session_transaction() as session:
            session['tipo']='cliente'
            session['conexao_id']=self.cid+1000
        with patch.object(self.m,'enfileirar_atualizacao') as queue:
            self.client.get('/atualizar?cid='+str(self.cid))
            queue.assert_not_called()

    def test_partial_failure_does_not_clear_pending_stage_error(self):
        m=self.m
        m.registrar_erro(self.cid,'ads','no permission')
        m.registrar_erro(self.cid,'atualizacao','old global failure')
        with m.banco() as conn:
            m.executar(conn,'UPDATE erros SET quando=%s WHERE conexao_id=%s',(int(time.time())-60,self.cid))
        with patch.object(m,'token_atual',return_value='fake'), \
             patch.object(m,'puxar_conta',return_value=True), \
             patch.object(m,'puxar_anuncios',side_effect=IndexError('tuple index out of range')), \
             patch.object(m,'puxar_pedidos',return_value=True) as sales, \
             patch.object(m,'puxar_perguntas',return_value=True), \
             patch.object(m,'puxar_envios',return_value=True), \
             patch.object(m,'puxar_promocoes',return_value=True), \
             patch.object(m,'puxar_ads',return_value=False), \
             patch.object(m,'gravar_historico'):
            self.assertFalse(m.executar_atualizacao(self.cid))
            sales.assert_called_once()
        with m.banco() as conn:
            errors={r['categoria']:r for r in m.consultar(conn,'SELECT * FROM erros WHERE conexao_id=%s',(self.cid,))}
        self.assertIsNotNone(errors['atualizacao']['resolvido_em'])
        self.assertIsNone(errors['ads']['resolvido_em'])
        self.assertIsNone(errors['anuncios']['resolvido_em'])
        self.assertEqual(errors['anuncios']['mensagem'],'Falha na coleta: IndexError')
