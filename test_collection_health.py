"""Collection-health triage never treats missing data as zero."""
import unittest
from datetime import date
from collection_health import assess, render, summary


class CollectionHealthTests(unittest.TestCase):
    def test_detects_stale_ads_sales_and_catalogue(self):
        now=2000000
        shops=[{'id':1,'cliente':'Loja A','status':'ativa'}]
        catalog=[{'conexao_id':1,'latest':now-90000}]
        ads=[{'conexao_id':1,'first_day':'2026-10-01','last_day':'2026-10-17','days_7':5}]
        sales=[{'conexao_id':1,'latest_day':'2026-10-18'}]
        runs=[{'conexao_id':1,'status':'falhou','inicio_em':now-4000,'heartbeat_em':None}]
        errors=[{'conexao_id':1,'categoria':'ads'}]
        rows=assess(shops,catalog,ads,sales,runs,errors,today=date(2026,10,22),now=now)
        self.assertEqual(rows[0]['state'],'atencao')
        self.assertEqual(len(rows[0]['issues']),5)
        self.assertIn('5/7',str(rows[0]['issues']))
        self.assertIn('falha',str(rows[0]['issues']))
        self.assertIn('Loja A',render(rows,compact=True))

    def test_store_without_ads_history_not_marked_as_ads_failure(self):
        shops=[{'id':2,'cliente':'Loja B','status':'ativa'}]
        rows=assess(shops,[{'conexao_id':2,'latest':1000}],[],
                    [{'conexao_id':2,'latest_day':'2026-10-21'}],[],[],
                    today=date(2026,10,22),now=1100)
        self.assertEqual(rows[0]['state'],'normal')
        self.assertEqual(summary(rows)['attention'],0)

    def test_inactive_store_is_not_an_active_sync_failure(self):
        rows=assess([{'id':4,'cliente':'Pausada','status':'inativa'}],[],[],[],[],[],
                    today=date(2026,10,22),now=10000)
        self.assertEqual(rows[0]['state'],'inativa')

    def test_running_sync_with_fresh_heartbeat_is_not_stuck(self):
        rows=assess([{'id':1,'cliente':'OK','status':'ativa'}],
                    [{'conexao_id':1,'latest':9999}],[],
                    [{'conexao_id':1,'latest_day':'2026-10-21'}],
                    [{'conexao_id':1,'status':'executando','inicio_em':1,'heartbeat_em':9990}],[],
                    today=date(2026,10,22),now=10000)
        self.assertEqual(rows[0]['state'],'normal')

    def test_user_content_escaped(self):
        rows=[dict(id=1,name='<script>alert(1)</script>',state='atencao',
                   issues=['bad <script>'],action='Investigar')]
        output=render(rows)
        self.assertIn('&lt;script&gt;',output)
        self.assertNotIn('<script>',output)


if __name__=='__main__':
    unittest.main()
