"""Synthetic sales layout; never reads production data."""
import contextlib
from datetime import date, timedelta
from catalog_preview import page, dest
from sales_view import render_sales
from test_sales import row

today=date.today()
days=[(today-timedelta(days=n)).isoformat() for n in range(14)]
def query(conn, sql, params):
    if 'COUNT(*)' in sql:
        return [{'n':0}]
    if 'vendas_cobertura' in sql:
        return [{'dia':day,'atualizado_em':1} for day in days]
    return [row(str(n), criado_em=day+'T12:00:00-03:00') for n,day in enumerate(days)]
body="<div class='barra-topo'><h2>Vendas e Margem de Contribuição</h2></div>"
body+=render_sales(1,{'periodo':'7'},lambda:contextlib.nullcontext(None),query)
body+="<div class='card'><h2>Vendas</h2><div class='sub'>Informações sintéticas.</div><div style='overflow-x:auto'><table><thead><tr><th>Pedido</th><th>Receita</th></tr></thead><tbody><tr><td>123</td><td>R$ 120,00</td></tr></tbody></table></div></div>"
(dest/'sales-theme.html').write_text(page('Vendas',1,'Loja de demonstração','vendas',body),encoding='utf-8')
