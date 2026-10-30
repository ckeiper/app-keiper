import contextlib
import csv
import io
import json
import unittest
from unittest.mock import Mock
from flask import Flask
from freight_reconciliation import FIELDS,schema_columns
from freight_sales_compare import compare_sales_rows
from freight_store import save_review,report_detail
from freight_difference_view import render,export_csv,filtered,register_export


def review():
    details=[];rows=[];refs={}
    for identifier,charge,baseline,source in [('1001',15,10,'real'),('1002',8,10,'estimado'),('1003',10,10,'real')]:
        values=dict(operation_type='Venda',operation_id=identifier,shipment_id='S'+identifier,
                    gross_shipping=charge,shipping_discount=0,seller_shipping=charge)
        rows.append([values.get(k) for k in FIELDS])
        refs[identifier]=dict(frete=baseline,frete_fonte=source,frete_verificavel=True,fechado_em='2026-10-01')
    result=compare_sales_rows(rows,schema_columns(list(FIELDS.values())),refs,[],[],details=details)
    return dict(version=1,checked_at='2026-10-27T14:00:00+00:00',comparison=result,details=details)


def report():
    return dict(period_start='2026-10-01',period_end='2026-10-01',freight_review=review())


class FreightDifferenceTests(unittest.TestCase):
    def test_order_evidence_keeps_signed_amounts_and_source_without_buyer_data(self):
        value=review();c=value['comparison']
        self.assertEqual((c['above_total'],c['below_total']),('5.00','2.00'))
        self.assertEqual(len(value['details']),2)
        self.assertEqual(value['details'][0],dict(order_id='1001',shipment_id='S1001',charged='15.00',baseline='10.00',delta='5.00',source='real',status='above',matched_by='pedido',sale_date='2026-10-01'))
        self.assertEqual(value['details'][1]['delta'],'-2.00')
        self.assertNotIn('order_id',c);self.assertNotIn('buyer',str(value))

    def test_ambiguous_or_unavailable_orders_never_get_an_invented_detail(self):
        from test_freight_sales_compare import SalesFreightComparisonTests
        case=SalesFreightComparisonTests()
        for movements,refs in [([{},{}],None),([{}],{'order':dict(frete=0,frete_fonte='real',frete_verificavel=False)})]:
            values=dict(operation_type='Venda',operation_id='payment',shipment_id='shipment',gross_shipping=20,shipping_discount=5,seller_shipping=15)
            rows=[[dict(values,**m).get(k) for k in FIELDS] for m in movements]
            details=[];result=compare_sales_rows(rows,schema_columns(list(FIELDS.values())),refs or {'order':dict(frete=12,frete_fonte='real',frete_verificavel=True)},[dict(operation_id='payment',pedido_id='order')],[],details=details)
            self.assertEqual(result['compared_orders'],0);self.assertEqual(details,[])

    def test_filter_export_and_html_use_the_same_direction_and_reference(self):
        value=report();rows,direction,source=filtered(value['freight_review'],dict(direcao='below',fonte='estimado'))
        self.assertEqual([r['order_id'] for r in rows],['1002'])
        text=render(value,6,8,dict(direcao='below',fonte='estimado'))
        self.assertIn('1002',text);self.assertNotIn('>1001<',text);self.assertIn('Estimada',text)
        parsed=list(csv.reader(io.StringIO(export_csv(value,dict(direcao='below',fonte='estimado')).lstrip('\ufeff')),delimiter=';'))
        self.assertEqual(len(parsed),2);self.assertEqual(parsed[1][:6],['1002','S1002','8,00','10,00','-2,00','estimado'])

    def test_legacy_summary_does_not_fabricate_the_missing_per_order_list_or_below_total(self):
        data=dict(period_start='2026-10-01',period_end='2026-10-01',sales_comparison=review()['comparison'])
        data['sales_comparison'].pop('below_total')
        text=render(data,6,8,{})
        self.assertIn('ainda não tem a lista por venda',text);self.assertIn('Não registrado',text)
        self.assertNotIn('fa-order-table',text);self.assertIsNone(export_csv(data,{}))

    def test_pagination_is_bounded_but_export_contains_every_filtered_difference(self):
        data=report();row=data['freight_review']['details'][0]
        data['freight_review']['details']=[dict(row,order_id=str(1000+i),delta=str(i+1)) for i in range(70)]
        text=render(data,6,8,dict(pagina='2'))
        self.assertEqual(text.count('scope="row"'),20);self.assertIn('Página 2 de 2',text)
        self.assertEqual(len(list(csv.reader(io.StringIO(export_csv(data,{})),delimiter=';'))),71)
        self.assertNotIn('scope="row">1000',render(data,6,8,{}))

    def test_html_and_csv_escape_identifiers_without_changing_amount_meaning(self):
        data=report();data['freight_review']['details'][0]['order_id']='<img onerror=x>'
        data['freight_review']['details'][0]['shipment_id']='=HYPERLINK("evil")'
        text=render(data,6,8,{})
        self.assertNotIn('<img onerror=x>',text)
        parsed=list(csv.reader(io.StringIO(export_csv(data,{})),delimiter=';'))
        self.assertTrue(parsed[1][1].startswith("'="));self.assertEqual(parsed[1][4],'5,00')

    def test_saving_review_updates_only_its_json_key_and_uses_store_and_file_hash(self):
        query=Mock(return_value=[dict(id=8)])
        self.assertEqual(save_review(None,query,6,b'synthetic',review()),8)
        sql=query.call_args.args[1];params=query.call_args.args[2]
        self.assertIn('jsonb_set',sql);self.assertIn("'{freight_review}'",sql)
        self.assertNotIn('DELETE',sql);self.assertEqual(params[1],6);self.assertEqual(len(params[2]),64)
        report_detail(None,query,6,8);self.assertEqual(query.call_args.args[2],(6,8))

    def test_csv_route_checks_role_store_and_legacy_before_export(self):
        app=Flask(__name__);app.secret_key='synthetic';query=Mock(return_value=[dict(resumo=report())])
        register_export(app,lambda f:f,lambda cid:cid==6,lambda:contextlib.nullcontext(None),query)
        client=app.test_client();url='/auditoria-frete/6/relatorios/8/diferencas.csv'
        self.assertEqual(client.get(url).status_code,403);query.assert_not_called()
        with client.session_transaction() as s:s['tipo']='admin'
        self.assertEqual(client.get(url.replace('/6/','/7/')).status_code,403);query.assert_not_called()
        response=client.get(url+'?direcao=below')
        self.assertEqual(response.status_code,200);self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertIn('1002',response.text);self.assertNotIn('1001',response.text)
        self.assertEqual(query.call_args.args[2],(6,8))
        query.return_value=[];self.assertEqual(client.get(url).status_code,404)
        query.return_value=[dict(resumo={})];self.assertEqual(client.get(url).status_code,404)
