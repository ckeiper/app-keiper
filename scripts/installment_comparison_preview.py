import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog_preview import page, dest
from test_installment_comparison import form
from installment_comparison import render, simulate
for mode in ('blank', 'ready', 'negative', 'error', 'three'):
    values = form()
    if mode == 'negative': values['product'] = '200'
    if mode == 'three':
        for key in ('label', 'source', 'source_date', 'installments', 'gross', 'fee', 'financing'):
            values[key+'_2'] = values[key+'_1']
        values['source_2'] = 'Referência '+('muito extensa ' * 20)
    result = simulate(values) if mode in ('ready', 'negative', 'three') else None
    if mode == 'blank': values = {}
    error = 'Financiamento não pode exceder a tarifa total.' if mode == 'error' else ''
    (dest/('installments-'+mode+'.html')).write_text(page('Parcelamento', 1, 'Loja fictícia', 'anuncios',
        '<p>Dados fictícios de teste.</p>'+render(1, 'MLB100', 'Anúncio fictício', 'token', values, result, error)))
