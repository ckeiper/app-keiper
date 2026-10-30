import datetime as dt
import unittest
from decimal import Decimal as D
from unittest.mock import Mock
from investigation_evidence import load_bulk
from sales_decline import render

END=dt.date(2026,10,20)

def ranking():
    return dict(available=True,rows={
        'MLB1':dict(value=D(50),previous_value=D(100),orders=1,previous_orders=2,units=1,previous_units=2),
        'MLB2':dict(value=D(150),previous_value=D(100),orders=3,previous_orders=2,units=3,previous_units=2)})

class DeclineSignalsTests(unittest.TestCase):
    def test_bulk_reads_are_tenant_scoped_bounded_and_only_analyze_losses(self):
        stamp=int(dt.datetime(2026,10,20,12,tzinfo=dt.timezone(dt.timedelta(hours=-3))).timestamp())
        query=Mock(side_effect=[[],[dict(item_id='MLB1',observed_at=stamp,state='empty',logistics='fulfillment')]])
        result=load_bulk(None,query,42,ranking(),END)
        self.assertEqual(set(result),{'MLB1'})
        self.assertEqual(result['MLB1']['codes'],['full'])
        self.assertEqual(query.call_count,2)
        self.assertEqual(query.call_args_list[0].args[2],(42,'2026-10-07','2026-10-20'))
        for call in query.call_args_list:
            self.assertIn('conexao_id=%s',call.args[1])
        self.assertEqual(query.call_args_list[1].args[2][0],42)

    def test_no_reads_when_coverage_invalid_or_no_losses(self):
        query=Mock(side_effect=AssertionError('Unexpected read'))
        self.assertEqual(load_bulk(None,query,1,dict(available=False),END),{})
        self.assertEqual(load_bulk(None,query,1,dict(available=True,rows={}),END),{})
        query.assert_not_called()

    def test_filters_search_pagination_and_coverage_disclosure(self):
        source=ranking();source['rows']['MLB3']=dict(source['rows']['MLB1'])
        evidence={'MLB1':dict(actions=[dict(title='Full observado',action='Conferir reposição')],codes=['full'],visits_days=4,full_days=1,expected=14),
                  'MLB3':dict(actions=[],codes=[],visits_days=0,full_days=0,expected=14)}
        output=render(source,[],1,{'sinal_queda':'full'},END,evidence_by_item=evidence)
        self.assertIn('1–1 de 1',output)
        self.assertIn('4/14 dias',output)
        self.assertIn('Conferir reposição',output)
        self.assertNotIn('/MLB3',output)
        output=render(source,[],1,{'sinal_queda':'sem_sinais'},END,evidence_by_item=evidence)
        self.assertNotIn('/MLB1',output)
        self.assertIn('confira a cobertura',output)
        output=render(source,[],1,{'sinal_queda':'full','busca_queda':'MLB3'},END,evidence_by_item=evidence)
        self.assertIn('0–0 de 0',output)

if __name__=='__main__':
    unittest.main()
