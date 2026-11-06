import contextlib
from copy import deepcopy
from datetime import date,timedelta
from decimal import Decimal
import unittest
from unittest.mock import Mock
from flask import Flask
from listing_weekly_pattern import analyze,render,register,window

TODAY=date(2026,11,5)


def fixture(cid=7,item='MLB1'):
    start,end=window(TODAY);orders=[];items=[];covered=[]
    for i in range(56):
        day=start+timedelta(days=i);qty=day.weekday()+1;covered.append(day.isoformat())
        orders.append(dict(conexao_id=cid,pedido_id=str(i+1),status='paid',total=qty*10,moeda='BRL',
            criado_em=day.isoformat()+'T12:00:00-03:00',pagamentos_json=[dict(status='approved')],unidades=qty))
        items.append(dict(conexao_id=cid,pedido_id=str(i+1),item_id=item,quantidade=qty,preco_unitario=10))
    return dict(orders=orders,items=items,coverage=covered,pending=False)


class PatternTests(unittest.TestCase):
    def test_window_always_eight_complete_monday_sunday_weeks(self):
        for offset in range(7):
            today=date(2026,11,2)+timedelta(days=offset);start,end=window(today)
            self.assertEqual(start,date(2026,9,7));self.assertEqual(end,date(2026,11,1))
            self.assertLess(end,today);self.assertEqual((end-start).days+1,56)
        self.assertEqual(window(date(2026,11,9))[1],date(2026,11,8))

    def test_exact_distribution_denominators_and_no_input_mutation(self):
        context=fixture();before=deepcopy(context);data=analyze(context,7,'MLB1',TODAY)
        self.assertEqual(context,before);self.assertTrue(data['available']);self.assertEqual(data['covered'],56)
        self.assertEqual(data['summary']['units'],224);self.assertEqual(data['summary']['orders'],56)
        self.assertEqual(sum(r['total'] for r in data['rows']),224)
        for i,row in enumerate(data['rows']):
            self.assertEqual((row['total'],row['mean'],row['median'],row['minimum'],row['maximum'],row['selling_weeks']),
                             (8*(i+1),Decimal(i+1),i+1,i+1,i+1,8))

    def test_zeros_median_and_spike_remain_descriptive(self):
        context=fixture();values=[0,1,2,3,4,5,6,50]
        for i,qty in enumerate(values):
            index=i*7
            if not qty:context['orders'][index]['status']='cancelled'
            else:
                context['orders'][index].update(unidades=qty,total=qty*10)
                context['items'][index]['quantidade']=qty
        data=analyze(context,7,'MLB1',TODAY);r=data['rows'][0]
        self.assertEqual((r['total'],r['mean'],r['median'],r['minimum'],r['maximum'],r['selling_weeks']),
                         (71,Decimal(71)/8,3.5,0,50,7))
        zero=analyze(dict(context,orders=[],items=[]),7,'MLB1',TODAY)
        self.assertTrue(zero['available']);self.assertEqual(zero['summary']['units'],0)
        self.assertTrue(all(r['share'] is None for r in zero['rows']))
        self.assertIn('Participação não calculada',render(7,'MLB1',{},zero))

    def test_missing_coverage_invalid_items_and_pending_never_become_zero(self):
        for change in ('coverage','mapping','price','payments','units','pending','foreign'):
            with self.subTest(change=change):
                c=fixture()
                if change=='coverage':c['coverage'].pop()
                if change=='mapping':c['items'].pop()
                if change=='price':c['items'][0]['preco_unitario']=None
                if change=='payments':c['orders'][0]['pagamentos_json']=None
                if change=='units':c['orders'][0]['unidades']=None
                if change=='pending':c['pending']=True
                if change=='foreign':c['items'][0]['conexao_id']=8
                data=analyze(c,7,'MLB1',TODAY)
                self.assertFalse(data['available']);self.assertEqual(data['rows'],[])
                self.assertNotIn('<table>',render(7,'MLB1',{},data));self.assertTrue(data['reason'])

    def test_median_preserves_half_unit_at_large_counts(self):
        context=fixture()
        for i in range(8):
            qty=10**16+i;index=i*7
            context['orders'][index].update(unidades=qty,total=qty*10)
            context['items'][index]['quantidade']=qty
        row=analyze(context,7,'MLB1',TODAY)['rows'][0]
        self.assertEqual(row['median'],Decimal('10000000000000003.5'))

    def test_item_scope_timezone_and_closed_week_boundaries(self):
        c=fixture();start,end=window(TODAY)
        c['orders'][0]['criado_em']=(start+timedelta(days=1)).isoformat()+'T01:00:00Z' # Monday 22h Brasília
        d=analyze(c,7,'MLB1',TODAY);self.assertEqual(d['rows'][0]['total'],8)
        c['orders'][-1]['criado_em']=(end+timedelta(days=1)).isoformat()+'T02:59:59Z' # Sunday
        self.assertEqual(analyze(c,7,'MLB1',TODAY)['rows'][-1]['total'],56)
        c['orders'][-1]['criado_em']=(end+timedelta(days=1)).isoformat()+'T03:00:00Z' # excluded Monday
        self.assertEqual(analyze(c,7,'MLB1',TODAY)['rows'][-1]['total'],49)
        self.assertEqual(analyze(c,7,'MLB2',TODAY)['summary']['units'],0)
        c=fixture();c['orders'][0]['criado_em']=start.isoformat()+'T12:00:00' # no timezone
        self.assertFalse(analyze(c,7,'MLB1',TODAY)['available'])

    def test_html_escapes_and_states(self):
        data=analyze(fixture(),7,'MLB1',TODAY)
        text=render(7,'MLB1',dict(titulo='<script>title()</script>'),data)
        self.assertIn('&lt;script&gt;title()',text);self.assertNotIn('<script>',text)
        self.assertEqual(text.count('class="wp-bar-row"'),7)
        self.assertEqual(text.count('coleta coberta</span>'),56)
        self.assertIn('sem previsão ou sazonalidade anual validada',text)
        self.assertNotIn('method="post"',text)

    def test_readonly_route_scope_roles_and_constant_query_count(self):
        app=Flask(__name__);app.secret_key='test';query=Mock();execute=Mock()
        register(app,lambda f:f,lambda cid:cid==7,lambda:contextlib.nullcontext(None),query,execute,lambda *a:a[-1],today=lambda:TODAY)
        client=app.test_client();path='/anuncios/7/MLB1/padrao-semanal'
        self.assertEqual(client.get(path).status_code,403);query.assert_not_called()
        with client.session_transaction() as s:s['tipo']='admin'
        self.assertEqual(client.get('/anuncios/8/MLB1/padrao-semanal').status_code,403)
        self.assertEqual(client.get('/anuncios/7/INVALID/padrao-semanal').status_code,404)
        query.return_value=[];self.assertEqual(client.get(path).status_code,404)
        c=fixture();query.reset_mock();query.side_effect=[[dict(cliente='Loja',titulo='Produto')],c['orders'],c['items'],[dict(dia=d) for d in c['coverage']],[dict(pending=False)]]
        self.assertEqual(client.get(path).status_code,200);self.assertEqual(query.call_count,5)
        self.assertEqual(query.call_args_list[0].args[2],(7,'MLB1'))
        self.assertTrue(all(call.args[2][0]==7 for call in query.call_args_list))
        self.assertIn('READ ONLY',execute.call_args.args[1]);self.assertEqual(client.post(path).status_code,405)

    def test_four_week_comparison_uses_equal_occurrences_and_reconciles(self):
        data=analyze(fixture(),7,'MLB1',TODAY);c=data['comparison'];start,end=window(TODAY)
        self.assertEqual((c['previous_start'],c['previous_end'],c['recent_start'],c['recent_end']),
                         (start,start+timedelta(days=27),start+timedelta(days=28),end))
        self.assertEqual((c['previous'],c['recent'],c['change'],c['percent']),(112,112,0,Decimal(0)))
        self.assertEqual(sum(r['previous'] for r in data['rows']),112)
        self.assertEqual(sum(r['recent'] for r in data['rows']),112)
        for i,r in enumerate(data['rows']):
            self.assertEqual(r['previous']+r['recent'],r['total'])
            self.assertEqual((r['previous_mean'],r['recent_mean'],r['change'],r['percent']),
                             (Decimal(i+1),Decimal(i+1),0,Decimal(0)))

    def test_comparison_mixed_growth_and_decline_keep_correct_denominators(self):
        context=fixture()
        for i in range(28,56):
            if i%7==6:context['orders'][i]['status']='cancelled'
            else:
                qty=2*(i%7+1);context['orders'][i].update(unidades=qty,total=qty*10)
                context['items'][i]['quantidade']=qty
        data=analyze(context,7,'MLB1',TODAY);c=data['comparison']
        self.assertEqual((c['previous'],c['recent'],c['change'],c['percent']),(112,168,56,Decimal(50)))
        monday,sunday=data['rows'][0],data['rows'][6]
        self.assertEqual((monday['previous'],monday['recent'],monday['change'],monday['percent']),(4,8,4,Decimal(100)))
        self.assertEqual((sunday['previous'],sunday['recent'],sunday['change'],sunday['percent']),(28,0,-28,Decimal(-100)))
        self.assertEqual(sum(r['change'] for r in data['rows']),c['change'])

    def test_comparison_zero_base_stays_undefined_and_recent_zero_is_decline(self):
        context=fixture()
        for order in context['orders'][:28]:order['status']='cancelled'
        data=analyze(context,7,'MLB1',TODAY)
        self.assertEqual((data['comparison']['previous'],data['comparison']['recent']),(0,112))
        self.assertIsNone(data['comparison']['percent']);self.assertTrue(all(r['percent'] is None for r in data['rows']))
        html=render(7,'MLB1',{},data)
        self.assertIn('— · base zero',html);self.assertNotIn('Infinity',html)
        zero=analyze(dict(context,orders=[],items=[]),7,'MLB1',TODAY)
        self.assertIsNone(zero['comparison']['percent']);self.assertEqual(zero['comparison']['change'],0)
        context=fixture()
        for order in context['orders'][28:]:order['status']='cancelled'
        self.assertEqual(analyze(context,7,'MLB1',TODAY)['comparison']['percent'],Decimal(-100))

    def test_comparison_midpoint_uses_brasilia_dates_and_blocks_either_half_gap(self):
        context=fixture();start,end=window(TODAY);midpoint=start+timedelta(days=28)
        context['orders'][27]['criado_em']=midpoint.isoformat()+'T02:59:59Z'
        self.assertEqual(analyze(context,7,'MLB1',TODAY)['comparison']['previous'],112)
        context['orders'][27]['criado_em']=midpoint.isoformat()+'T03:00:00Z'
        data=analyze(context,7,'MLB1',TODAY)
        self.assertEqual((data['comparison']['previous'],data['comparison']['recent']),(105,119))
        for index in (0,27,28,55):
            c=fixture();c['coverage'].pop(index);d=analyze(c,7,'MLB1',TODAY)
            self.assertFalse(d['available']);self.assertIsNone(d['comparison'])
            self.assertNotIn('class="wp-comparison"',render(7,'MLB1',{},d))

    def test_comparison_render_keeps_totals_means_and_limits_explicit(self):
        html=render(7,'MLB1',{},analyze(fixture(),7,'MLB1',TODAY))
        self.assertIn('quatro ocorrências de cada dia',html)
        self.assertEqual(html.count('class="wp-cmp-series"'),14)
        self.assertIn('recente menos anterior',html)
        self.assertIn('não identifica causa',html.lower())
        self.assertIn('tabindex="0"><table><caption>Totais de unidades',html)
