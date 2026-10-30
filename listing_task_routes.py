"""Authenticated task routes. A task status never changes the marketplace."""
import hmac
import re
import secrets
from flask import request,session,redirect
from sales_metrics import reporting_today
from listing_tasks import validate,create,transition,load,MissingTask,StaleTask
from listing_task_view import render


def register_tasks(app,login_required,can_view,bank,query,execute,shop_page,today=reporting_today):
    @app.route('/anuncios/<int:cid>/<item_id>/tarefas',methods=['GET','POST'])
    @login_required
    def listing_task_workflow(cid,item_id):
        if session.get('tipo')!='admin' or not can_view(cid):return 'Acesso restrito',403
        if not re.fullmatch(r'MLB[0-9]{1,20}',item_id):return 'Anúncio não encontrado',404
        token=session.setdefault('_csrf',secrets.token_urlsafe(32))
        if request.method=='POST' and not hmac.compare_digest(token.encode(),request.form.get('_csrf','').encode()):
            return 'Formulário expirado. Recarregue a página.',400
        with bank() as conn:
            shops=query(conn,'''SELECT c.cliente,a.titulo FROM conexoes c JOIN anuncios a ON a.conexao_id=c.id
                WHERE c.id=%s AND a.item_id=%s''',(cid,item_id))
        if not shops:return 'Anúncio não encontrado nesta loja.',404
        path=f'/anuncios/{cid}/{item_id}/tarefas'
        message='Tarefa atualizada.' if request.args.get('salvo')=='1' else ''
        status=200;values={}
        if request.method=='POST':
            try:
                operation=request.form.get('operation','')
                if operation=='create':
                    values=dict(request.form);validated=validate(request.form,today())
                    with bank() as conn:tid=create(conn,query,execute,cid,item_id,validated,session['usuario_id'])
                elif operation=='status':
                    tid=request.form.get('task_id')
                    with bank() as conn:
                        transition(conn,query,execute,cid,item_id,tid,request.form.get('version'),
                            request.form.get('previous'),request.form.get('target'),session['usuario_id'])
                else:raise ValueError('Operação inválida.')
                return redirect(path+'?status=all&tarefa='+str(int(tid))+'&salvo=1#lt-historico',code=303)
            except MissingTask:return 'Tarefa não encontrada neste anúncio.',404
            except StaleTask as exc:message,status=str(exc),409
            except (ValueError,TypeError) as exc:message,status=str(exc) or 'Revise os campos.',400
        try:
            with bank() as conn:
                execute(conn,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                model=load(conn,query,cid,item_id,request.args,today())
        except MissingTask:return 'Tarefa não encontrada neste anúncio.',404
        except ValueError as exc:return str(exc),400
        body=render(cid,item_id,shops[0],model,today(),token,values=values,message=message)
        return shop_page('Tarefas do anúncio',cid,shops[0]['cliente'],'anuncios',body),status

    @app.route('/anuncios/<int:cid>/<item_id>/calendario',methods=['GET'])
    @login_required
    def listing_task_calendar(cid,item_id):
        from listing_calendar import load as calendar_load,render as calendar_render
        if session.get('tipo')!='admin' or not can_view(cid):return 'Acesso restrito',403
        if not re.fullmatch(r'MLB[0-9]{1,20}',item_id):return 'Anúncio não encontrado',404
        try:
            with bank() as conn:
                execute(conn,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                shops=query(conn,'''SELECT c.cliente,a.titulo FROM conexoes c JOIN anuncios a ON a.conexao_id=c.id
                    WHERE c.id=%s AND a.item_id=%s''',(cid,item_id))
                if not shops:return 'Anúncio não encontrado nesta loja.',404
                model=calendar_load(conn,query,cid,item_id,request.args,today())
        except ValueError as exc:return str(exc),400
        return shop_page('Calendário do anúncio',cid,shops[0]['cliente'],'anuncios',calendar_render(cid,item_id,shops[0],model,today()))
