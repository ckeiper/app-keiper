import contextlib,datetime,json,unittest
from unittest.mock import Mock
from flask import Flask
from promotion_observations import snapshot,record,periods
from promotion_comparison import register,render,comparison,finance_section
from listing_details import normalize_promotions

TODAY=datetime.date(2026,10,29)
def promotion(**kw):
    d=dict(id='P1',type='SELLER_CAMPAIGN',status='active',start='2026-10-01T00:00:00-03:00',end='2026-10-20T00:00:00-03:00',price='80',original='100',variation_id=None,conditions={});d.update(kw);return d

def reading():return dict(id=1,observed_at=1791000000,available=True,reason='consulta_item',promotions=[promotion()])

class PromotionObservationTests(unittest.TestCase):
 def test_preserves_item_fields_not_detection_as_start(self):
    normalized=normalize_promotions([dict(id='P1',type='SELLER_CAMPAIGN',status='started',price=80,start_date='2026-10-01T00:00:00-03:00',end_date='2026-10-20T00:00:00-03:00',meli_percentage=5,access_token='secret')])
    s=snapshot(dict(checked_at=123,promotions=normalized,error=None))
    self.assertEqual(s['promotions'][0]['start'],'2026-10-01T00:00:00-03:00');self.assertNotIn('secret',json.dumps(s));self.assertEqual(s['promotions'][0]['conditions']['meli_percentage'],'5')
    missing=snapshot(dict(checked_at=123,promotions=[promotion(start=None)]));self.assertIsNone(missing['promotions'][0]['start'])
 def test_failed_attempt_never_reuses_old_confirmation(self):
    s=snapshot(dict(checked_at=100,attempted_at=200,promotions=[promotion()],error='HTTP 403 secret'))
    self.assertEqual((s['observed_at'],s['available'],s['promotions']),(200,False,[]));self.assertNotIn('secret',str(s))
    self.assertFalse(snapshot(dict(checked_at=100,promotions=[None]))['available'])
    self.assertFalse(snapshot(dict(checked_at=100,promotions=[promotion()]*201))['available'])
    for stamp in [True,None,-1,float('nan'),10**100]:self.assertIsNone(snapshot(dict(checked_at=stamp,promotions=[])))
 def test_archive_append_only_scoped_and_deduplicated(self):
    e=Mock();record(None,e,7,'MLB1',dict(checked_at=100,promotions=[promotion()]))
    self.assertIn('DO NOTHING',e.call_args.args[1]);self.assertEqual(e.call_args.args[2][:3],(7,'MLB1',100));self.assertNotIn('UPDATE',e.call_args.args[1])
 def test_whole_days_timezone_and_equal_windows(self):
    r=periods(promotion(),TODAY,7);self.assertTrue(r['available'])
    self.assertEqual((r['start'],r['end'],r['previous_start'],r['previous_end']),(datetime.date(2026,10,1),datetime.date(2026,10,7),datetime.date(2026,9,24),datetime.date(2026,9,30)))
    r=periods(promotion(start='2026-10-01T12:00:00-03:00'),TODAY,7)
    self.assertEqual(r['start'],datetime.date(2026,10,2));self.assertEqual(r['previous_end'],datetime.date(2026,9,30))
    self.assertFalse(periods(promotion(start='2026-10-01T00:00:00'),TODAY)['available'])
    self.assertFalse(periods(promotion(end='2026-10-07T23:59:59-03:00'),TODAY)['available'])
 def test_removed_scheduled_unknown_or_variant_never_confirms_period(self):
    for kwargs in [dict(status='finished'),dict(status='candidate'),dict(status='pending'),dict(type='BANK'),dict(type='VOLUME'),dict(variation_id='1'),dict(start=None),dict(end='bad'),dict(start='0001-01-01T00:00:00-03:00'),dict(start='9999-12-30T00:00:00-03:00',end='9999-12-31T00:00:00-03:00')]:
        with self.subTest(kwargs=kwargs):self.assertFalse(periods(promotion(**kwargs),TODAY)['available'])
    self.assertFalse(periods(promotion(),datetime.date(2026,10,7))['available'])
    self.assertFalse(periods(promotion(),TODAY,30)['available'])
 def test_unverified_dates_block_before_database_reads(self):
    q=Mock();r=comparison(None,q,7,'MLB1',promotion(start=None),TODAY,7);self.assertFalse(r['available']);q.assert_not_called()
 def test_view_escapes_and_separates_schedules_and_observations(self):
    s=reading();s['promotions'][0]['conditions']={'offer_id':'<script>'}
    text=render(7,'MLB1','<script>',[s],1,1,1,s,0,dict(available=False,reason='Aguardando dados'),7,TODAY)
    self.assertNotIn('<script>',text);self.assertIn('&lt;script&gt;',text);self.assertIn('Não confirmam',text)
    s['available']=False;s['reason']='consulta_indisponivel';self.assertNotIn('Oferta consultada',render(7,'MLB1','X',[s],1,1,1,s,0,None,7,TODAY))
 def test_authorization_snapshot_read_only_and_no_cross_store(self):
    app=Flask(__name__);app.secret_key='test';q=Mock();e=Mock();register(app,lambda f:f,lambda cid:cid==7,lambda:contextlib.nullcontext(None),q,e,lambda *a:a[-1]);c=app.test_client();url='/anuncios/7/MLB1/promocoes-resultados'
    self.assertEqual(c.get(url).status_code,403)
    with c.session_transaction() as session:session['tipo']='admin'
    self.assertEqual(c.get(url.replace('/7/','/8/')).status_code,403);q.assert_not_called()
    self.assertEqual(c.get(url+'?dias=8').status_code,400)
    q.side_effect=[[dict(cliente='Loja',titulo='Anúncio')],[dict(n=0)],[]];r=c.get(url);self.assertEqual(r.status_code,200);self.assertIn('READ ONLY',e.call_args.args[1]);self.assertIn('no-store',r.headers['Cache-Control'])
    self.assertEqual(c.post(url).status_code,405)


class PromotionFinanceRenderingTests(unittest.TestCase):
 def test_cost_sources_follow_the_actual_windows(self):
    from test_profitability_action import fixture,TODAY as finance_today,ITEM
    from profitability_action import load
    periods_,orders,items,records=fixture()
    result=load(None,Mock(return_value=records),1,ITEM,periods_,orders,items,finance_today)
    text=finance_section(result,1,ITEM,periods_)
    self.assertIn('R$ 640,00',text);self.assertIn('R$ 1.340,00',text)
    self.assertIn('registro=1',text);self.assertIn('registro=2',text)
    self.assertNotIn('excluindo o dia do registro',text)
