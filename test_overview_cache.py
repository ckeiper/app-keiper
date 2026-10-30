import unittest
from unittest.mock import Mock
from overview_cache import load_cached_overview, _cache

class OverviewCacheTests(unittest.TestCase):
    def setUp(self):
        _cache.clear()

    def test_repeat_read_hits_cache(self):
        loader=Mock(return_value={"reports":[1]})
        shop=[{"id":7,"status":"ativa"}]
        a=load_cached_overview(shop,{"periodo":"30"},None,None,loader,clock=lambda:100)
        b=load_cached_overview(shop,{"periodo":"30"},None,None,loader,clock=lambda:105)
        self.assertIs(a,b)
        loader.assert_called_once()

    def test_store_scope_never_crosses_user_boundary(self):
        loader=Mock(side_effect=[{"scope":7},{"scope":8}])
        a=load_cached_overview([{"id":7,"status":"ativa"}],{},None,None,loader,clock=lambda:100)
        b=load_cached_overview([{"id":8,"status":"ativa"}],{},None,None,loader,clock=lambda:105)
        self.assertNotEqual(a,b)
        self.assertEqual(loader.call_count,2)

    def test_filters_and_ttl_invalidate(self):
        loader=Mock(side_effect=[1,2,3])
        shop=[{"id":7,"status":"ativa"}]
        self.assertEqual(load_cached_overview(shop,{"periodo":"7"},None,None,loader,clock=lambda:100),1)
        self.assertEqual(load_cached_overview(shop,{"periodo":"30"},None,None,loader,clock=lambda:110),2)
        self.assertEqual(load_cached_overview(shop,{"periodo":"7"},None,None,loader,clock=lambda:121),3)

    def test_errors_are_never_cached(self):
        loader=Mock(side_effect=[ValueError("failed"),{"ok":True}])
        shop=[{"id":7,"status":"ativa"}]
        with self.assertRaises(ValueError):
            load_cached_overview(shop,{},None,None,loader,clock=lambda:100)
        self.assertEqual(load_cached_overview(shop,{},None,None,loader,clock=lambda:101),{"ok":True})
        self.assertEqual(loader.call_count,2)

if __name__=="__main__":
    unittest.main()
