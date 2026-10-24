"""Admin-only profitability evidence with global CSRF and immutable history."""
import re
import secrets
from datetime import timedelta
from urllib.parse import urlencode
from flask import request, session, redirect
from sales_metrics import reporting_today
from profitability_store import period, load_pair, validate, result_for, save
from profitability_comparison import compare
from profitability_comparison_view import render_comparison
from profitability_view import render


def register_profitability(app, login_required, can_view, bank, query, execute, shop_page, today=reporting_today):
    @app.route('/anuncios/<int:cid>/<item_id>/rentabilidade', methods=['GET','POST'])
    @login_required
    def listing_profitability(cid, item_id):
        if session.get('tipo') != 'admin' or not can_view(cid):
            return 'Acesso restrito ao administrador.', 403
        if not re.fullmatch(r'MLB[0-9]{1,20}', item_id):
            return 'Anúncio não encontrado.', 404
        try:
            day = today()
            start, end = period(request.args, day)
        except ValueError as exc:
            return str(exc), 400
        # Shared security middleware verifies _csrf before any POST write.
        csrf = session.setdefault('_csrf', secrets.token_urlsafe(32))
        message, status = '', 200
        with bank() as conn:
            if request.method == 'GET':
                # Sales, item mappings and both cost versions must share the
                # same database snapshot while collectors update in parallel.
                execute(conn, 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            shops = query(conn, '''SELECT c.cliente,a.titulo FROM conexoes c JOIN anuncios a
                ON a.conexao_id=c.id WHERE c.id=%s AND a.item_id=%s''', (cid,item_id))
            if not shops:
                return 'Anúncio não encontrado nesta loja.', 404
            pair = load_pair(conn,query,cid,item_id,start,end,day-timedelta(days=366))
            summary = pair['current']
            if request.method == 'POST':
                try:
                    costs,sources,key = validate(request.form)
                    if request.form.get('basis') != summary['fingerprint']:
                        raise ValueError('As vendas mudaram. Recarregue a página e confira os custos.')
                    save(conn,execute,cid,item_id,start,end,summary,costs,sources,session['usuario_id'],key)
                    return redirect(request.path+'?'+urlencode({'inicio':start.isoformat(),'fim':end.isoformat(),'salvo':'1'}),code=303)
                except ValueError as exc:
                    message,status = str(exc),400
            records = query(conn, '''SELECT * FROM listing_profitability_records
                WHERE conexao_id=%s AND item_id=%s AND inicio=%s AND fim=%s
                ORDER BY id DESC LIMIT 1''', (cid,item_id,start,end))
            prior_records = [] if pair['previous'].get('outside_window') else query(conn, """SELECT * FROM listing_profitability_records
                WHERE conexao_id=%s AND item_id=%s AND inicio=%s AND fim=%s
                ORDER BY id DESC LIMIT 1""", (cid,item_id,pair['previous_start'],pair['previous_end']))
            history = query(conn, '''SELECT id,inicio,fim,created_at FROM listing_profitability_records
                WHERE conexao_id=%s AND item_id=%s ORDER BY id DESC LIMIT 20''', (cid,item_id))
        record = records[0] if records else None
        result = result_for(summary, record)
        prior_record = prior_records[0] if prior_records else None
        comparison = compare(summary,pair['previous'],record,prior_record)
        comparison_html = render_comparison(comparison,start,end,pair['previous_start'],
                                            pair['previous_end'],record,prior_record,
                                            previous_accessible=not pair['previous'].get('outside_window'))
        if request.args.get('salvo') == '1' and not message:
            message = 'Nova versão registrada. Histórico preservado.'
        body = render(cid,item_id,shops[0]['titulo'],start,end,summary,result,record,history,
                      csrf,secrets.token_urlsafe(24),request.form if status==400 else None,message,comparison_html=comparison_html)
        return shop_page('Rentabilidade por anúncio',cid,shops[0]['cliente'],'anuncios',body),status
