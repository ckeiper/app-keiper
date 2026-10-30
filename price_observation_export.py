"""Tenant-scoped export of sampled offer evidence, never inferred prices."""
import csv
from datetime import datetime,timedelta
from io import StringIO
import re
from flask import request,session,Response
from offer_history import BR,confirmed_price
from sales_metrics import reporting_today


def csv_text(item,rows):
    out=StringIO(newline='');writer=csv.writer(out,delimiter=';')
    writer.writerow(['anuncio','coleta_brasilia','preco_final_confirmado_brl','validacao'])
    for row in rows:
        price=confirmed_price(row)
        writer.writerow([item,datetime.fromtimestamp(row['observed_at'],BR).strftime('%d/%m/%Y %H:%M:%S'),
                         format(price,'.2f').replace('.',',') if price is not None else '',
                         'confirmado' if price is not None else 'nao_verificado'])
    return '\ufeff'+out.getvalue()


def register_export(app,login_required,can_view,bank,query,execute,today=reporting_today):
    @app.route('/anuncios/<int:cid>/<item_id>/precos-observados.csv',methods=['GET'])
    @login_required
    def listing_price_observation_export(cid,item_id):
        if session.get('tipo')!='admin' or not can_view(cid):return 'Acesso restrito',403
        if not re.fullmatch(r'MLB[0-9]{1,20}',item_id):return 'Anúncio não encontrado',404
        try:days=int(request.args.get('dias','7'))
        except ValueError:return 'Período inválido',400
        if days not in (7,30):return 'Período inválido',400
        end=today();start=int(datetime.combine(end-timedelta(days=days*2-1),datetime.min.time(),BR).timestamp())
        stop=min(int(datetime.combine(end+timedelta(days=1),datetime.min.time(),BR).timestamp()),int(__import__('time').time())+1)
        with bank() as conn:
            execute(conn,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            found=query(conn,'SELECT item_id FROM anuncios WHERE conexao_id=%s AND item_id=%s',(cid,item_id))
            if not found:return 'Anúncio não encontrado nesta loja.',404
            rows=query(conn,'''SELECT observed_at,price,confirmed FROM listing_offer_observations
                WHERE conexao_id=%s AND item_id=%s AND observed_at>=%s AND observed_at<%s
                ORDER BY observed_at LIMIT 5001''',(cid,item_id,start,stop))
        if len(rows)>5000:return 'Mais de 5.000 leituras: reduza o período; nenhum arquivo parcial foi gerado.',413
        response=Response(csv_text(item_id,rows),content_type='text/csv; charset=utf-8')
        response.headers['Content-Disposition']=f'attachment; filename="{item_id}-precos-{days}dias-comparados.csv"'
        response.headers['Cache-Control']='no-store';response.headers['X-Content-Type-Options']='nosniff'
        return response
