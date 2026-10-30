import unittest
from copy import deepcopy
from datetime import date, datetime, timedelta
from html import unescape
from urllib.parse import urlsplit,parse_qs
from full_report_components import snapshot,paginate,render_snapshot,render_summary
from full_view import render_full
from sales_metrics import SAO_PAULO

START=date(2026,9,1);END=date(2026,9,30)
STAMP=int(datetime(2026,9,30,12,tzinfo=SAO_PAULO).timestamp())
ARGS=dict(item_id='MLB1',periodo='personalizado',inicio=START.isoformat(),fim=END.isoformat())
LISTING=dict(item_id='MLB1',titulo='Produto demonstrativo')

def observation(stamp=STAMP):
    return dict(item_id='MLB1',observed_at=stamp,state='available',quantity=3,logistics='fulfillment',
                evidence=dict(metadata=dict(collected_at=stamp,logistics='fulfillment',missing=False,
                    inventories=[dict(inventory_id='A',variation_id=1),dict(inventory_id='B',variation_id=2)]),
                    partial=False,inventories=[dict(inventory_id='A',quantity=0,reason=None),dict(inventory_id='B',quantity=3,reason=None)]))

class FullReportTests(unittest.TestCase):
    def test_official_zero_positive_and_immutability(self):
        rows=[observation()];original=deepcopy(rows)
        result=snapshot(rows,'MLB1',START,END)
        self.assertEqual([r['quantity'] for r in result['rows']],[0,3])
        self.assertEqual(rows,original);self.assertFalse(result['partial'])

    def test_shared_inventory_or_duplicate_variation_never_allocates_stock(self):
        for mode in ('inventory','variation'):
            row=observation();mapping=row['evidence']['metadata']['inventories']
            if mode=='inventory':mapping[1]['inventory_id']='A'
            else:mapping[1]['variation_id']=1
            result=snapshot([row],'MLB1',START,END)
            self.assertEqual([r['quantity'] for r in result['rows']],[None,None])
            self.assertTrue(all('compartilhado ou duplicado' in r['reason'] for r in result['rows']))

    def test_stale_future_non_full_and_duplicate_latest_never_fall_back(self):
        old=observation(STAMP-60)
        for changes in [dict(collected_at=STAMP-10801),dict(collected_at=STAMP+1),dict(collected_at=True),dict(logistics='other')]:
            row=observation();row['evidence']['metadata'].update(changes)
            self.assertEqual(snapshot([old,row],'MLB1',START,END)['rows'],[])
        row=observation();row['evidence']['metadata']['collected_at']=STAMP-10800
        self.assertEqual(len(snapshot([row],'MLB1',START,END)['rows']),2)
        self.assertEqual(snapshot([old,observation(),observation()],'MLB1',START,END)['rows'],[])
        row=observation();row['evidence']=None
        self.assertEqual(snapshot([old,row],'MLB1',START,END)['rows'],[])

    def test_failed_missing_invalid_or_duplicated_read_is_unknown_not_zero(self):
        for value in (True,-1,1.5,None,'3'):
            row=observation();row['evidence']['inventories'][1]['quantity']=value
            self.assertIsNone(snapshot([row],'MLB1',START,END)['rows'][1]['quantity'])
        row=observation();row['evidence']['inventories'][1]['reason']='HTTP 403'
        self.assertIsNone(snapshot([row],'MLB1',START,END)['rows'][1]['quantity'])
        row=observation();row['evidence']['inventories'].append(dict(row['evidence']['inventories'][1]))
        self.assertIsNone(snapshot([row],'MLB1',START,END)['rows'][1]['quantity'])
        row=observation();row['evidence']['inventories']=[]
        self.assertTrue(all(r['quantity'] is None for r in snapshot([row],'MLB1',START,END)['rows']))

    def test_item_and_period_scope_and_partial_state_are_explicit(self):
        row=observation();row['item_id']='MLB2'
        self.assertEqual(snapshot([row],'MLB1',START,END)['rows'],[])
        self.assertEqual(snapshot([observation(STAMP+86400)],'MLB1',START,END)['rows'],[])
        row=observation();row['evidence']['partial']=True
        self.assertTrue(snapshot([row],'MLB1',START,END)['partial'])
        self.assertIn('não representam todas as variações',render_snapshot(1,ARGS,LISTING,[row],START,END))

    def test_pagination_clamps_preserves_selection_and_whitelists_parameters(self):
        args=dict(ARGS,full_consultas='2',secret='ignored')
        rows,nav=paginate(list(range(51)),1,args,'full_dias',20,'full-dias')
        self.assertEqual(rows,list(range(20)))
        import re
        href=unescape(re.search(r'href="([^"]+)"',nav).group(1));params=parse_qs(urlsplit(href).query)
        self.assertEqual(params['item_id'],['MLB1']);self.assertEqual(params['full_consultas'],['2'])
        self.assertEqual(params['inicio'],['2026-09-01']);self.assertNotIn('secret',params)
        for page,expected in [('bad',0),('-1',0),('999',40)]:
            selected,_=paginate(list(range(51)),1,dict(ARGS,full_dias=page),'full_dias',20,'full-dias')
            self.assertEqual(selected[0],expected)

    def test_full_report_bounds_both_histories_and_summary_uses_whole_window(self):
        rows=[observation(STAMP-i*60) for i in range(40)]
        covered=[(START+timedelta(days=i)).isoformat() for i in range(30)]
        text=render_full(1,ARGS,LISTING,rows,[],[],covered,{})
        self.assertIn('30/30',text);self.assertIn('1/30',text)
        self.assertNotIn('Ainda não há coletas Full',text)
        self.assertIn('Página 1 de 2',text)
        from html.parser import HTMLParser
        class Tables(HTMLParser):
            def __init__(self):super().__init__();self.counts=[];self.current=-1
            def handle_starttag(self,tag,attrs):
                if tag=='table':self.counts.append(0);self.current+=1
                if tag=='tr':self.counts[self.current]+=1
        parser=Tables();parser.feed(text)
        self.assertEqual(parser.counts,[3,21,21,31])
        text=render_full(1,dict(ARGS,full_dias='2',full_consultas='2'),LISTING,rows,[],[],covered,{})
        parser=Tables();parser.feed(text);self.assertEqual(parser.counts,[3,21,11,11])

    def test_escape_and_malformed_evidence_remain_readable(self):
        row=observation();row['evidence']['inventories'][0]['reason']='<script>'
        text=render_full(1,ARGS,dict(LISTING,titulo='<script>'),[row],[],[],[],{})
        self.assertNotIn('<script>',text);self.assertIn('&lt;script&gt;',text)
        for evidence in (None,[],dict(inventories=[None,{}]),dict(inventories='bad')):
            row=observation();row['evidence']=evidence
            self.assertIn('Consultas e rastreabilidade',render_full(1,ARGS,LISTING,[row],[],[],[],{}))
