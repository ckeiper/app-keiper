import hmac
import re
import secrets
import time
from flask import request,session,redirect
from sales_metrics import reporting_today
from listing_sales_goals import validate,create,cancel,load
from listing_sales_goal_view import render


def register_sales_goals(app,login_required,can_view,bank,query,execute,shop_page,today=reporting_today):
    @app.route('/anuncios/<int:cid>/<item_id>/metas-vendas',methods=['GET','POST'])
    @login_required
    def listing_sales_goal_workflow(cid,item_id):
        if session.get('tipo')!='admin' or not can_view(cid):return 'Acesso restrito',403
        if not re.fullmatch(r'MLB[0-9]{1,20}',item_id):return 'Anúncio não encontrado',404
        token=session.setdefault('_csrf',secrets.token_urlsafe(32));values={};message='';status=200
        if request.method=='POST' and not hmac.compare_digest(token.encode(),request.form.get('_csrf','').encode()):return 'Formulário expirado. Recarregue a página.',400
        with bank() as conn:
            execute(conn,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            shops=query(conn,'''SELECT c.cliente,a.titulo,a.item_id,a.quantidade,a.atualizado_em FROM conexoes c JOIN anuncios a ON a.conexao_id=c.id
                WHERE c.id=%s AND a.item_id=%s''',(cid,item_id))
            if not shops:return 'Anúncio não encontrado nesta loja.',404
            model=load(conn,query,cid,item_id,request.args)
            from listing_sales_goals import evaluate_current
            model['evaluations']={row['id']:evaluate_current(conn,query,cid,item_id,row,today()) for row in model['rows']}
        path=f'/anuncios/{cid}/{item_id}/metas-vendas'
        if request.method=='POST':
            try:
                operation=request.form.get('operation')
                if operation=='create':
                    values=dict(request.form);data=validate(request.form,today())
                    with bank() as conn:create(conn,query,cid,item_id,data,session['usuario_id'])
                elif operation=='cancel':
                    with bank() as conn:cancel(conn,query,cid,item_id,request.form.get('goal_id'),session['usuario_id'])
                else:raise ValueError('Operação inválida.')
                return redirect(path,code=303)
            except LookupError:return 'Meta não encontrada neste anúncio.',404
            except ValueError as exc:message,status=str(exc),400
        return shop_page('Metas de vendas',cid,shops[0]['cliente'],'anuncios',render(cid,item_id,shops[0],model,today(),int(time.time()),token,values,message)),status
