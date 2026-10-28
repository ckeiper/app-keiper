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


class CampaignConfigurationTests(unittest.TestCase):
    def test_official_roas_equivalence_and_budget_format(self):
        from ads_overview_design import campaign_configuration
        self.assertEqual(campaign_configuration(dict(orcamento=1234.5, roas_objetivo=4)), ('R$ 1.234,50', '25,00%'))
        self.assertEqual(campaign_configuration(dict(orcamento=0, roas_objetivo=6)), ('R$ 0,00', '16,67%'))

    def test_missing_invalid_and_nonfinite_are_not_zero(self):
        from ads_overview_design import campaign_configuration
        for value in (None, '', 'bad', -1, float('nan'), float('inf'), True):
            with self.subTest(value=value):
                self.assertEqual(campaign_configuration(dict(orcamento=value, roas_objetivo=value)), ('Não informado', 'Não informado'))
        self.assertEqual(campaign_configuration(dict(roas_objetivo=0))[1], 'Não informado')

    def test_route_shows_current_config_even_with_old_daily_spend(self):
        result=render_fixture(campaign_updates={'a':dict(hoje_atualizado=1)})
        self.assertIn("<td data-label='Orçamento diário'>R$ 100,00</td>",result)
        self.assertIn("<td data-label='ACOS objetivo'>25,00%</td>",result)
        self.assertIn("<td data-label='ACOS objetivo'>16,67%</td>",result)
        self.assertIn('Consumo de hoje indisponível',result)
        missing=render_fixture(campaign_updates={'a':dict(orcamento=None,roas_objetivo=None)})
        self.assertIn("<td data-label='Orçamento diário'>Não informado</td>",missing)
        self.assertIn("<td data-label='ACOS objetivo'>Não informado</td>",missing)
