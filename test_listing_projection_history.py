import contextlib
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock
import unittest
from flask import Flask
from listing_projection_history import evaluate,render
from listing_weekly_pattern import analyze,register
from test_listing_weekly_pattern import fixture,TODAY


def daily_context(first=1,recent=2):
    context=fixture()
    for i,order in enumerate(context['orders']):
        qty=first if i<28 else recent
        if not qty:order['status']='cancelled'
        else:
            order.update(unidades=qty,total=qty*10);context['items'][i]['quantidade']=qty
    return context


class ProjectionHistoryTests(unittest.TestCase):
    def test_fixed_windows_and_constant_mean_have_exact_zero_errors(self):
        source=analyze(fixture(),7,'MLB1',TODAY);before=deepcopy(source);result=evaluate(source)
        self.assertEqual(source,before);self.assertTrue(result['available']);self.assertEqual(len(result['rows']),4)
        for i,row in enumerate(result['rows']):
            self.assertEqual((row['training_end']-row['training_start']).days,27)
            self.assertEqual((row['test_end']-row['test_start']).days,6)
            self.assertEqual(row['test_start'],row['training_end']+timedelta(days=1))
            self.assertEqual(row['training_start'],source['start']+timedelta(days=7*i))
            self.assertEqual((row['estimate'],row['actual'],row['error']),(Decimal(28),28,Decimal(0)))
        self.assertEqual(result['rows'][-1]['test_end'],source['end'])
        self.assertEqual((result['mae'],result['bias'],result['absolute_error_percent']),(Decimal(0),Decimal(0),Decimal(0)))

    def test_change_keeps_fractional_estimates_and_exact_aggregate_errors(self):
        result=evaluate(analyze(daily_context(),7,'MLB1',TODAY))
        self.assertEqual([r['estimate'] for r in result['rows']],[Decimal('7'),Decimal('8.75'),Decimal('10.5'),Decimal('12.25')])
        self.assertEqual([r['actual'] for r in result['rows']],[14]*4)
        self.assertEqual((result['estimate'],result['actual']),(Decimal('38.5'),56))
        self.assertEqual((result['mae'],result['bias'],result['absolute_error_percent']),
                         (Decimal('4.375'),Decimal('-4.375'),Decimal('31.25')))
        self.assertEqual(sum(r['error'] for r in result['rows']),result['estimate']-result['actual'])

    def test_zero_realized_does_not_invent_percentage_and_error_can_exceed_100(self):
        zero=evaluate(analyze(daily_context(0,0),7,'MLB1',TODAY))
        self.assertEqual(zero['mae'],0);self.assertIsNone(zero['absolute_error_percent'])
        result=evaluate(analyze(daily_context(1,0),7,'MLB1',TODAY))
        self.assertEqual(result['actual'],0);self.assertEqual(result['bias'],Decimal('4.375'))
        self.assertIsNone(result['absolute_error_percent'])
        large=evaluate(analyze(daily_context(100,1),7,'MLB1',TODAY))
        self.assertGreater(large['absolute_error_percent'],100)

    def test_later_sales_never_change_estimates_for_earlier_targets(self):
        context=fixture();baseline=evaluate(analyze(context,7,'MLB1',TODAY))
        for i in range(49,56):
            context['orders'][i].update(unidades=999,total=9990);context['items'][i]['quantidade']=999
        changed=evaluate(analyze(context,7,'MLB1',TODAY))
        self.assertEqual([r['estimate'] for r in changed['rows']],[r['estimate'] for r in baseline['rows']])
        self.assertEqual([r['actual'] for r in changed['rows'][:3]],[r['actual'] for r in baseline['rows'][:3]])
        self.assertNotEqual(changed['rows'][-1]['actual'],baseline['rows'][-1]['actual'])

    def test_completed_target_enters_only_later_training_windows(self):
        context=fixture();baseline=evaluate(analyze(context,7,'MLB1',TODAY))
        context['orders'][28].update(unidades=101,total=1010);context['items'][28]['quantidade']=101
        changed=evaluate(analyze(context,7,'MLB1',TODAY))
        self.assertEqual(changed['rows'][0]['estimate'],baseline['rows'][0]['estimate'])
        self.assertGreater(changed['rows'][1]['estimate'],baseline['rows'][1]['estimate'])

    def test_unverified_or_broken_daily_series_never_produces_errors(self):
        for change in ('pending','coverage','price','scope'):
            c=fixture()
            if change=='pending':c['pending']=True
            if change=='coverage':c['coverage'].pop()
            if change=='price':c['items'][0]['preco_unitario']=None
            if change=='scope':c['orders'][0]['conexao_id']=8
            result=evaluate(analyze(c,7,'MLB1',TODAY));self.assertFalse(result['available']);self.assertEqual(result['rows'],[])
        source=analyze(fixture(),7,'MLB1',TODAY)
        for change in ('short','day','bool','negative','covered','end'):
            d=deepcopy(source)
            if change=='short':d['daily'].pop()
            if change=='day':d['daily'][1]['day']=d['daily'][0]['day']
            if change=='bool':d['daily'][0]['units']=True
            if change=='negative':d['daily'][0]['units']=-1
            if change=='covered':d['covered']=55
            if change=='end':d['end']+=timedelta(days=1)
            self.assertFalse(evaluate(d)['available'])

    def test_render_escapes_and_describes_only_retrospective_results(self):
        data=analyze(daily_context(),7,'MLB1',TODAY)
        html=render(7,'MLB1',dict(titulo='<script>alert(1)</script>'),data)
        self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)
        self.assertEqual(html.count('class="wp-cmp-series"'),8)
        self.assertNotIn('method="post"',html);self.assertIn('não reconstitui',html.lower())
        zero=render(7,'MLB1',{},analyze(daily_context(0,0),7,'MLB1',TODAY))
        self.assertIn('O percentual não é calculado',zero)
        bad=render(7,'MLB1',{},analyze(dict(fixture(),pending=True),7,'MLB1',TODAY))
        self.assertIn('Conferência indisponível',bad);self.assertNotIn('<table>',bad)

    def test_route_keeps_administrator_scope_readonly_and_five_queries(self):
        app=Flask(__name__);app.secret_key='test';query=Mock();execute=Mock()
        register(app,lambda f:f,lambda cid:cid==7,lambda:contextlib.nullcontext(None),query,execute,lambda *a:a[-1],today=lambda:TODAY)
        client=app.test_client();path='/anuncios/7/MLB1/conferencia-media'
        self.assertEqual(client.get(path).status_code,403);query.assert_not_called()
        with client.session_transaction() as s:s['tipo']='admin'
        self.assertEqual(client.get('/anuncios/8/MLB1/conferencia-media').status_code,403);query.assert_not_called()
        self.assertEqual(client.get(path.replace('MLB1','INVALID')).status_code,404)
        c=fixture();query.side_effect=[[dict(cliente='Loja')],c['orders'],c['items'],[dict(dia=d) for d in c['coverage']],[dict(pending=False)]]
        response=client.get(path);self.assertEqual(response.status_code,200)
        self.assertIn('Conferência histórica',response.get_data(as_text=True));self.assertEqual(query.call_count,5)
        self.assertTrue(all(call.args[2][0]==7 for call in query.call_args_list))
        self.assertIn('READ ONLY',execute.call_args.args[1]);self.assertEqual(client.post(path).status_code,405)
