import contextlib
import datetime
import html
import unittest
from copy import deepcopy
from decimal import Decimal as D
from unittest.mock import Mock
from listing_comparison import selection,render

END=datetime.date(2026,10,23)
def sample():
    rows={}
    listings=[]
    for i in range(1,5):
        key='MLB'+str(i);listings.append(dict(item_id=key,titulo='Produto '+str(i)))
        rows[key]=dict(orders=i,previous_orders=2*i,units=3*i,previous_units=4*i,value=D(100*i),previous_value=D(200*i))
    return dict(available=True,rows=rows),listings

class ListingComparisonTests(unittest.TestCase):
 def test_two_to_four_distinct_same_store_items_and_order(self):
    r,l=sample();args=dict(comparar1='mlb3',comparar2='MLB1',comparar3='MLB3',comparar4='MLB4')
    before=deepcopy([r,l,args]);s=selection(r,l,args)
    self.assertTrue(s['available']);self.assertEqual(s['ids'],['MLB3','MLB1','MLB4'])
    self.assertEqual([r,l,args],before)
    self.assertFalse(selection(r,l,dict(comparar1='MLB1'))['available'])
 def test_unknown_foreign_invalid_and_incomplete_never_become_zero(self):
    r,l=sample()
    for bad in ['MLB999','<script>','MLB1 OR 1=1','MLB'+'9'*21]:
        self.assertFalse(selection(r,l,dict(comparar1='MLB1',comparar2=bad))['available'])
    r['available']=False
    text=render(42,r,l,dict(comparar1='MLB1',comparar2='MLB2'),END)
    self.assertNotIn('<table',text);self.assertIn('Dados incompletos não são zero',text)
 def test_exact_same_windows_and_verified_zero_without_false_percentage(self):
    r,l=sample();r['rows']['MLB2'].update(previous_value=D(0),previous_orders=0,value=D(0),orders=0)
    text=render(42,r,l,dict(comparar1='MLB1',comparar2='MLB2'),END)
    self.assertIn('10/10/2026 a 16/10/2026',text);self.assertIn('17/10/2026 a 23/10/2026',text)
    self.assertIn('R$ 200,00 → R$ 100,00',text)
    self.assertIn('R$ 0,00 → R$ 0,00',text);self.assertIn('Sem base percentual anterior',text)
    self.assertIn('Sem pedidos → Sem pedidos',text)
    self.assertIn('não some os pedidos',text)
 def test_untrusted_content_escaped_and_suggestions_bounded(self):
    r,l=sample();l[0]['titulo']='<script>'
    l += [dict(item_id='MLB'+str(i),titulo='Outro '+str(i)) for i in range(10,220)]
    text=render(42,r,l,dict(comparar1='MLB1',comparar2='MLB2'),END)
    self.assertIn('&lt;script&gt;',text);self.assertNotIn('<script>',text)
    self.assertEqual(text.count('<option value="MLB'),200)
    self.assertIn('Sugestões limitadas',text)
 def test_thirty_day_windows_and_selection_are_retained(self):
    r,l=sample();text=render(42,r,l,dict(comparar1='MLB1',comparar2='MLB2'),END,days=30)
    self.assertIn('value="30" selected',text);self.assertIn('value="MLB1"',text)
    self.assertIn('25/08/2026 a 23/09/2026',text)
    self.assertIn('24/09/2026 a 23/10/2026',text)
 def test_ranking_route_includes_comparison_without_adding_reads(self):
    from flask import Flask,request,session
    from test_listing_details import main_function
    app=Flask(__name__);app.secret_key='test'
    r,l=sample();r.update(available=False,reason='Pendente',rows={})
    query=Mock(side_effect=[[dict(cliente='Loja')],l,[],[],[],[dict(n=True)]])
    fn=main_function('ranking_anuncios',dict(pode_ver_loja=lambda cid:cid==42,pagina=lambda *a:a[-1],
        pagina_loja=lambda *a:a[-1],request=request,session=session,datetime=datetime,
        ranking_query_bounds=lambda *a,**kw:('a','b','c','d'),banco=lambda:contextlib.nullcontext(None),
        executar=Mock(),consultar=query,ranking_metrics=lambda *a,**kw:r,esc=html.escape))
    with app.test_request_context('/ranking-anuncios/42?comparar1=MLB1&comparar2=MLB2'):
        body=fn(42)
    self.assertIn('Comparar anúncios lado a lado',body);self.assertNotIn('<table',body)
    self.assertEqual(query.call_count,6)
