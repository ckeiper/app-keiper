import unittest

from freight_import import (
    identify_reconciliation_columns,
    render_reconciliation_column_hints,
)


class FreightColumnDiagnosticsTests(unittest.TestCase):
    def test_detects_specific_headers_below_first_row(self):
        sheets = [{"name": "Conciliação", "sample": [
            ["Relatório de pagamentos"],
            ["Número de venda", "Número de envio", "Tarifa de envio",
             "Valor da transação", "Tipo de operação"],
        ]}]
        candidates = identify_reconciliation_columns(sheets)[0]["candidates"]
        kinds = {item["kind"] for item in candidates}
        self.assertEqual(kinds, {"pedido", "envio", "frete", "valor", "tipo"})
        self.assertTrue(all(item["row"] == 2 for item in candidates))

    def test_generic_value_column_is_not_financially_mapped(self):
        sheets = [{"name": "Dados", "sample": [["Valor", "Amount", "Produto"]]}]
        self.assertEqual(identify_reconciliation_columns(sheets)[0]["candidates"], [])

    def test_escapes_uploaded_cell_values(self):
        sheets = [{"name": "<script>", "sample": [
            ["Número de venda <img src=x onerror=alert(1)>"]
        ]}]
        rendered = render_reconciliation_column_hints(sheets)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("<img", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("&lt;img", rendered)


if __name__ == "__main__":
    unittest.main()
