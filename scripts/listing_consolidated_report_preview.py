import sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from listing_consolidated_report import html_report,pdf_report
from test_listing_consolidated_report import fixture
out=Path('visual-qa');out.mkdir(exist_ok=True)
for days in (7,30):
    d=fixture(days)
    (out/('listing-consolidated-'+str(days)+'.html')).write_text(html_report(7,'MLB1',d,int(time.time())))
    (out/('listing-consolidated-'+str(days)+'.pdf')).write_bytes(pdf_report(7,'MLB1',d,int(time.time())))
print('Synthetic consolidated HTML and real PDF previews generated.')
