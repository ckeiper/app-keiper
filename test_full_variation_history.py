import unittest
from copy import deepcopy
from datetime import timedelta
from html import unescape
from urllib.parse import urlsplit,parse_qs
from full_variation_history import build,render,MAX_READS
from test_full_report import observation,START,END,STAMP,ARGS,LISTING


def reading(stamp,quantity,inventory='A'):
    row=observation(stamp)
    row['evidence']['metadata']['inventories'][0]['inventory_id']=inventory
    row['evidence']['inventories'][0].update(inventory_id=inventory,quantity=quantity)
    row['quantity']=quantity+3 if type(quantity) is int and quantity>=0 else None
    row['evidence']['partial']=quantity is None
    return row


class FullVariationHistoryTests(unittest.TestCase):
    def test_exact_signed_differences_zero_and_immutable_sources(self):
        rows=[reading(STAMP-7200,2),reading(STAMP-3600,0),reading(STAMP,3)]
        original=deepcopy(rows);result=build(rows,'MLB1',START,END,'1')
        self.assertTrue(result['available']);self.assertEqual([r['quantity'] for r in result['rows']],[3,0,2])
        self.assertEqual([r['delta'] for r in result['rows']],[3,-2,None]);self.assertEqual(rows,original)
        text=render(1,dict(ARGS,full_variacao='1'),LISTING,rows,START,END)
        self.assertIn('+3 unidades',text);self.assertIn('-2 unidades',text)

    def test_invalid_middle_read_breaks_comparison_without_old_fallback(self):
        rows=[reading(STAMP-7200,2),reading(STAMP-3600,None),reading(STAMP,3)]
        result=build(rows,'MLB1',START,END,'1')['rows']
        self.assertIsNone(result[0]['delta']);self.assertIsNone(result[1]['quantity'])
        for invalid in (None,[],dict(metadata={})):
            rows[1]['evidence']=invalid
            self.assertIsNone(build(rows,'MLB1',START,END,'1')['rows'][0]['delta'])

    def test_missing_variation_and_duplicate_timestamp_are_explicit_gaps(self):
        rows=[reading(STAMP-7200,2),reading(STAMP-3600,1),reading(STAMP,3)]
        rows[1]['evidence']['metadata']['inventories']=rows[1]['evidence']['metadata']['inventories'][1:]
        result=build(rows,'MLB1',START,END,'1')['rows']
        self.assertIsNone(result[1]['quantity']);self.assertIsNone(result[0]['delta'])
        rows=[reading(STAMP-7200,2),reading(STAMP-3600,1),reading(STAMP-3600,1),reading(STAMP,3)]
        result=build(rows,'MLB1',START,END,'1')['rows']
        self.assertEqual(len(result),3);self.assertIsNone(result[1]['quantity']);self.assertIsNone(result[0]['delta'])

    def test_shared_inventory_changed_inventory_or_stale_mapping_does_not_bridge(self):
        old=reading(STAMP-3600,2)
        row=reading(STAMP,3,inventory='C')
        self.assertIsNone(build([old,row],'MLB1',START,END,'1')['rows'][0]['delta'])
        row=reading(STAMP,3);row['evidence']['metadata']['inventories'][1]['inventory_id']='A'
        self.assertIsNone(build([old,row],'MLB1',START,END,'1')['rows'][0]['quantity'])
        row=reading(STAMP,3);row['evidence']['metadata']['collected_at']=STAMP-10801
        self.assertIsNone(build([old,row],'MLB1',START,END,'1')['rows'][0]['quantity'])

    def test_six_hour_boundary_is_exact_and_long_gap_does_not_imply_movements(self):
        for gap,expected in [(21600,1),(21601,None)]:
            result=build([reading(STAMP-gap,2),reading(STAMP,3)],'MLB1',START,END,'1')
            self.assertEqual(result['rows'][0]['delta'],expected)
        text=render(1,ARGS,LISTING,[reading(STAMP,3)],START,END)
        self.assertIn('Não identifica entradas, saídas, reposição',text)

    def test_scope_selection_and_observation_budget_are_bounded(self):
        rows=[reading(STAMP-i*60,i) for i in range(MAX_READS+1)]
        foreign=reading(STAMP+30,999);foreign['item_id']='MLB2';rows.append(foreign)
        result=build(rows,'MLB1',START,END,'1')
        self.assertTrue(result['limited']);self.assertEqual(result['loaded'],MAX_READS)
        self.assertEqual(result['rows'][0]['quantity'],0);self.assertEqual(len(result['rows']),MAX_READS)
        self.assertFalse(build(rows,'MLB1',START,END,'999')['available'])
        self.assertFalse(build(rows,'MLB1',END+timedelta(days=1),END+timedelta(days=1),'1')['available'])
        self.assertIn('Recorte limitado',render(1,ARGS,LISTING,rows,START,END))

    def test_pagination_preserves_variation_and_other_pages_without_unknown_args(self):
        import re
        rows=[reading(STAMP-i*60,i) for i in range(41)]
        args=dict(ARGS,full_variacao='2',full_consultas='2',secret='ignored')
        text=render(1,args,LISTING,rows,START,END)
        self.assertEqual(text.count('<tr><th scope="row">'),20)
        href=unescape(re.search(r'href="([^"]+)">Próxima',text).group(1));params=parse_qs(urlsplit(href).query)
        self.assertEqual(params['full_variacao'],['2']);self.assertEqual(params['full_consultas'],['2'])
        self.assertEqual(params['full_historico_variacao'],['2']);self.assertNotIn('secret',params)
        self.assertIn('item_id=MLB1',render(1,{},LISTING,rows,START,END))
        text=render(1,dict(args,full_historico_variacao='999'),LISTING,rows,START,END)
        self.assertIn('Página 3 de 3',text);self.assertEqual(text.count('<tr><th scope="row">'),1)

    def test_escape_invalid_selection_missing_codes_and_reasons(self):
        row=reading(STAMP,3);row['evidence']['inventories'][0].update(quantity=None,reason='<script>')
        text=render(1,dict(ARGS,full_variacao='1'),LISTING,[row],START,END)
        self.assertIn('&lt;script&gt;',text);self.assertNotIn('<script>',text)
        text=render(1,dict(ARGS,full_variacao='" onfocus="bad'),LISTING,[row],START,END)
        self.assertIn('&quot;',text);self.assertNotIn('<table',text)
        self.assertIn('Sem código de variação',render(1,ARGS,LISTING,[],START,END))
