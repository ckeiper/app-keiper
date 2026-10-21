import datetime as dt
import io
import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs,urlparse
from copas_visits_store import _fetch_visits,HISTORY_DAYS

TODAY=dt.date(2026,10,21)

class VisitsHistoryTests(unittest.TestCase):
    def fetch(self,records,item_id='MLB1'):
        payload=json.dumps(dict(item_id=item_id,results=records))
        with patch('urllib.request.urlopen',return_value=io.StringIO(payload)) as api:
            result=_fetch_visits('MLB1','fake',TODAY)
            url=api.call_args.args[0].full_url
        return result,parse_qs(urlparse(url).query)

    def test_requests_fourteen_completed_days_and_preserves_real_zero(self):
        records=[dict(date=(TODAY-dt.timedelta(days=n)).isoformat()+'T03:00:00Z',total=0 if n==14 else n) for n in range(1,15)]
        result,params=self.fetch(records)
        self.assertEqual(params,dict(last=['14'],unit=['day'],ending=['2026-10-21']))
        self.assertEqual(len(result[1]),HISTORY_DAYS)
        self.assertIsNone(result[2])
        self.assertIn((dt.date(2026,10,7),0),result[1])

    def test_today_and_older_days_never_enter_completed_window(self):
        result,_=self.fetch([dict(date=d,total=1) for d in ('2026-10-06','2026-10-07','2026-10-20','2026-10-21')])
        self.assertEqual([d.isoformat() for d,v in result[1]],['2026-10-07','2026-10-20'])

    def test_missing_days_stay_missing(self):
        result,_=self.fetch([dict(date='2026-10-15',total=5)])
        self.assertEqual(len(result[1]),1)

    def test_duplicates_invalid_counts_or_wrong_item_reject_whole_response(self):
        row=dict(date='2026-10-15',total=5)
        result,_=self.fetch([row,row]);self.assertIsNotNone(result[2]);self.assertEqual(result[1],[])
        for count in (None,-1,True,1.5,'5'):
            result,_=self.fetch([dict(row,total=count)])
            self.assertIsNotNone(result[2]);self.assertEqual(result[1],[])
        result,_=self.fetch([row],item_id='MLBOTHER');self.assertIsNotNone(result[2])

if __name__=='__main__':
    unittest.main()
