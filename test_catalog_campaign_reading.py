import unittest
from unittest.mock import patch
from listing_catalog import campaign_reading,filter_catalog,render_catalog
from test_listing_catalog import item,NOW
from test_catalog_price_order import snapshot
class CampaignReadingTests(unittest.TestCase):
 def test_valid_empty_response_is_not_a_claim_of_active_discount(self):
  r=dict(item(1),promocoes_json=dict(checked_at=NOW,promotions=[],error=None))
  self.assertEqual(campaign_reading(r,NOW),'valida')
  html=render_catalog(1,[r],{},now=NOW)
  self.assertIn('Campanhas: consulta válida',html)
  self.assertIn('não garante promoção ativa',html)
 def test_future_stale_boolean_or_missing_timestamp_is_pending(self):
  for stamp in [NOW+1,NOW-7201,True,None,float('nan'),float('inf'),10**1000]:
   self.assertEqual(campaign_reading(dict(promocoes_json=dict(checked_at=stamp,promotions=[])),NOW),'pendente')
  self.assertEqual(campaign_reading(dict(promocoes_json=dict(checked_at=NOW-7200,promotions=[])),NOW),'valida')
 def test_inapplicable_requires_compatible_status_and_recent_snapshot(self):
  r=dict(status='closed',promocoes_json=dict(checked_at=NOW,not_applicable='Anúncio encerrado'))
  self.assertEqual(campaign_reading(r,NOW),'inaplicavel')
  r['status']='active';self.assertEqual(campaign_reading(r,NOW),'pendente')
 def test_filter_combines_and_pagination_preserves_it(self):
  rows=[dict(item(i),promocoes_json=dict(checked_at=NOW,promotions=[],error='failure')) for i in range(25)]
  self.assertEqual(len(filter_catalog(rows,dict(status='active',campanhas='pendente'),NOW)),25)
  html=render_catalog(1,rows,dict(campanhas='pendente',por_pagina='10'),now=NOW)
  self.assertIn('campanhas=pendente',html)
 def test_winning_price_and_campaign_error_remain_separate(self):
  r=dict(item(1),promocoes_json=dict(snapshot(),error='campaign unavailable'))
  with patch('listing_details.time.time',return_value=NOW):
   html=render_catalog(1,[r],{},now=NOW)
   self.assertIn("catalog-price'>R$ 80,00",html)
   self.assertEqual(campaign_reading(r,NOW),'pendente')
