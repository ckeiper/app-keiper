import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog_preview import page, dest
from listing_sku_variations import render
from test_listing_sku_variations import fixture, NOW
for mode in ('empty', 'groups', 'limited', 'stale', 'partial', 'unknown'):
    data = fixture()
    if mode == 'empty':
        data.update(total=0, groups=[], members=[])
    if mode == 'limited':
        data['groups'][0]['n'] = 25
        data['members'][0]['occurrences'] = 20
        data.update(page=2, pages=3)
    if mode == 'stale':
        data['members'][0]['collected_at'] = '1'
    if mode == 'unknown':
        data.update(total=0, groups=[], members=[], stats=dict(total=8, read=0, partial=0))
    if mode == 'groups':
        data['members'][0]['coverage'] = 'read'
    (dest/('sku-variations-'+mode+'.html')).write_text(page('SKUs oficiais', 7, 'Loja teste', 'anuncios', render(7, data, NOW)))
