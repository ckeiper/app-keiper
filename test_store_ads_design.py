import unittest
from store_sidebar import render_store_sidebar, ITEMS
from scripts.ads_overview_preview import render_fixture


class StoreNavigationTests(unittest.TestCase):
    def test_every_store_destination_and_active_campaign_context(self):
        result=render_store_sidebar(7,'Loja <Teste>','ads',admin=True)
        self.assertIn('Loja &lt;Teste&gt;',result)
        for key,label,path,icon in ITEMS:
            self.assertIn("href='"+path+"7'",result)
        self.assertEqual(result.count("aria-current='page'"),1)
        self.assertIn("href='/ads/7' title='Publicidade' aria-current='page'",result)
        self.assertNotIn("href='/campanhas/7'",result)
        self.assertIn("href='/atualizar?cid=7'",result)
        self.assertIn("href='/excluir/7'",result)
        self.assertIn("href='/seguranca'",result)
        self.assertNotIn("href='/ads/8'",result)

    def test_client_has_no_admin_shortcuts(self):
        result=render_store_sidebar(7,'Cliente','resumo')
        self.assertNotIn("href='/seguranca'",result)
        self.assertNotIn("href='/diagnostico'",result)


class AdsOverviewDesignTests(unittest.TestCase):
    def test_indicators_precede_alerts_and_campaigns_remain_links(self):
        result=render_fixture()
        self.assertLess(result.index("<div class='ka-kpis'>"),result.index("<div class='ka-section-title'>"))
        self.assertIn('KIT &lt;5&gt;',result)
        self.assertNotIn('KIT <5>',result)
        self.assertIn("href='/ads/1/campanha/a'",result)
        self.assertIn("data-endpoint='/atualizacoes/1/ads'",result)
        self.assertEqual(result.count("class='k-refresh'"),1)
        self.assertIn('"16/10"',result)

    def test_empty_and_filtered_states_keep_real_controls(self):
        empty=render_fixture(empty=True)
        self.assertIn('Sem dados de publicidade',empty)
        self.assertNotIn("<div class='ka-kpis'>",empty)
        filtered=render_fixture(args='&campanha=inexistente')
        self.assertIn('Nenhuma campanha atende aos filtros',filtered)
        self.assertIn("value='inexistente'",filtered)

    def test_invalid_period_does_not_render_a_misleading_dashboard(self):
        result=render_fixture(args='&de=2026-10-23&ate=2026-10-22')
        self.assertEqual(result[1],400)
