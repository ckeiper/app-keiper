import contextlib,csv,io
import unittest
from unittest.mock import Mock
from flask import Flask
from price_observation_export import csv_text,register_export
from test_price_stability import END,readings

class PriceExportTests(unittest.TestCase):
 def test_csv_preserves_unknown_without_fabricated_zero(self):
    rows=readings()[:2];rows[1]['confirmed']=False
    text=csv_text('MLB1',rows);self.assertTrue(text.startswith('\ufeff'))
    parsed=list(csv.reader(io.StringIO(text.lstrip('\ufeff')),delimiter=';'))
    self.assertEqual(parsed[1][2:4],['100,00','confirmado']);self.assertEqual(parsed[2][2:4],['','nao_verificado'])
 def test_scoped_readonly_auth_export_and_limit(self):
    app=Flask(__name__);app.secret_key='test';q=Mock();e=Mock()
    register_export(app,lambda f:f,lambda cid:cid==7,lambda:contextlib.nullcontext(None),q,e,today=lambda:END)
    c=app.test_client();path='/anuncios/7/MLB1/precos-observados.csv'
    self.assertEqual(c.get(path).status_code,403)
    with c.session_transaction() as s:s.update(tipo='admin')
    self.assertEqual(c.get(path.replace('/7/','/8/')).status_code,403);self.assertEqual(c.get(path+'?dias=999').status_code,400);q.assert_not_called()
    q.side_effect=[[dict(item_id='MLB1')],readings()];r=c.get(path)
    self.assertEqual(r.status_code,200);self.assertEqual(r.headers['Cache-Control'],'no-store');self.assertIn('attachment;',r.headers['Content-Disposition'])
    self.assertEqual(q.call_args.args[2][:2],(7,'MLB1'));self.assertIn('LIMIT 5001',q.call_args.args[1]);self.assertIn('READ ONLY',e.call_args.args[1])
    q.side_effect=[[dict(item_id='MLB1')],readings()*500];self.assertEqual(c.get(path).status_code,413)
    q.side_effect=None;q.return_value=[];self.assertEqual(c.get(path).status_code,404)
