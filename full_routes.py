"""Authorized, cached-only Full report routes."""
from datetime import datetime, time, timedelta
from html import escape
from urllib.parse import urlencode

from flask import request, redirect
from full_view import render_full
from overview_read import bounded_query
from sales_metrics import period, SAO_PAULO
from sales_view import filters


def register_full(app, login_required, can_view, banco, query, page, shop_page, session):
    @app.route('/full')
    @login_required
    def full_choose_store():
        try:
            cid = int(request.args.get('loja', ''))
        except ValueError:
            return page('Full', '<div class="card">Selecione uma loja no painel.</div>'), 400
        if not can_view(cid):
            return page('Acesso negado', '<div class="card">Acesso restrito</div>'), 403
        return redirect('/full/' + str(cid))

    @app.route('/full/<int:cid>')
    @login_required
    def full_report(cid):
        if not can_view(cid):
            return page('Acesso negado', '<div class="card">Acesso restrito</div>'), 403
        with banco() as conn:
            shop = query(conn, 'SELECT id,cliente FROM conexoes WHERE id=%s', (cid,))
            if not shop:
                return page('Full', '<div class="card">Loja não encontrada</div>'), 404
            if session.get('tipo') == 'admin':
                shops = query(conn, 'SELECT id,cliente FROM conexoes ORDER BY cliente,id', ())
            else:
                shops = shop
            listings = query(conn, 'SELECT item_id,titulo FROM anuncios WHERE conexao_id=%s ORDER BY titulo,item_id', (cid,))
        allowed = [s for s in shops if can_view(s['id'])]
        body = """<style>
        body:has(.full-page-theme),body:has(.full-page-theme) .layout,body:has(.full-page-theme) .layout>.conteudo{background:#081426;color:#eaf2ff}
        body:has(.full-page-theme) .conteudo h2{color:#edf5ff}
        body:has(.full-page-theme) .conteudo>form.card,body:has(.full-page-theme) .conteudo>.card{background:#11243a;border:1px solid #2d4864;color:#eaf2ff;border-radius:15px}
        body:has(.full-page-theme) .conteudo form.card{display:flex;align-items:end;gap:12px;flex-wrap:wrap}
        body:has(.full-page-theme) .conteudo form.card label{display:grid;gap:6px;min-width:140px;color:#bdd0e4;font-size:12px;font-weight:700}
        body:has(.full-page-theme) .conteudo form.card input,body:has(.full-page-theme) .conteudo form.card select{min-height:40px;max-width:100%;box-sizing:border-box;background:#0d1d30;border:1px solid #3a5772;border-radius:8px;color:#f1f7ff;padding:8px 10px;color-scheme:dark}
        body:has(.full-page-theme) .conteudo .aviso{background:#382e21;border-color:#80653c;color:#ffe0ae}
        @media(max-width:600px){body:has(.full-page-theme) .conteudo form.card label{flex:1;min-width:120px}}
        </style><span class='full-page-theme' hidden></span><h2>Full e vendas</h2><form action='/full' method='get' class='card'><label>Loja <select name='loja'>"""
        for s in allowed:
            body += "<option value='" + str(s['id']) + "'" + (' selected' if s['id'] == cid else '') + '>' + escape(s['cliente']) + '</option>'
        body += "</select></label> <button class='btn-acoes'>Abrir loja</button></form>"
        if not listings:
            body += '<div class="card">Não há anúncios coletados nesta loja.</div>'
            return shop_page('Full e vendas',cid,shop[0]['cliente'],'full',body)
        item_id = request.args.get('item_id', listings[0]['item_id'])
        listing = next((a for a in listings if a['item_id'] == item_id), None)
        if listing is None:
            return shop_page('Full e vendas',cid,shop[0]['cliente'],'full',body + '<div class="card">Anúncio não encontrado nesta loja.</div>'), 404
        select = "<label>Anúncio <select name='item_id'>"
        for a in listings:
            select += "<option value='" + escape(a['item_id'],quote=True) + "'" + (' selected' if a['item_id'] == item_id else '') + '>' + escape(str(a.get('titulo') or a['item_id'])) + ' · ' + escape(a['item_id']) + '</option>'
        select += '</select></label> '
        body += filters(cid, request.args, action='/full/' + str(cid)).replace('<button', select + '<button', 1)
        try:
            start,end,_,_ = period(request.args)
            if (end-start).days >= 180:
                raise ValueError('Selecione no máximo 180 dias para comparar Full e vendas.')
            since = int(datetime.combine(start,time.min,SAO_PAULO).timestamp())
            until = int(datetime.combine(end+timedelta(days=1),time.min,SAO_PAULO).timestamp())
            with banco() as conn:
                conn.set_session(isolation_level='REPEATABLE READ',readonly=True)
                read = bounded_query(conn,query)
                observations = read(conn, '''SELECT item_id,observed_at,state,quantity,logistics,evidence
                    FROM full_observations WHERE conexao_id=%s AND item_id=%s
                    AND observed_at >= %s AND observed_at < %s ORDER BY observed_at LIMIT 10001''',
                                    (cid,item_id,since,until))
                if len(observations) > 10000:
                    raise ValueError('Há mais de 10 mil consultas nesta seleção. Reduza o período; nenhum histórico parcial foi exibido.')
                first = read(conn,'''SELECT MIN(observed_at) AS first,
                    MIN(observed_at) FILTER (WHERE state <> 'unknown') AS first_known
                    FROM full_observations WHERE conexao_id=%s AND item_id=%s''', (cid,item_id))[0]
                orders = read(conn, '''SELECT conexao_id,pedido_id,status,total,moeda,criado_em,
                    pagamentos_json,unidades,vendas_dia_coleta FROM pedidos
                    WHERE conexao_id=%s AND vendas_verificado_em IS NOT NULL
                    AND (keiper_overview_day_v1(criado_em) BETWEEN %s AND %s
                         OR keiper_overview_day_v1(criado_em) IS NULL)''', (cid,start,end))
                items = read(conn, '''SELECT pi.conexao_id,pi.pedido_id,pi.item_id,pi.quantidade,pi.preco_unitario
                    FROM pedidos_itens pi JOIN pedidos p ON p.conexao_id=pi.conexao_id AND p.pedido_id=pi.pedido_id
                    WHERE p.conexao_id=%s AND p.vendas_verificado_em IS NOT NULL
                    AND (keiper_overview_day_v1(p.criado_em) BETWEEN %s AND %s
                         OR keiper_overview_day_v1(p.criado_em) IS NULL)''',(cid,start,end))
                coverage = read(conn, 'SELECT dia FROM vendas_cobertura WHERE conexao_id=%s AND dia BETWEEN %s AND %s', (cid,start.isoformat(),end.isoformat()))
                legacy = read(conn, 'SELECT EXISTS(SELECT 1 FROM pedidos WHERE conexao_id=%s AND vendas_verificado_em IS NULL) AS pending', (cid,))[0]['pending']
            body += render_full(cid,request.args,listing,observations,orders,items,[r['dia'] for r in coverage],first,legacy)
        except ValueError as exc:
            body += '<div class="aviso">' + escape(str(exc)) + '</div>'
        return shop_page('Full e vendas',cid,shop[0]['cliente'],'full',body)
