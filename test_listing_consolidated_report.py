import contextlib,datetime,io,unittest
from unittest.mock import Mock,patch
from decimal import Decimal
from flask import Flask
from pypdf import PdfReader
from test_listing_review_report import fixture as operational_fixture
from listing_consolidated_report import sections,html_report,pdf_report,register,load
from profitability_store import load_pair,summarize_context


def fixture(days=7):
    end=datetime.date(2026,10,27);start=end-datetime.timedelta(days=days-1);prior=start-datetime.timedelta(days=days)
    op=operational_fixture();op['shop']['cliente']='Loja Teste';op['shop']['titulo']='Produto <Teste>'
    coverage=[(prior+datetime.timedelta(days=i)).isoformat() for i in range(days*2)]
    orders=[dict(conexao_id=7,pedido_id='1',status='paid',total=100,moeda='BRL',criado_em=end.isoformat()+'T12:00:00-03:00',pagamentos_json=[dict(status='approved')],unidades=2)]
    items=[dict(conexao_id=7,pedido_id='1',item_id='MLB1',quantidade=2,preco_unitario=50)]
    context=dict(orders=orders,items=items,coverage=coverage,pending=False)
    pair=dict(current=summarize_context(context,7,'MLB1',start,end),previous=summarize_context(context,7,'MLB1',prior,start-datetime.timedelta(days=1)),previous_start=prior,previous_end=start-datetime.timedelta(days=1))
    return dict(operational=op,pair=pair,context=context,visits=[dict(dia=d,visitas=10) for d in coverage],full=[],offers=[],observations_limited=False,financial=None,contribution=dict(available=False,reason='Aguardando custos documentados.'),history=[],history_limited=False,ads=[],start=start,end=end,days=days)


class ConsolidatedReportTests(unittest.TestCase):
 def test_sections_use_verified_listing_sales_and_keep_ads_separate(self):
    d=fixture();s=sections(d)
    self.assertEqual(s[0]['rows'][0],['Pedidos pagos','0','1']);self.assertEqual(s[0]['rows'][2][2],'R$ 100,00')
    self.assertIn('observacional',s[0]['rows'][-1][0]);self.assertEqual(s[2]['rows'][-1][1],'1');self.assertEqual(s[2]['rows'][-1][4],'Não observado')
    self.assertIn('não deste anúncio',s[3]['note']);self.assertEqual(s[3]['rows'][0][1],'Indisponível')
    self.assertEqual(s[4]['rows'][0][1],'Indisponível')
 def test_html_escape_and_real_pdf_content(self):
    d=fixture();html=html_report(7,'MLB1',d,123);self.assertIn('Produto &lt;Teste&gt;',html);self.assertIn('relatorio-consolidado.pdf?dias=7',html)
    pdf=pdf_report(7,'MLB1',d,123);self.assertTrue(pdf.startswith(b'%PDF-'))
    reader=PdfReader(io.BytesIO(pdf));text='\n'.join(page.extract_text() for page in reader.pages)
    self.assertIn('Loja Teste',text);self.assertIn('R$ 100,00',text);self.assertIn('Rentabilidade documentada',text);self.assertGreaterEqual(len(reader.pages),2)
 def test_missing_coverage_not_zero_and_long_notes_do_not_break_pdf(self):
    d=fixture(30);d['context']['coverage']=[];d['pair']['current'].update(orders=None,gross_items=None,reason='Cobertura incompleta.')
    from listing_content import CRITERIA
    d['operational']['reviews']={c:dict(verdict='revise',note='palavra'*500,created_at=1,created_by=1) for c in CRITERIA}
    s=sections(d);self.assertEqual(s[0]['rows'][0][2],'Indisponível');self.assertEqual(s[2]['rows'][0][1],'Indisponível')
    self.assertTrue(pdf_report(7,'MLB1',d,123).startswith(b'%PDF-'))
 def test_route_auth_readonly_download_and_no_other_store(self):
    app=Flask(__name__);app.secret_key='test';q=Mock();e=Mock();register(app,lambda f:f,lambda cid:cid==7,lambda:contextlib.nullcontext(None),q,e);c=app.test_client();base='/anuncios/7/MLB1/relatorio-consolidado'
    self.assertEqual(c.get(base).status_code,403)
    with c.session_transaction() as session:session['tipo']='admin'
    self.assertEqual(c.get(base.replace('/7/','/8/')).status_code,403);q.assert_not_called()
    self.assertEqual(c.get(base+'?dias=90').status_code,400);self.assertEqual(c.post(base).status_code,405)
    with patch('listing_consolidated_report.load',return_value=fixture()):
        response=c.get(base+'.pdf');self.assertEqual(response.status_code,200);self.assertEqual(response.mimetype,'application/pdf');self.assertIn('attachment',response.headers['Content-Disposition']);self.assertIn('no-store',response.headers['Cache-Control'])
    self.assertIn('READ ONLY',e.call_args.args[1])
 def test_missing_listing_short_circuits_before_financial_queries(self):
    q=Mock(return_value=[]);self.assertIsNone(load(None,q,7,'MLB1'));self.assertEqual(q.call_count,1);self.assertEqual(q.call_args.args[2],(7,'MLB1'))
