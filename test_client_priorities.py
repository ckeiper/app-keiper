"""Client priorities rollout must be opt-in and store-scoped."""
import unittest
from decimal import Decimal as D
from client_priorities import admin_index, store_portal


class ClientPrioritiesTests(unittest.TestCase):
    def test_admin_controls_scoped_to_each_shop_and_escaped(self):
        shops=[dict(id=1,cliente='<script>Empresa</script>'),dict(id=2,cliente='Cliente B')]
        html=admin_index(shops,{2},[],csrf='<token>')
        self.assertIn('/prioridades/1/acesso',html)
        self.assertIn('/prioridades/2/acesso',html)
        self.assertIn('Portal liberado',html)
        self.assertIn('Portal não liberado',html)
        self.assertIn('&lt;script&gt;',html)
        self.assertNotIn('<script>Empresa',html)
        self.assertIn('&lt;token&gt;',html)

    def test_client_store_portal_lists_only_scoped_verified_rankings(self):
        row=dict(previous_orders=5,orders=2,previous_value=D('500'),value=D('200'),
                 previous_units=5,units=2)
        report=dict(shop={'cliente':'Minha Loja'},
                    rows=[{'listing':{'item_id':'MLB1','titulo':'Produto'}}],
                    ranking={'available':True,'rows':{'MLB1':row}},
                    signals=[{'kind':'estoque','title':'Estoque zerado','priority':'alta',
                              'label':'Produto','evidence':'0 unidades disponíveis',
                              'action':'Repor estoque'}])
        html=store_portal(report,5,client_view=True)
        self.assertIn('/diagnostico/5/MLB1',html)
        self.assertIn('Estoque zerado',html)
        self.assertNotIn('Voltar à carteira',html)
        self.assertNotIn('/diagnostico/6/',html)

    def test_access_checks_happen_before_loading_other_store_metrics(self):
        from pathlib import Path
        source=Path('main.py').read_text()
        route=source[source.index('def prioridades_loja(cid):'):source.index('@app.route("/prioridades/<int:cid>/acesso"')]
        self.assertLess(route.index('if not pode_ver_loja(cid):'),route.index('load_management(cid,'))
        self.assertLess(route.index("if not enabled or not enabled[0]['habilitado']:"),route.index('load_management(cid,'))
        self.assertIn("@admin_required\ndef acesso_prioridades_cliente",source)
        self.assertIn("secrets.compare_digest(expected,token)",source)
        self.assertIn('habilitado BOOLEAN NOT NULL DEFAULT FALSE',source)
        self.assertIn('Minhas prioridades',source)


if __name__=='__main__':
    unittest.main()
