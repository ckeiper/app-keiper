from contextlib import nullcontext
from datetime import date, timedelta
from decimal import Decimal
import unittest
from unittest.mock import patch

from overview import build_overview, load_overview, render_overview, STALE_SECONDS
from sales_metrics import period

BOUNDS = (date(2026,10,10),date(2026,10,11),date(2026,10,8),date(2026,10,9))
NOW = 100000


def shop(cid=1, name='Loja A', status='ativa'):
    return dict(id=cid, cliente=name, status=status)


def orders(cid=1, current=100, previous=200, ncur=10, nprev=10):
    result=[]
    for suffix, day, value, n in [('c','2026-10-10',current,ncur),('p','2026-10-08',previous,nprev)]:
        for i in range(n):
            result.append(dict(conexao_id=cid,pedido_id=f'{suffix}{i}', status='paid',
                               total=Decimal(value)/n, moeda='BRL', unidades=1,
                               criado_em=day+'T12:00:00-03:00', pagamentos_json=[{'status':'approved'}]))
    return result


def coverage(*ids, timestamp=NOW):
    return [dict(conexao_id=cid,dia=f'2026-10-{i:02}',atualizado_em=timestamp)
            for cid in ids for i in range(8,12)]


class OverviewTests(unittest.TestCase):
    def test_consolidation_is_weighted_and_uses_same_cohort(self):
        data=build_overview([shop(),shop(2,'Loja B'),shop(3,'Incompleta')],
                            orders()+orders(2,300,300,30,10)+orders(3,9000,9000),
                            coverage(1,2),[],BOUNDS,now=NOW)
        self.assertEqual(data['included'],2)
        self.assertEqual(data['excluded'],1)
        self.assertEqual(data['totals']['current']['revenue'],400)
        self.assertEqual(data['totals']['current']['orders'],40)
        self.assertEqual(data['totals']['current']['ticket'],10)
        self.assertEqual(data['totals']['previous']['revenue'],500)
        self.assertEqual(data['totals']['previous']['ticket'],25)

    def test_previous_gap_excludes_shop_from_both_totals_and_drop_alerts(self):
        cov=[c for c in coverage(1) if c['dia']!='2026-10-08']
        data=build_overview([shop()],orders(),cov,[],BOUNDS,now=NOW)
        self.assertEqual(data['included'],0)
        self.assertIsNone(data['totals']['current']['revenue'])
        self.assertIsNone(data['totals']['previous']['revenue'])
        self.assertEqual([a['kind'] for a in data['alerts']],['sync'])

    def test_financial_threshold_is_inclusive_and_not_rounded(self):
        for current,expected in [(85,True),(Decimal('85.01'),False),(84,True)]:
            data=build_overview([shop()],orders(current=current,previous=100),coverage(1),[],BOUNDS,now=NOW)
            self.assertEqual(any(a['kind']=='revenue' for a in data['alerts']),expected)

    def test_order_threshold_needs_percentage_and_absolute_drop(self):
        for current,previous,expected in [(20,25,True),(21,25,False),(2,5,False),(0,5,True)]:
            data=build_overview([shop()],orders(current=100,previous=100,ncur=current,nprev=previous),
                                coverage(1),[],BOUNDS,now=NOW)
            self.assertEqual(any(a['kind']=='orders' for a in data['alerts']),expected)

    def test_alerts_sort_by_financial_loss_before_unknown_impact(self):
        data=build_overview([shop(),shop(2,'B'),shop(3,'C')],
                            orders(current=0,previous=100)+orders(2,current=700,previous=1000),
                            coverage(1,2),[],BOUNDS,now=NOW)
        self.assertEqual([a['cid'] for a in data['alerts']],[2,1,3])
        self.assertEqual(data['alerts'][0]['impact'],300)
        self.assertIsNone(data['alerts'][-1]['impact'])

    def test_no_shops_and_zero_previous_never_invent_percentages(self):
        empty=build_overview([],[],[],[],BOUNDS,now=NOW)
        self.assertIsNone(empty['totals']['current']['orders'])
        data=build_overview([shop()],orders(current=100,previous=0,nprev=0),coverage(1),[],BOUNDS,now=NOW)
        self.assertFalse(data['alerts'])
        self.assertIsNone(data['reports'][0]['change'])
        self.assertIn('Sem base percentual',render_overview(data,{}))

    def test_stale_inactive_or_unresolved_errors_suspend_drop_alerts(self):
        for status,cov,errors in [('inativa',coverage(1),[]),
                                 ('ativa',coverage(1,timestamp=NOW-STALE_SECONDS-1),[]),
                                 ('ativa',coverage(1),[dict(conexao_id=1,quando=None)]),
                                 ('ativa',coverage(1),[dict(conexao_id=1,quando=NOW+1)])]:
            data=build_overview([shop(status=status)],orders(),cov,errors,BOUNDS,now=NOW)
            self.assertEqual(data['included'],0)
            self.assertEqual([a['kind'] for a in data['alerts']],['sync'])
        recovered=build_overview([shop()],orders(),coverage(1),[dict(conexao_id=1,quando=NOW-1)],BOUNDS,now=NOW)
        self.assertEqual(recovered['included'],1)

    def test_unknown_dates_exclude_shop_but_missing_units_do_not(self):
        rows=orders()
        rows[0]['unidades']=None
        data=build_overview([shop()],rows,coverage(1),[],BOUNDS,now=NOW)
        self.assertEqual(data['included'],1)
        rows[0]['criado_em']=None
        data=build_overview([shop()],rows,coverage(1),[],BOUNDS,now=NOW)
        self.assertEqual(data['included'],0)
        self.assertEqual([a['kind'] for a in data['alerts']],['sync'])

    def test_unauthorized_records_never_reach_totals_names_or_alerts(self):
        data=build_overview([shop()],orders()+orders(99,90000,100000),coverage(1,99),
                            [dict(conexao_id=99,quando=NOW+1)],BOUNDS,now=NOW)
        self.assertEqual(data['totals']['current']['revenue'],100)
        self.assertTrue(all(a['cid']==1 for a in data['alerts']))
        self.assertNotIn('/painel/99',render_overview(data,{}))

    def test_filters_dates_and_escaping(self):
        for n in (7,15,30,60,90):
            b=period({'periodo':str(n)},date(2026,10,15))
            self.assertEqual((b[1]-b[0]).days,(b[3]-b[2]).days)
        data=build_overview([shop(name='<script>evil</script>')],orders(),coverage(1),[],BOUNDS,now=NOW)
        view=render_overview(data,{},admin=True)
        self.assertIn('&lt;script&gt;evil',view)
        self.assertNotIn('<script>evil',view)
        self.assertIn("action='/painel'",view)
        self.assertIn('/usuarios',view)
        self.assertNotIn('/usuarios',render_overview(data,{},admin=False))

    def test_loader_uses_batched_authorized_bounded_snapshot(self):
        class Conn:
            def set_session(self,**kwargs):
                self.options=kwargs
        conn=Conn()
        calls=[]
        def query(c,sql,params):
            calls.append((sql,params))
            self.assertEqual(params[0],[1,2])
            if 'FROM pedidos' in sql:
                self.assertIn('LIMIT',sql)
            return []
        load_overview([shop(),shop(2)],{},lambda:nullcontext(conn),query)
        self.assertEqual(len(calls),3)
        self.assertEqual(conn.options,dict(isolation_level='REPEATABLE READ',readonly=True))

    def test_safety_limit_never_exposes_truncated_subtotals(self):
        data=build_overview([shop()],orders(),coverage(1),[],BOUNDS,now=NOW,limited=True)
        self.assertEqual(data['included'],0)
        self.assertIsNone(data['totals']['current']['revenue'])
        self.assertEqual([a['kind'] for a in data['alerts']],['sync'])
        self.assertNotIn('R$ 100,00',render_overview(data,{}))


if __name__=='__main__':
    unittest.main()
