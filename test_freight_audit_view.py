import unittest
from datetime import date,datetime,timezone
from freight_audit_view import render_page,coverage,history


def report():
    return dict(importado_em=datetime(2026,10,27,14,0,tzinfo=timezone.utc),resumo=dict(
        period_start='2026-09-17',period_end='2026-10-17',rows=120,seller_shipping_total='0.00'))


class FreightAuditViewTests(unittest.TestCase):
    def test_empty_history_and_unknown_coverage_do_not_invent_zero_or_records(self):
        body=render_page('csrf',True,'Loja fictícia')
        self.assertIn('Seu primeiro relatório',body);self.assertIn('Sem cobertura',body)
        self.assertNotIn('R$ 0,00',body);self.assertNotIn('fa-history-table',body.split("<div class='freight-audit'>")[1])

    def test_known_zero_remains_zero_and_dates_keep_their_source_meaning(self):
        body=render_page('csrf',True,'Loja fictícia',[report()])
        self.assertIn('17/09/2026 a 17/10/2026',body);self.assertIn('R$ 0,00',body)
        self.assertIn('27/10/2026 às 11:00',body)
        value=coverage([dict(dia=date(2026,10,26),resumo={'seller_shipping_total':'0.00'})],today=date(2026,10,27))
        self.assertIn('1 de 30 dias',value);self.assertIn('R$ 0,00',value)
        self.assertEqual(value.count("class='fa-day is-covered'"),1)
        self.assertEqual(value.count("class='fa-day'"),29)

    def test_client_does_not_get_import_or_consolidation_controls_or_history(self):
        body=render_page('csrf',False,'Loja fictícia',[report()])
        markup=body.split("<div class='freight-audit'>")[1].split('<script>')[0]
        self.assertNotIn("value='importar'",markup);self.assertNotIn("value='consolidar'",markup)
        self.assertNotIn("id='fa-history'",markup);self.assertNotIn("id='fa-coverage'",markup)
        self.assertIn('Pré-visualizar planilha',body)

    def test_shop_csrf_and_stored_dates_are_escaped(self):
        value=report();value['resumo']['period_start']='<script>'
        body=render_page("' onfocus='bad",True,'<img onerror=x>',[value])
        self.assertNotIn('<img onerror=x>',body);self.assertNotIn("value='' onfocus",body)
        self.assertNotIn('<script></script>',body);self.assertIn('Data não informada',body)

    def test_server_result_is_before_history_and_advanced_confirmation_starts_unchecked(self):
        body=render_page('csrf',True,'Loja fictícia',[report()],result='<p>Resultado sintético</p>')
        self.assertLess(body.index("id='fa-results'"),body.index("id='fa-history'"))
        self.assertIn("name='completo' value='sim'",body);self.assertNotIn(' checked',body)
        self.assertIn("method='post' enctype='multipart/form-data'",body)
        self.assertIn("name='csrf_token' value='csrf'",body)
