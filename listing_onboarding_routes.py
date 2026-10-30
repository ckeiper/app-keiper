"""Administrator-only plan enrollment with scoped, atomic task creation."""
import hmac
import re
import secrets
from flask import request,session,redirect
from sales_metrics import reporting_today
from listing_onboarding import validate,create_plan,load
from listing_onboarding_view import render


def register_onboarding(app,login_required,can_view,bank,query,execute,shop_page,today=reporting_today):
    @app.route('/anuncios/<int:cid>/<item_id>/primeiros-30-dias',methods=['GET','POST'])
    @login_required
    def listing_onboarding_plan(cid,item_id):
        if session.get('tipo')!='admin' or not can_view(cid):return 'Acesso restrito',403
        if not re.fullmatch(r'MLB[0-9]{1,20}',item_id):return 'Anúncio não encontrado',404
        token=session.setdefault('_csrf',secrets.token_urlsafe(32))
        if request.method=='POST' and not hmac.compare_digest(token.encode(),request.form.get('_csrf','').encode()):return 'Formulário expirado. Recarregue a página.',400
        with bank() as conn:
            shops=query(conn,'''SELECT c.cliente,a.titulo FROM conexoes c JOIN anuncios a ON a.conexao_id=c.id
                WHERE c.id=%s AND a.item_id=%s''',(cid,item_id))
        if not shops:return 'Anúncio não encontrado nesta loja.',404
        path=f'/anuncios/{cid}/{item_id}/primeiros-30-dias';values={};message='';status=200
        if request.method=='POST':
            values=dict(request.form)
            try:
                data=validate(request.form,today())
                with bank() as conn:create_plan(conn,query,execute,cid,item_id,data,session['usuario_id'])
                return redirect(path,code=303)
            except ValueError as exc:message,status=str(exc),400
        with bank() as conn:
            execute(conn,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            data=load(conn,query,cid,item_id)
        return shop_page('Primeiros 30 dias',cid,shops[0]['cliente'],'anuncios',render(cid,item_id,shops[0],data,today(),token,values,message)),status
