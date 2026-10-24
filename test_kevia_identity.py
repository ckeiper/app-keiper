import unittest
from html.parser import HTMLParser
from keiper_ai_view import render
from kyra_central import render_central
from kyra_history import render_history


class Headings(HTMLParser):
    def __init__(self):
        super().__init__();self.active=False;self.values=[]
    def handle_starttag(self,tag,attrs):
        if tag=='h2':self.active=True;self.values.append('')
    def handle_data(self,text):
        if self.active:self.values[-1]+=text
    def handle_endtag(self,tag):
        if tag=='h2':self.active=False


class KeviaIdentityTests(unittest.TestCase):
    def test_saved_analysis_views_share_current_public_identity(self):
        for output in [render({},cid=42),render_central([]),render_history([])]:
            with self.subTest(view=output[:60]):
                self.assertIn('KEVIA',output)
                self.assertNotIn('KYRA',output)
        headings=Headings();headings.feed(render({},cid=42))
        self.assertIn('KEVIA',headings.values)
        self.assertNotIn('KYRA',headings.values)
        # Stable links preserve existing bookmarks and stored history.
        self.assertIn('/ads/42',render({},cid=42))
