"""Actual store shell with synthetic geography data, no API or production reads."""
from datetime import date
from catalog_preview import page,dest
from sales_geography import summarize
from sales_geography_view import render
from test_sales_geography import row
start=end=date(2026,10,28)
for name,rows,coverage in [('ready',[row(),row('2',uf='RJ',total=30),row('3',uf=None,total=70)],{start.isoformat()}),('empty',[],set())]:
    report=summarize(rows,start,end,coverage)
    (dest/('sales-geography-'+name+'.html')).write_text(page('Mapa de vendas por estado',7,'Loja de teste','vendas',render(7,{},start,end,report)),encoding='utf-8')
print('Synthetic geographic sales previews rendered.')
