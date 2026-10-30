import contextlib
import datetime
import html
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from promo_history import render_history,number
from test_listing_details import main_function


class PromotionHistoryTests(unittest.TestCase):
    def test_no_rows_and_counts_are_limited_to_displayed_window(self):
        self.assertIn('Nenhuma participação',render_history([],7))
        output=render_history([dict(status='confirmed')]*150,7)
        self.assertEqual(output.count('<tr>'),101)
        self.assertIn('>100</div>',output)
        self.assertIn('Últimas 100 solicitações',output)
        self.assertIn('não representa lucro líquido',output)

    def test_escaping_path_encoding_and_brazilian_dates(self):
        output=render_history([dict(titulo='<script>x</script>',item_id='MLB123456789',
            promocao_id='a/b?x="',status='uncertain',preco=100,margem_pct=-3,
            criado_em=1792796400)],42)
        self.assertNotIn('<script>',output)
        self.assertIn('&lt;script&gt;',output)
        self.assertIn('a%2Fb%3Fx%3D%22/MLB123456789',output)
        self.assertIn('Brasília',output)
        self.assertIn('R$ 100,00',output)
        self.assertIn('-3,00%',output)
        self.assertNotIn('<form',output)

    def test_invalid_financial_values_stay_unavailable_independently(self):
        for value in [None,True,'NaN','Infinity','x','1e100']:
            self.assertEqual(number(value), '—')
        self.assertEqual(number(-1,money=True),'—')
        output=render_history([dict(preco=100,margem_pct=None,criado_em='invalid')],1)
        self.assertIn('R$ 100,00',output)
        self.assertNotIn('nan',output)
        self.assertNotIn('None',output)

    def test_real_page_scopes_history_read_and_does_not_contact_marketplace(self):
        query=Mock(side_effect=[
            [dict(cliente='Loja',mc_meta_pct=20)],[],
            [dict(item_id='MLB123456789',promocao_id='P-MLB123456',status='confirmed',preco=80,margem_pct=10)],[]])
        env=dict(pode_ver_loja=lambda cid:True,banco=lambda:contextlib.nullcontext(None),
            consultar=query,datetime=datetime,pagina=lambda *args:args[-1],
            pagina_loja=lambda *args:args[-1],ultima_atualizacao=lambda cid:None,
            barra_atualizar=lambda *args:'',request=SimpleNamespace(args={}),esc=html.escape)
        result=main_function('promocoes',env)(42)
        self.assertIn('Histórico de participações',result)
        history_call=query.call_args_list[2]
        self.assertIn('WHERE h.conexao_id=%s',history_call.args[1])
        self.assertIn('a.conexao_id=h.conexao_id',history_call.args[1])
        self.assertIn('LIMIT 100',history_call.args[1])
        self.assertEqual(history_call.args[2],(42,))
        query.reset_mock();env['pode_ver_loja']=lambda cid:False
        self.assertIn('Acesso restrito',main_function('promocoes',env)(43))
        query.assert_not_called()
