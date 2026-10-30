"""Read-only availability comparison using existing catalogue and sales sources."""
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from html import escape
from zoneinfo import ZoneInfo

from listing_priority_sources import listing_signals


def cells(listings, ranking, ids, days, now=None):
    counts = Counter(str(row['item_id']) for row in listings)
    unique = [row for row in listings if counts[str(row['item_id'])] == 1]
    signals = listing_signals(unique, ranking, days, now=now)
    rows = {str(row['item_id']): row for row in unique}
    result = {}
    for item in ids:
        signal = signals.get(item, {})
        values = ['Indisponível'] * 4
        if signal.get('stock_verified'):
            stock = signal['stock']
            values[0] = str(int(stock)) + ' unidades'
            stamp = int(rows[item]['atualizado_em'])
            values[1] = datetime.fromtimestamp(stamp, timezone.utc).astimezone(
                ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M') + ' · Brasília'
            if 'daily_units' in signal:
                units = signal['velocity_units']
                values[2] = str(int(units)) + ' unidades em ' + str(days) + ' dias encerrados'
                coverage = stock * days / units
                shown = coverage.quantize(Decimal('.01'), rounding=ROUND_DOWN)
                values[3] = ('<0,01' if 0 < coverage < Decimal('.01') else str(shown).replace('.', ',')) + ' dias'
            else:
                values[2] = 'Sem vendas positivas verificadas'
        result[item] = values
    return result


def render(listings, ranking, ids, names, days, now=None):
    values = cells(listings, ranking, ids, days, now=now)
    esc = lambda value: escape(str(value), quote=True)
    out = '<details class="lc-daily lc-stock"><summary>Comparar estoque e cobertura observada</summary><p>Estoque do último registro válido com até seis horas, comparado às unidades vendidas no período atual acima. O estoque é uma leitura atual, não o estoque histórico dos dois períodos.</p><div class="lc-scroll lc-stock-scroll" tabindex="0" role="region" aria-label="Estoque e cobertura observada dos anúncios"><table><thead><tr><th scope="col">Disponibilidade atual</th>'
    for item in ids:
        out += '<th scope="col">' + esc(names.get(item, item)) + '<small>' + esc(item) + '</small></th>'
    out += '</tr></thead><tbody>'
    for index, label in enumerate(['Estoque registrado', 'Leitura do catálogo', 'Base de vendas observada', 'Estoque ÷ média diária de unidades']):
        out += '<tr><th scope="row">' + label + '</th>'
        for item in ids:
            out += '<td>' + esc(values[item][index]) + '</td>'
        out += '</tr>'
    return out + '</tbody></table></div><p>Cobertura descritiva, sem previsão de demanda ou data garantida de ruptura. Estoque zero confirmado é zero; dado ausente, antigo, futuro ou inválido fica indisponível. Sem vendas positivas verificadas, não há divisão nem cobertura infinita. Quantidade do anúncio não comprova saldo específico do Full ou disponibilidade de cada variação.</p></details>'
