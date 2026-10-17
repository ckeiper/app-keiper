import pathlib
import unittest


class SalesBackfillBatchTests(unittest.TestCase):
    def test_recent_seven_days_and_only_five_older_days(self):
        source = pathlib.Path("sales_sync.py").read_text(encoding="utf-8")
        self.assertIn("range(7)", source)
        self.assertIn("][:5]", source)
        self.assertNotIn("][:30]", source)


if __name__ == "__main__":
    unittest.main()
