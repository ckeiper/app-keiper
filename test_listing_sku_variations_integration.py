import os
import json
import time
import unittest
from auth_test_support import database_session
from listing_sku_evidence import snapshot
from listing_sku_variations import load


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'), 'isolated PostgreSQL not configured')
class OfficialSkuIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['DATABASE_URL'] = os.environ['KEIPER_TEST_DATABASE_URL']
        import main
        cls.m = main
        if main.scheduler.running:
            main.scheduler.shutdown(wait=False)

    def test_distinct_listings_variations_scope_coverage_and_limits(self):
        m = self.m
        ids = []
        now = int(time.time())
        try:
            with m.banco() as conn:
                for name in ('Official SKU A', 'Official SKU B'):
                    ids.append(m.consultar(conn, "INSERT INTO conexoes(cliente,status) VALUES(%s,'ativa') RETURNING id", (name,))[0]['id'])
                for index in range(13):
                    attributes = [dict(id='SELLER_SKU', value_name=' ABC ')] if index==0 else []
                    variations = [dict(id=1, attributes=[dict(id='SELLER_SKU', value_name='ABC')]), dict(id=2, attributes=[dict(id='SELLER_SKU', value_name='ONE-LISTING' if index==0 else 'abc')])]
                    if index==0:
                        variations.append(dict(id=3, attributes=[dict(id='SELLER_SKU', value_name='ONE-LISTING')]))
                    item_id = 'MLB'+str(index+1)
                    data = snapshot(dict(id=item_id, seller_id=7, site_id='MLB', attributes=attributes, variations=variations), 7, item_id, now)
                    m.executar(conn, 'INSERT INTO anuncios(conexao_id,item_id,titulo,sku,sku_metadata_json) VALUES(%s,%s,%s,%s,%s::jsonb)', (ids[0], item_id, 'Produto', 'INTERNAL', json.dumps(data)))
                m.executar(conn, 'INSERT INTO anuncios(conexao_id,item_id,titulo,sku_metadata_json) VALUES(%s,%s,%s,%s::jsonb)', (ids[0], 'MLB99', 'malformed', json.dumps(dict(version=1,state='partial',entries={},collected_at=now))))
                m.executar(conn, 'INSERT INTO anuncios(conexao_id,item_id,titulo,sku_metadata_json) VALUES(%s,%s,%s,%s::jsonb)', (ids[1], 'MLB1', 'SEGREDO OUTRA LOJA', json.dumps(data)))
                result = load(conn, m.consultar, ids[0], {})
                self.assertEqual(result['total'], 2)
                group = next(g for g in result['groups'] if g['code']=='ABC')
                self.assertEqual(group['n'], 13)
                self.assertEqual(group['occurrences'], 14)
                self.assertEqual(len([r for r in result['members'] if r['code']=='ABC']), 10)
                self.assertEqual(result['stats']['read'], 13)
                self.assertEqual(result['stats']['partial'], 1)
                for code in ('ONE-LISTING', 'INTERNAL', "' OR 1=1 --"):
                    self.assertEqual(load(conn, m.consultar, ids[0], dict(sku=code))['total'], 0)
            client = m.app.test_client()
            with database_session(client) as session:
                session.update(usuario_id=1,tipo='admin')
            response = client.get('/anuncios/'+str(ids[0])+'/skus-variacoes?sku=ABC')
            self.assertEqual(response.status_code, 200)
            text = response.get_data(as_text=True)
            self.assertIn('13 anúncios', text)
            self.assertNotIn('SEGREDO OUTRA LOJA', text)
            self.assertIn('variação 1', text)
        finally:
            with m.banco() as conn:
                m.executar(conn, 'DELETE FROM anuncios WHERE conexao_id=ANY(%s)', (ids,))
                m.executar(conn, 'DELETE FROM conexoes WHERE id=ANY(%s)', (ids,))
