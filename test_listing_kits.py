import contextlib
import datetime
import secrets
import unittest
from decimal import Decimal
from unittest.mock import Mock
from flask import Flask
from listing_kits import validate,economics,check_links,save,evidence
from listing_kit_view import register,render

TODAY=datetime.date(2026,10,29)
def form():
    return dict(confirmed='yes',mode='proposal',submission_key='k'*32,source='Planilha conferida de composição e custos',source_date=TODAY.isoformat(),days='7',
        label_0='Produto A',item_0='MLB2',qty_0='2',cost_0='10,00',reference_0='Nota fiscal do fornecedor',
        price='50',fee_pct='10',fixed_fee='1',tax_pct='5',shipping='2',ads='3',packaging='1',adjustments='0')
def row(stock=8,stamp=100000):return dict(item_id='MLB2',quantidade=stock,atualizado_em=stamp,status='active',titulo='Produto A')

class KitTests(unittest.TestCase):
 def test_explicit_composition_financials_and_fixed_period(self):
    c,key=validate(form(),TODAY);r=economics(c)
    self.assertEqual(c['start'],'2026-10-22');self.assertEqual(c['end'],'2026-10-28')
    self.assertEqual((r['products'],r['fees'],r['taxes'],r['total'],r['contribution']),(20,6,Decimal('2.50'),Decimal('34.50'),Decimal('15.50')))
    self.assertEqual(r['margin'],31)
    f=form();f.update(price='1',fee_pct='100',tax_pct='100');self.assertLess(economics(validate(f,TODAY)[0])['contribution'],0)
 def test_missing_costs_sources_or_confirmation_never_zero(self):
    for key in ('cost_0','shipping','reference_0','source','confirmed','mode','submission_key','source_date'):
        f=form();f.pop(key)
        with self.subTest(key=key),self.assertRaises(ValueError):validate(f,TODAY)
    for values in [dict(qty_0='1'),dict(qty_0='0'),dict(qty_0='1.5'),dict(qty_0='-2'),dict(cost_0='nan'),dict(price='0'),dict(source_date='2099-01-01'),dict(days='90'),dict(fee_pct='100.01')]:
        with self.subTest(values=values),self.assertRaises(ValueError):validate(dict(form(),**values),TODAY)
 def test_duplicate_components_and_cross_store_links(self):
    f=form();f.update(label_1='Produto A',qty_1='1',cost_1='1',reference_1='Documento de custo válido')
    with self.assertRaises(ValueError):validate(f,TODAY)
    f['label_1']='Produto B';f['item_1']='MLB2'
    with self.assertRaises(ValueError):validate(f,TODAY)
    c,_=validate(form(),TODAY)
    with self.assertRaises(ValueError):check_links(c,[],'MLB1')
    with self.assertRaises(ValueError):check_links(c,[row()],'MLB2')
    check_links(c,[row()],'MLB1')
 def test_stock_limits_stale_manual_and_missing_sales(self):
    c,_=validate(form(),TODAY);ctx=dict(orders=[],items=[],coverage=[],pending=False)
    e=evidence(c,ctx,[row()],'MLB1',datetime.date.fromisoformat(c['start']),datetime.date.fromisoformat(c['end']),100000)
    self.assertEqual(e['capacity'],4);self.assertIsNone(e['sales']['orders'])
    for listing in [row(stamp=1),row(stock=None),row(stock=-1)]:
        self.assertIsNone(evidence(c,ctx,[listing],'MLB1',TODAY,TODAY,100000)['capacity'])
    self.assertEqual(evidence(c,ctx,[row(stock=0)],'MLB1',TODAY,TODAY,100000)['capacity'],0)
    c['components'][0]['item']=None;self.assertIsNone(evidence(c,ctx,[],'MLB1',TODAY,TODAY,100000)['capacity'])
 def test_save_idempotence_without_overwrite(self):
    c,key=validate(form(),TODAY);q=Mock(return_value=[dict(id=4)])
    self.assertEqual(save(None,q,7,'MLB1',c,key,1,123),4);call=q.call_args;self.assertIn('DO NOTHING',call.args[1]);digest=call.args[2][-1]
    q=Mock(side_effect=[[],[dict(id=4,payload_hash=digest)]]);self.assertEqual(save(None,q,7,'MLB1',c,key,1,124),4)
    q=Mock(side_effect=[[],[dict(id=4,payload_hash='other')]])
    with self.assertRaises(ValueError):save(None,q,7,'MLB1',c,key,1,124)
 def test_verified_history_is_not_demand_for_a_proposal(self):
    c,_=validate(form(),TODAY);start=datetime.date.fromisoformat(c['start']);end=datetime.date.fromisoformat(c['end'])
    covered=[(start+datetime.timedelta(days=i)).isoformat() for i in range(7)]
    orders=[dict(conexao_id=7,pedido_id='1',status='paid',moeda='BRL',total=100,criado_em=end.isoformat()+'T12:00:00-03:00',pagamentos_json=[dict(status='approved')],unidades=3)]
    items=[dict(conexao_id=7,pedido_id='1',item_id='MLB1',quantidade=3,preco_unitario=30)]
    ctx=dict(orders=orders,items=items,coverage=covered,pending=False);proof=evidence(c,ctx,[row()],'MLB1',start,end,100000)
    self.assertEqual(proof['sales']['orders'],1);self.assertEqual(proof['sales']['gross_items'],90)
    record=dict(id=1,composition=c,created_at=123,created_by=1)
    html=render(7,'MLB1','<script>','csrf','k'*32,{},record,proof,[],1,1)
    self.assertIn('Demanda do kit proposto ainda não validada',html);self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>',html)
    ctx['pending']=True;self.assertIsNone(evidence(c,ctx,[row()],'MLB1',start,end,100000)['sales']['orders'])
 def test_auth_csrf_missing_listing_and_scoped_reads(self):
    app=Flask(__name__);app.secret_key='x';q=Mock();e=Mock();register(app,lambda f:f,lambda cid:cid==7,lambda:contextlib.nullcontext(None),q,e,lambda *a:a[-1]);c=app.test_client();url='/anuncios/7/MLB1/kits'
    self.assertEqual(c.get(url).status_code,403)
    with c.session_transaction() as s:s.update(tipo='admin',usuario_id=1,_csrf='csrf')
    self.assertEqual(c.get(url.replace('/7/','/8/')).status_code,403);self.assertEqual(c.post(url,data=form()).status_code,403);q.assert_not_called()
    q.return_value=[];self.assertEqual(c.get(url).status_code,404)
    q.side_effect=[[dict(cliente='Loja',titulo='Kit')],[dict(n=0)],[]]
    r=c.get(url);self.assertEqual(r.status_code,200);self.assertIn('no-store',r.headers['Cache-Control']);self.assertIn('READ ONLY',e.call_args.args[1])
    for call in q.call_args_list:self.assertEqual(call.args[2][:2],(7,'MLB1'))
