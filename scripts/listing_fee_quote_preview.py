import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog_preview import page, dest
from test_listing_fee_quote import item, fee, requester, NOW
from listing_fee_quote import render, quote
for mode in ('blank', 'quoted', 'zero', 'unknown', 'missing'):
    value = fee()
    if mode == 'zero': value.update(sale_fee_amount=0, sale_fee_details=dict(fixed_fee=0))
    if mode == 'missing': value['sale_fee_details'] = {}
    result = quote('test-token', 123, 'MLB100', requester([dict(id=123), item(), [value]]), NOW)
    if mode == 'unknown': result = dict(state='unknown', checked_at=NOW, message='Contexto logístico ausente ou incompatível para cotação.')
    if mode == 'blank': result = None
    (dest/('fee-quote-'+mode+'.html')).write_text(page('Cotação de tarifa', 1, 'Loja fictícia', 'anuncios',
        '<p>Dados fictícios de teste.</p>'+render(1, 'MLB100', 'Anúncio fictício', 'csrf', result)))
