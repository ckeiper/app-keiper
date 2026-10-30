import unittest
from unittest.mock import patch
from listing_details import render_promotions, normalize_promotions, active_promotions
from listing_catalog import render_catalog, campaign_reading
from test_listing_catalog import item, NOW
from test_catalog_price_order import snapshot


@patch('listing_details.time.time', return_value=NOW)
class PromotionRenderResilienceTests(unittest.TestCase):
    def test_invalid_dates_do_not_break_whole_catalog(self, _):
        for stamp in [None, 'bad', True, NOW+1, float('nan'), float('inf'), 10**1000]:
            with self.subTest(stamp_type=type(stamp)):
                row=dict(item(1), promocoes_json=dict(checked_at=stamp, promotions=[]))
                output=render_catalog(1,[row],{},now=NOW)
                self.assertIn('Campanhas: conferir consulta',output)
                self.assertIn('Dados desatualizados',output)

    def test_malformed_campaigns_are_pending_and_never_details(self, _):
        for records in [None, {}, [None], ['bad'], [{}], [dict(status='active',type=[])],
                        [dict(status='active',type='DEAL',price=[])],
                        [dict(status='active',type='DEAL',price=10**1000)],
                        [dict(status='active',type='DEAL',raw={'name':[]})]]:
            snap=dict(checked_at=NOW,promotions=records)
            self.assertEqual(campaign_reading(dict(promocoes_json=snap),NOW),'pendente')
            self.assertEqual(active_promotions(snap), [])
            output=render_catalog(1,[dict(item(1),promocoes_json=snap)],{},now=NOW)
            self.assertIn('Campanhas não confirmadas',output)
            self.assertNotIn('Ver detalhes</summary>',output)

    def test_valid_winner_survives_invalid_or_old_campaigns(self, _):
        for campaigns in [None, [{}]]:
            snap=dict(snapshot(),promotions=campaigns)
            output=render_promotions(snap)
            self.assertIn('Por R$ 80,00',output)
            self.assertNotIn('Outras campanhas',output)
        snap=dict(snapshot(),checked_at=NOW-7201,promotions=normalize_promotions([
            dict(type='DEAL',status='started',price=60,original_price=100)]))
        output=render_promotions(snap)
        self.assertIn('Por R$ 80,00',output)
        self.assertNotIn('Ver detalhes',output)

    def test_errors_escape_and_valid_campaigns_keep_existing_behavior(self, _):
        self.assertIn('&lt;script&gt;',render_promotions(dict(error='<script>')))
        self.assertIn('Não disponível',render_promotions(dict(error={'message':'bad'})))
        snap=dict(checked_at=NOW,promotions=normalize_promotions([
            dict(type='DEAL',status='started',price=80,original_price=100)]))
        self.assertIn('Preço informado pela campanha',render_promotions(snap))
