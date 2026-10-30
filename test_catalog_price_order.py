import unittest
from unittest.mock import patch
from listing_catalog import filter_catalog,displayed_price
from listing_details import effective_promotion,active_promotions
from test_listing_catalog import item,NOW

def snapshot(stamp=NOW):
 return dict(checked_at=stamp,promotions=[],sale_price=dict(checked_at=stamp,data=dict(currency_id='BRL',amount=80,regular_amount=200,metadata=dict(promotion_id='A'))))
class PriceOrderTests(unittest.TestCase):
 @patch('listing_details.time.time',return_value=NOW)
 def test_sorts_by_displayed_promotion_instead_of_base(self,_):
  rows=[dict(item(1),preco=200,promocoes_json=snapshot()),dict(item(2),preco=100)]
  self.assertEqual([r['item_id'] for r in filter_catalog(rows,dict(ordem='preco'),NOW)],['MLB2','MLB1'])
  self.assertEqual(displayed_price(rows[0]),80)
 @patch('listing_details.time.time',return_value=NOW)
 def test_stale_future_or_error_uses_same_catalog_fallback(self,_):
  for stamp in [NOW-7201,NOW+1,None,True,'bad',float('nan'),float('inf'),10**1000]:
   r=dict(item(1),preco=200,promocoes_json=snapshot(stamp))
   r['promocoes_json']['promotions']=[dict(status='active')]
   self.assertIsNone(effective_promotion(r['promocoes_json']))
   self.assertEqual(active_promotions(r['promocoes_json']),[])
   self.assertEqual(displayed_price(r),200)
 @patch('listing_details.time.time',return_value=NOW)
 def test_boundary_and_stable_ties_missing_last(self,_):
  self.assertIsNotNone(effective_promotion(snapshot(NOW-7200)))
  rows=[dict(item(3),preco=None),dict(item(2),preco=100),dict(item(1),preco=100)]
  self.assertEqual([r['item_id'] for r in filter_catalog(rows,dict(ordem='preco'),NOW)],['MLB1','MLB2','MLB3'])
 @patch('listing_details.time.time',return_value=NOW)
 def test_malformed_payload_not_confirmed(self,_):
  for value in [[],None,dict(sale_price='bad'),dict(sale_price=dict(checked_at=NOW,data='bad')),dict(sale_price=dict(checked_at=NOW,data=dict(metadata='bad')))]:
   self.assertIsNone(effective_promotion(value))
