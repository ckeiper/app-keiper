"""Regression tests for partial Mercado Livre shipment refreshes.

Extracts the production function without importing the Flask app or opening
production connections. SQL is captured; no external API or database is used.
"""
import ast
import contextlib
from pathlib import Path
import unittest


def shipment_sync(api_get, execute, errors):
    tree = ast.parse(Path(__file__).with_name("main.py").read_text(encoding="utf-8"))
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "puxar_envios")
    namespace = {
        "api_get": api_get,
        "registrar_erro": lambda *args: errors.append(args),
        "banco": lambda: contextlib.nullcontext(None),
        "executar": execute,
        "time": __import__("time"),
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "main.py", "exec"), namespace)
    return namespace["puxar_envios"]


class ShipmentSyncRegressionTests(unittest.TestCase):
    def test_partial_refresh_upserts_without_deleting_history(self):
        statements = []
        errors = []
        paths = []

        def api(token, path, params=None):
            paths.append(path)
            if path == "/orders/search":
                return {"results": [
                    {"id": 101, "shipping": {"id": 501}},
                    {"id": 102, "shipping": {"id": 502}},
                ]}, None
            return {"status": "ready", "tracking_number": "TRACK",
                    "date_created": "2026-10-17",
                    "cost_to_seller": None}, None

        def execute(conn, sql, params):
            statements.append((sql, params))

        success = shipment_sync(api, execute, errors)(4, "token", 123)
        self.assertTrue(success)
        self.assertEqual(paths, ["/orders/search", "/shipments/501", "/shipments/502"])
        self.assertEqual(len(statements), 2)
        self.assertFalse(any("DELETE FROM envios" in sql.upper()
                             for sql, _ in statements))
        self.assertTrue(all("ON CONFLICT (conexao_id, envio_id)" in sql
                            for sql, _ in statements))
        self.assertTrue(all("COALESCE(EXCLUDED.custo_frete, envios.custo_frete)" in sql
                            for sql, _ in statements))
        self.assertEqual([params[1] for _, params in statements], ["501", "502"])

    def test_failure_does_not_remove_other_shipments(self):
        statements, errors = [], []
        def api(token, path, params=None):
            if path == "/orders/search":
                return {"results": [{"id": 101, "shipping": {"id": 501}},
                                    {"id": 102, "shipping": {"id": 502}}]}, None
            if path == "/shipments/501":
                return None, "HTTP 503"
            return {"status": "ready", "cost_to_seller": 12.0}, None
        result = shipment_sync(api, lambda conn, sql, params: statements.append(sql),
                               errors)(4, "token", 123)
        self.assertFalse(result)
        self.assertEqual(len(statements), 1)
        self.assertTrue(errors)
        self.assertFalse(any("DELETE FROM envios" in sql.upper() for sql in statements))

    def test_limits_refresh_to_twenty_unique_shipments(self):
        statements, paths, errors = [], [], []
        def api(token, path, params=None):
            paths.append(path)
            if path == "/orders/search":
                return {"results": [{"id": i, "shipping": {"id": i}}
                                    for i in range(1, 60)]}, None
            return {"status": "ready"}, None
        result = shipment_sync(api, lambda conn, sql, params: statements.append(params),
                               errors)(4, "token", 123)
        self.assertTrue(result)
        self.assertEqual(len(statements), 20)
        self.assertEqual(len(paths), 21)


if __name__ == "__main__":
    unittest.main()
