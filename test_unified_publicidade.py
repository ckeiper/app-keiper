import datetime
import html
import unittest
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs
from flask import Flask, request, redirect
from test_listing_details import main_function
from ads_campaign_detail import render
from scripts.ads_overview_preview import render_fixture


class UnifiedPublicidadeTests(unittest.TestCase):
    def legacy(self, query='', allowed=True):
        app=Flask('unified-ads-test')
        route=main_function('campanhas',dict(request=request,redirect=redirect,datetime=datetime,
            pode_ver_loja=lambda cid:allowed,pagina=lambda title,body:body))
        with app.test_request_context('/campanhas/7'+query),patch('sales_metrics.reporting_today',return_value=datetime.date(2026,10,22)):
            return route(7)

    def test_legacy_url_redirects_to_the_same_store(self):
        self.assertEqual(self.legacy().location,'/ads/7')
        response=self.legacy('?campanha=Kit&dias=7')
        self.assertEqual(parse_qs(urlparse(response.location).query),dict(campanha=['Kit'],dias=['7']))

    def test_legacy_no_sales_window_keeps_active_filter_and_dates(self):
        response=self.legacy('?sem_vendas=7')
        params=parse_qs(urlparse(response.location).query)
        self.assertEqual(params,dict(situacao=['ativas_sem_vendas'],de=['2026-10-15'],ate=['2026-10-22']))
        self.assertEqual(self.legacy(allowed=False)[1],403)

    def test_overview_has_one_entry_and_opens_individual_analysis(self):
        result=render_fixture()
        self.assertNotIn("href='/campanhas/",result)
        self.assertIn("href='/ads/1/campanha/a'",result)
        self.assertIn("href='#ka-campaign-list'",result)
        self.assertIn("id='ka-campaign-list'",result)

    def test_target_control_lives_on_the_individual_campaign(self):
        result=render(7,dict(campanha_id='A&B',nome='Kit',roas_objetivo=4),[],7,datetime.date(2026,10,22))
        self.assertIn("action='/salvar_roas/7/A%26B'",result)
        self.assertIn('Salvar meta',result)
        self.assertIn("href='/ads/7'",result)

    def test_active_no_sales_filter_is_available_in_overview(self):
        result=render_fixture(args='&situacao=ativas_sem_vendas')
        self.assertIn("value='ativas_sem_vendas' selected",result)
        self.assertIn('Nenhuma campanha atende aos filtros.',result)
