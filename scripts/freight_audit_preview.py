"""Synthetic freight audit screens through the real store shell. No production data."""
import sys
from pathlib import Path
from datetime import datetime,date,timedelta,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from freight_audit_view import render_page, reporting_today
from freight_reconciliation import render_sales_reconciliation,empty_day
from ledger_arithmetic import empty,accumulate
from freight_sales_compare import compare_sales_rows,render_sales_comparison
from test_freight_differences import review

financial=empty(True)
accumulate(financial,1000,160,840,'Venda')
data=dict(rows=120,shipping_rows=70,invalid_shipping_rows=0,inconsistent_shipping_rows=0,
          repeated_operation_rows=20,missing_operation_rows=0,absent_shipping_rows=30,
          invalid_date_rows=0,gross_shipping_total='1800.00',shipping_discount_total='600.00',
          seller_shipping_total='1200.00',period_start='2026-09-17',period_end='2026-10-17',financial=financial)
data['freight_review']=review()
reports=[dict(id=1,importado_em=datetime(2026,10,27,14,tzinfo=timezone.utc),resumo=data)]
today=reporting_today()
days=[dict(dia=today-timedelta(days=i),resumo=dict(empty_day(),seller_shipping_total='40.00')) for i in range(12)]
for mode in ('empty','saved','result','client','duplicate'):
    result=render_sales_reconciliation(data)+render_sales_comparison(compare_sales_rows([],{}, {},[],[])) if mode=='result' else ''
    if mode in ('result','duplicate'):result+="<div class='aviso' role='status'>"+('Indicadores importados.' if mode=='result' else 'Este arquivo já foi importado nesta loja.')+'</div>'
    html=render_page('synthetic-csrf',mode!='client','Loja de demonstração',reports if mode not in ('empty','client') else [],days if mode=='saved' else [],result,report_id=1 if mode not in ('empty','client') else None,cid=1)
    (dest/('freight-audit-'+mode+'.html')).write_text(page('Auditoria de Frete',1,'Loja de demonstração','auditoria_frete','<p>Dados fictícios de teste.</p>'+html),encoding='utf-8')
