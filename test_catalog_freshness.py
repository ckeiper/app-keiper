import unittest
from listing_catalog import freshness,filter_catalog,render_catalog
from test_listing_catalog import item,NOW
class ReadingTests(unittest.TestCase):
 def test_boundary_future_and_invalid_dates(self):
  for stamp,expected in [(NOW,'recente'),(NOW-21600,'recente'),(NOW-21601,'antiga'),(NOW+1,'desconhecida'),(None,'desconhecida'),(0,'desconhecida'),(True,'desconhecida'),('NaN','desconhecida'),('1.5','desconhecida')]:
   self.assertEqual(freshness(dict(atualizado_em=stamp),NOW),expected)
 def test_combines_stock_and_reading_without_mutating_data(self):
  rows=[dict(item(1),quantidade=0),dict(item(2),quantidade=0,atualizado_em=NOW-30000)]
  r=filter_catalog(rows,dict(estoque='zero',leitura='antiga'),NOW)
  self.assertEqual([x['item_id'] for x in r],['MLB2']);self.assertEqual(len(rows),2)
 def test_pagination_preserves_filter_and_badges_are_explicit(self):
  rows=[dict(item(i),atualizado_em=NOW-30000) for i in range(25)]
  html=render_catalog(1,rows,dict(leitura='antiga',por_pagina='10'),now=NOW)
  self.assertIn('leitura=antiga',html);self.assertEqual(html.count('Catálogo: leitura antiga'),10)
  self.assertIn('fontes e datas próprias',html)
 def test_unknown_filter_does_not_hide_rows(self):
  self.assertEqual(len(filter_catalog([item(1)],dict(leitura='bad'),NOW)),1)
