"""Mandatory first-access finance setup and honest promo calculations."""
import unittest
from client_onboarding import validate_tax,parse_cost,status,onboarding_page


class FinancialOnboardingTests(unittest.TestCase):
    def test_tax_requires_explicit_valid_input(self):
        self.assertEqual(validate_tax('0'),0)
        self.assertEqual(validate_tax('8,5'),8.5)
        for value in ('','-1','101','nan','inf','abc',None):
            with self.subTest(value=value),self.assertRaises(ValueError):
                validate_tax(value)

    def test_cost_validation_rejects_negative_or_nan(self):
        self.assertEqual(parse_cost('R$ 12,50'),12.5)
        for value in ('-2','nan','inf','abc',None):
            self.assertIsNone(parse_cost(value))

    def test_completion_requires_import_tax_and_full_active_coverage(self):
        self.assertFalse(status(None,10,10)['done'])
        self.assertFalse(status({'imposto_confirmado_em':1},10,10)['done'])
        self.assertFalse(status({'custos_importados_em':1},10,10)['done'])
        self.assertFalse(status({'custos_importados_em':1,'imposto_confirmado_em':1},10,9)['done'])
        self.assertFalse(status({'custos_importados_em':1,'imposto_confirmado_em':1},0,0)['done'])
        self.assertTrue(status({'custos_importados_em':1,'imposto_confirmado_em':1},10,10)['done'])

    def test_page_escapes_shop_name_and_has_two_required_forms(self):
        page=onboarding_page(7,'<script>x</script>',status(None,3,0),'', '')
        self.assertIn('&lt;script&gt;',page)
        self.assertNotIn('<script>x</script>',page)
        self.assertIn('/primeiro-acesso/imposto',page)
        self.assertIn('/upload_custos/7',page)
        self.assertIn('/modelo_custos/7',page)

    def test_server_side_gate_and_client_only(self):
        from pathlib import Path
        main=Path('main.py').read_text()
        gate=main[main.index('def exigir_onboarding_financeiro_cliente():'):main.index("@app.route('/primeiro-acesso')")]
        self.assertIn("session.get('tipo')!='cliente'",gate)
        self.assertIn("financeiro_status_usuario(session['usuario_id'],cid)",gate)
        self.assertIn("return redirect('/primeiro-acesso')",gate)
        self.assertIn("session['onboarding_financeiro_concluido']=cid",gate)
        self.assertIn('CREATE TABLE IF NOT EXISTS cliente_onboarding_financeiro',main)
        self.assertIn('execute_batch(cursor',main)
        self.assertIn('if not atualizacoes:',main)
        self.assertIn('imposto = float(c.get("aliquota_imposto") or 0) / 100',main)
        self.assertIn('comissao = float(c.get("comissao_pct") or 0) / 100',main)


if __name__=='__main__':
    unittest.main()
