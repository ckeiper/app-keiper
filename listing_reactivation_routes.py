import hmac
import re
import secrets
import time
from flask import request,session,redirect
from sales_metrics import reporting_today
from listing_tasks import validate,create
from listing_reactivation import TITLE,load,render


def register_reactivation(app,login_required,can_view,bank,query,execute,shop_page,today=reporting_today):
    @app.route('/anuncios/<int:cid>/<item_id>/reativacao',methods=['GET','POST'])
    @login_required
    def listing_reactivation_review(cid,item_id):
        if session.get('tipo')!='admin' or not can_view(cid):return 'Acesso restrito',403
        if not re.fullmatch(r'MLB[0-9]{1,20}',item_id):return 'Anúncio não encontrado',404
        token=session.setdefault('_csrf',secrets.token_urlsafe(32))
        if request.method=='POST' and not hmac.compare_digest(token.encode(),request.form.get('_csrf','').encode()):return 'Formulário expirado. Recarregue a página.',400
        with bank() as conn:
            execute(conn,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            data=load(conn,query,cid,item_id,request.args)
        if data is None:return 'Anúncio não encontrado nesta loja.',404
        values={};message='';status=200
        if request.method=='POST':
            values=dict(request.form)
            try:
                if len(str(values.get('description','')).strip())<10:raise ValueError('Descreva a conferência com pelo menos dez caracteres.')
                task=validate(dict(values,title=TITLE),today())
                with bank() as conn:tid=create(conn,query,execute,cid,item_id,task,session['usuario_id'])
                return redirect(f'/anuncios/{cid}/{item_id}/tarefas?status=all&tarefa={tid}#lt-historico',code=303)
            except ValueError as exc:message,status=str(exc),400
        return shop_page('Revisão de reativação',cid,data['shop']['cliente'],'anuncios',render(cid,item_id,data,today(),int(time.time()),token,values,message)),status
