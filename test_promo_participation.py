"""Guardrails for the first real ML promotion write flow."""
import unittest
from decimal import Decimal
from pathlib import Path
from promo_participation import (
    parse_price,find_deal,check_candidate,margin_pct,safe_item,safe_promo,
    is_participating,candidate_table,confirmation_form
)


class DealParticipationTests(unittest.TestCase):
    def test_price_and_identifiers(self):
        self.assertEqual(parse_price('89,90'),Decimal('89.90'))
        for value in ('0','-2','nan','inf','abc','100000001','2.999',None):
            with self.subTest(value=value),self.assertRaises(ValueError):
                parse_price(value)
        self.assertEqual(safe_item('MLB123456789'),'MLB123456789')
        self.assertEqual(safe_promo('P-MLB123456'),'P-MLB123456')
        for item in ('MLB1','https://evil.test','MLB12345/../../secret'):
            with self.assertRaises(ValueError):
                safe_item(item)

    def test_deal_candidate_status_and_limits(self):
        rows=[{'id':'P-MLB123456','type':'DEAL','status':'candidate',
               'original_price':100,'min_discounted_price':70,
               'max_discounted_price':90}]
        row=find_deal(rows,'P-MLB123456')
        check_candidate(row,Decimal('80'))
        for price in ('65','95','100'):
            with self.subTest(price=price),self.assertRaises(ValueError):
                check_candidate(row,Decimal(price))
        with self.assertRaises(ValueError):
            check_candidate({**row,'status':'started'},Decimal('80'))
        self.assertFalse(is_participating(row))
        self.assertTrue(is_participating({**row,'status':'pending'}))
        self.assertIsNone(find_deal([{'id':'P-MLB123456','type':'LIGHTNING'}],'P-MLB123456'))

    def test_financial_floor(self):
        self.assertEqual(margin_pct('100','60','8','12'),Decimal('20.00'))
        self.assertLess(margin_pct('80','60','8','12'),Decimal('20'))
        with self.assertRaises(ValueError):
            margin_pct(100,-2,8,12)

    def test_candidate_table_escapes_untrusted_titles(self):
        html=candidate_table(4,'P-MLB123456',
            [{'id':'MLB123456789','status':'candidate','original_price':100,
              'suggested_discounted_price':80}],
            {'MLB123456789':'<script>alert(1)</script>'})
        self.assertNotIn('<script>',html)
        self.assertIn('&lt;script&gt;',html)
        self.assertIn('/promocoes/participar/4/P-MLB123456/MLB123456789',html)
        form=confirmation_form(4,'P-MLB123456','MLB123456789',Decimal('80'),20,15,100)
        self.assertIn('name=\'confirmar\'',form)
        self.assertIn('type=\'hidden\' name=\'deal_price\'',form)

    def test_server_side_guards_and_audit(self):
        main=Path('main.py').read_text()
        self.assertIn('CREATE TABLE IF NOT EXISTS promocoes_adesoes',main)
        self.assertIn("if not pode_ver_loja(cid):",main)
        self.assertIn("if request.form.get('confirmar')!='sim':",main)
        self.assertIn('validar_adesao_deal(cid,pid,item_id,request.form.get(\'deal_price\'))',main)
        self.assertIn("ON CONFLICT DO NOTHING",main)
        self.assertIn("if not reserved:",main)
        self.assertIn("json={'promotion_id':pid,'promotion_type':'DEAL','deal_price':float(price)}",main)
        self.assertIn("is_participating(find_deal(fresh,pid))",main)
        self.assertIn("state='uncertain'",main)
        self.assertIn("if mc < float(shop['mc_meta_pct']):",main)
        self.assertIn('Ver candidatos e participar',main)


if __name__=='__main__':
    unittest.main()
