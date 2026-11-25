import unittest
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

from listing_pause_reasons import inspect as inspect_reactivation
from listing_moderation_history import inspect, render


def response(payload):
    return Mock(status_code=200, json=lambda: payload)


def infraction(**changes):
    return dict(dict(id='10', user_id='7', related_item_id='MLB1',element_id='MLB1',
                     element_type='ITM',site_id='MLB',filter_subgroup='DESC',
                     date_created='2026-11-25',reason='Confira o preço.',remedy='Corrija e reative.'), **changes)


def payload(rows=None, total=21):
    return dict(infractions=[infraction()] if rows is None else rows,
                paging=dict(offset=0,limit=20,total=total))


class ModerationHistoryTests(unittest.TestCase):
    def test_request_is_scoped_and_pagination_is_rendered(self):
        get = Mock(return_value=response(payload([infraction() for _ in range(20)])))
        result = inspect('token',7,'MLB1',get)
        url = urlsplit(get.call_args.args[0])
        self.assertEqual(url.path,'/moderations/infractions/7')
        self.assertEqual(parse_qs(url.query)['related_item_id'],['MLB1'])
        self.assertEqual(parse_qs(url.query)['limit'],['20'])
        self.assertFalse(get.call_args.kwargs['allow_redirects'])
        output = render('csrf',result)
        self.assertIn('Próxima página',output)
        self.assertIn('value="20"',output)
        self.assertIn('Confira o preço.',output)

    def test_wrong_owner_or_listing_is_not_shown(self):
        get = Mock(return_value=response(payload([infraction(user_id='8'),infraction(related_item_id='MLB2')])))
        result = inspect('token',7,'MLB1',get)
        self.assertEqual(result['rows'],[])
        self.assertTrue(result['partial'])

    def test_invalid_pagination_is_not_an_empty_history(self):
        get = Mock(return_value=response(dict(infractions=[],paging={'total':0,'limit':20,'offset':'0'})))
        self.assertEqual(inspect('token',7,'MLB1',get)['state'],'unknown')

    def test_api_failure_preserves_status_and_authorization_happens_first(self):
        account = response({'id':7})
        item = response(dict(id='MLB1',seller_id=7,site_id='MLB',status='paused',sub_status=[]))
        get = Mock(side_effect=[account,item,Mock(status_code=403)])
        result = inspect_reactivation('token',7,'MLB1',get,history_offset=0)
        self.assertEqual(result['state'],'read')
        self.assertEqual(result['history']['state'],'unknown')
        get = Mock(return_value=response({'id':8}))
        self.assertEqual(inspect_reactivation('token',7,'MLB1',get,history_offset=0)['state'],'unknown')
        self.assertEqual(get.call_count,1)

    def test_content_is_escaped_and_empty_result_is_explicit(self):
        result = inspect('token',7,'MLB1',Mock(return_value=response(payload([infraction(reason='<script>x</script>')],1))))
        output = render('csrf',result)
        self.assertIn('&lt;script&gt;',output)
        self.assertNotIn('<script>',output)
        result = inspect('token',7,'MLB1',Mock(return_value=response(payload([],0))))
        self.assertIn('Nenhuma infração',render('csrf',result))
