"""OAuth route regression tests; no production database or ML calls."""
import ast
from contextlib import nullcontext
from pathlib import Path
import secrets
import time
import unittest
from unittest.mock import Mock
from urllib.parse import urlencode, urlparse, parse_qs

import requests
from flask import Flask, request, session, redirect


class StoreConnectTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(Path(__file__).with_name("main.py").read_text(encoding="utf-8"))
        routes = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                  and n.name in ("conectar", "callback_ml")]
        app = Flask(__name__)
        app.secret_key = "oauth-route-test-only"
        self.http = Mock()
        self.http.RequestException = requests.RequestException
        self.http.post.return_value = Mock(status_code=200, json=lambda: {
            "access_token": "secret-access", "refresh_token": "secret-refresh",
            "expires_in": 3600, "user_id": 123})
        self.http.get.return_value = Mock(status_code=200,
                                         json=lambda: {"id": 123, "nickname": "Cliente"})
        self.write = Mock(return_value=Mock(fetchone=lambda: (9,)))
        self.read = Mock(return_value=[])
        self.env = dict(app=app, request=request, session=session, redirect=redirect,
                        secrets=secrets, time=time, urlencode=urlencode,
                        requests=self.http, CLIENT_ID="123", CLIENT_SECRET="secret",
                        REDIRECT_URI="https://example.org/oauth?x=1&y=2",
                        AUTH_URL="https://auth.mercadolibre.com.br/authorization",
                        TOKEN_URL="https://api.mercadolibre.com/oauth/token",
                        API="https://api.mercadolibre.com",
                        pagina=lambda title, body: body,
                        banco=lambda: nullcontext(object()),
                        consultar=self.read, executar=self.write,
                        pode_ver_loja=lambda cid: True)
        exec(compile(ast.Module(body=routes, type_ignores=[]), "main.py", "exec"), self.env)
        self.client = app.test_client()

    def start(self):
        response = self.client.get("/conectar")
        self.assertEqual(response.status_code, 302)
        args = parse_qs(urlparse(response.location).query)
        self.assertEqual(args["redirect_uri"], [self.env["REDIRECT_URI"]])
        return args["state"][0]

    def finish(self, state, path="/oauth", **args):
        return self.client.get(path, query_string={"state": state, "code": "test-code", **args})

    def test_public_connect_and_success_without_panel_access(self):
        response = self.finish(self.start())
        self.assertEqual(response.status_code, 200)
        self.assertIn("Loja conectada com sucesso", response.text)
        self.assertNotIn("secret-access", response.text)
        self.write.assert_called_once()
        with self.client.session_transaction() as sess:
            self.assertNotIn("usuario_id", sess)
            self.assertNotIn("conexao_id", sess)

    def test_callback_alias_and_existing_connection(self):
        self.read.return_value = [{"id": 9}]
        self.assertEqual(self.finish(self.start(), "/callback").status_code, 200)
        self.assertIn("UPDATE conexoes", self.write.call_args.args[1])

    def test_authenticated_authorized_user_keeps_panel_redirect(self):
        with self.client.session_transaction() as sess:
            sess["usuario_id"] = 7
        response = self.finish(self.start())
        self.assertEqual(response.location, "/painel/9")

    def test_authenticated_other_store_never_gets_access(self):
        self.env["pode_ver_loja"] = lambda cid: False
        with self.client.session_transaction() as sess:
            sess.update(usuario_id=7, conexao_id=22)
        self.assertEqual(self.finish(self.start()).status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess["conexao_id"], 22)

    def test_missing_wrong_unicode_expired_and_other_browser_state(self):
        state = self.start()
        for invalid in ("", "wrong", "inválido"):
            self.assertEqual(self.finish(invalid).status_code, 400)
        other = self.env["app"].test_client()
        self.assertEqual(other.get("/oauth", query_string={"state": state, "code": "x"}).status_code, 400)
        with self.client.session_transaction() as sess:
            pending = dict(sess["ml_oauth"])
            pending["created_at"] -= 901
            sess["ml_oauth"] = pending
        self.assertEqual(self.finish(state).status_code, 400)
        self.http.post.assert_not_called()
        self.write.assert_not_called()

    def test_session_identity_change_rejected(self):
        state = self.start()
        with self.client.session_transaction() as sess:
            sess["usuario_id"] = 8
        self.assertEqual(self.finish(state).status_code, 400)
        self.http.post.assert_not_called()

    def test_replay_rejected(self):
        state = self.start()
        self.finish(state)
        self.assertEqual(self.finish(state).status_code, 400)
        self.http.post.assert_called_once()

    def test_user_cancels(self):
        state = self.start()
        response = self.client.get("/oauth", query_string={"state": state, "error": "access_denied"})
        self.assertIn("Autorização não concluída", response.text)
        self.http.post.assert_not_called()

    def test_provider_failures_never_write_or_leak(self):
        failures = [
            (self.http.post, Mock(status_code=400, json=lambda: {"error": "secret-provider"})),
            (self.http.get, Mock(status_code=503, json=lambda: {})),
            (self.http.get, Mock(status_code=200, json=lambda: {"id": 999})),
        ]
        for target, result in failures:
            original = target.return_value
            target.return_value = result
            response = self.finish(self.start())
            self.assertEqual(response.status_code, 502)
            self.assertNotIn("secret", response.text)
            self.write.assert_not_called()
            target.return_value = original
        self.http.post.side_effect = requests.Timeout("secret-timeout")
        self.assertEqual(self.finish(self.start()).status_code, 502)
        self.write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
