import unittest
from unittest.mock import Mock
from listing_account_permission import normalize,render
from listing_pause_reasons import inspect,render as render_review
from test_listing_pause_reasons import response


class AccountPermissionTests(unittest.TestCase):
    def account(self,allow,codes=None):
        return dict(id=7,status=dict(list=dict(allow=allow,codes=[] if codes is None else codes)))

    def test_boolean_only_and_missing_or_invalid_structures(self):
        for value in (0,1,'false','true',None,[],{}):
            self.assertIsNone(normalize(self.account(value))['allow'])
        for account in ({},dict(status=None),dict(status=[]),dict(status=dict(list='invalid'))):
            self.assertIsNone(normalize(account)['allow'])
        self.assertIs(normalize(self.account(True))['allow'],True)
        self.assertIs(normalize(self.account(False))['allow'],False)

    def test_codes_limits_and_escaping_without_changing_permission(self):
        account=self.account(False,['<script>']+[str(i) for i in range(25)])
        result=normalize(account);self.assertTrue(result['limited']);self.assertEqual(len(result['codes']),20)
        html=render(result);self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)
        for codes in ('x',[1],['x'*201],['x']*101):
            account['status']['list']['codes']=codes;result=normalize(account)
            self.assertIs(result['allow'],False);self.assertIsNone(result['codes'])
        self.assertEqual(normalize(self.account(True,['a','a']))['codes'],['a'])

    def test_no_extra_calls_and_no_personal_account_fields(self):
        account=self.account(False,['rejected_by_regulations']);account.update(email='private@example.invalid',address=dict(street='private'),access_token='secret')
        get=Mock(side_effect=[response(account),response(dict(id='MLB1',seller_id=7,site_id='MLB',status='paused',sub_status=[]))])
        result=inspect('token',7,'MLB1',get)
        self.assertEqual(get.call_count,2);self.assertIs(result['account_permission']['allow'],False)
        html=render_review('csrf',result);self.assertIn('Não permitida na conta',html)
        self.assertIn('rejected_by_regulations',html)
        for private in ('private@example.invalid','street','secret'):
            self.assertNotIn(private,str(result));self.assertNotIn(private,html)

    def test_account_permission_does_not_certify_item_eligibility(self):
        html=render(normalize(self.account(True)))
        self.assertIn('Permitida na conta',html);self.assertIn('não garante elegibilidade',html)
        self.assertIn('Não verificada',render(normalize(self.account('true'))))

    def test_permission_survives_moderation_failure_without_retry(self):
        get=Mock(side_effect=[response(self.account(False)),response(dict(id='MLB1',seller_id=7,site_id='MLB',status='paused',sub_status=[])),response({},429)])
        result=inspect('token',7,'MLB1',get,include_moderation=True)
        self.assertEqual(get.call_count,3);self.assertIs(result['account_permission']['allow'],False)
        self.assertEqual(result['moderation']['state'],'unknown')

    def test_wrong_ownership_does_not_expose_permission(self):
        get=Mock(side_effect=[response(self.account(False)),response(dict(id='MLB1',seller_id=8,site_id='MLB'))])
        result=inspect('token',7,'MLB1',get)
        self.assertNotIn('account_permission',result)
        self.assertIn('Não verificada nesta consulta',render_review('csrf',result))
