"""Authenticated, store-scoped read-only management dashboard."""
from html import escape
from flask import request, make_response
from management_data import load_management
from management_view import render_management


def register_management(app,login_required,can_view,bank,query,page,shop_page):
    @app.route('/painel/<int:cid>')
    @login_required
    def store_management(cid):
        if not can_view(cid):
            return page('Acesso negado','<div class="card">Acesso restrito</div>'),403
        try:
            report=load_management(cid,request.args,bank,query)
            if report is None:
                return page('Loja não encontrada','<div class="card">Loja não encontrada</div>'),404
            body=render_management(cid,report,request.args)
            response=make_response(shop_page('Gestão da loja',cid,report['shop']['cliente'],'resumo',body))
        except ValueError as exc:
            response=make_response(page('Gestão da loja','<div class="card" role="alert">'+escape(str(exc))
                +f"<p><a href='/painel/{cid}'>Voltar aos últimos 7 dias completos</a></p></div>"),400)
        response.headers['Cache-Control']='no-store'
        return response
