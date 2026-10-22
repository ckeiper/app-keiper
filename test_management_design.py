"""Verify navigation state, exact chart gaps and escaping without a browser."""
import unittest
from management_design import active_tab,panel,daily_chart,metric_card,product


class ManagementDesignTests(unittest.TestCase):
    def test_filter_navigation_keeps_the_relevant_panel_visible(self):
        self.assertEqual(active_tab({}),'overview')
        self.assertEqual(active_tab({'area':'estoque'}),'actions')
        self.assertEqual(active_tab({'visao':'queda'}),'analysis')
        self.assertEqual(active_tab({'aba':'analysis','area':'estoque'}),'analysis')
        self.assertEqual(active_tab({'aba':'invalid'}),'overview')
        self.assertNotIn(' hidden',panel('actions','actions'))
        self.assertIn(' hidden',panel('actions','overview'))

    def test_chart_does_not_connect_unknown_days_or_invent_zeroes(self):
        report={'current':{'daily':[100,None,200],'days':['2026-10-17','2026-10-18','2026-10-19']},
                'previous':{'daily':[None,None,None],'days':['2026-10-14','2026-10-15','2026-10-16']}}
        chart=daily_chart(report)
        self.assertEqual(chart.count("<path d='M"),2)
        self.assertIn('R$ 100,00',chart)
        self.assertIn('R$ 200,00',chart)
        self.assertIn('Indisponível',chart)
        self.assertNotIn('nan',chart.lower())
        report['current']['daily']=[None,None,None]
        self.assertNotIn('<svg',daily_chart(report))

    def test_card_escapes_content_and_preserves_no_data_state(self):
        card=metric_card('<script>','Indisponível','texto <b>')
        self.assertIn('&lt;script&gt;',card)
        self.assertIn('mgmt-stat-empty',card)
        self.assertNotIn('<script>',card)
        self.assertIn('R$ 0,00',metric_card('Faturamento de pedidos pagos','R$ 0,00','Valor confirmado'))


class ProductTests(unittest.TestCase):
    def test_only_trusted_https_images_are_rendered(self):
        for url in ('javascript:alert(1)','https://evil.test/x','https://mlstatic.com.evil.test/x','http://mlstatic.com/x','https://['):
            self.assertNotIn('<img',product({'listing':{'item_id':'MLB1','thumbnail':url}},1))
        html=product({'listing':{'item_id':'MLB1','titulo':'<script>','thumbnail':'https://http2.mlstatic.com/a.jpg'}},1)
        self.assertIn('<img',html)
        self.assertIn('&lt;script&gt;',html)
        self.assertIn('/diagnostico/1/MLB1',html)


class PriorityPlacementTests(unittest.TestCase):
    def test_current_store_home_loads_priority_queue_after_opportunities(self):
        import inspect
        from management_view import render_management
        from management_routes import register_management
        source=inspect.getsource(render_management)
        route=inspect.getsource(register_management)
        self.assertIn("@app.route('/painel/<int:cid>')",route)
        self.assertIn("body+=priorities(cid,report,args)",source)
        self.assertIn("id='mgmt-auto-priorities'",source)
        self.assertGreater(source.index("id='mgmt-auto-priorities'"),
                           source.index("body+=priorities(cid,report,args)"))
        self.assertIn("modo=prioridades",source)
        self.assertIn("fetch(url,{credentials:'same-origin'})",source)
        self.assertIn("if(!response.ok)throw",source)
        self.assertIn("ranking de anúncios",source)
