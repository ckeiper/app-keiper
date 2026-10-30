import hmac
import re
import secrets
import time
from flask import request,session,redirect
from goal_notifications import parent,preference,save,configured
from goal_notification_view import render


def history(conn,query,sid,args):
    if sid is None:return dict(rows=[],page=1,pages=1)
    n=query(conn,'SELECT COUNT(*) AS n FROM listing_goal_notifications WHERE subscription_id=%s',(sid,))[0]['n'];pages=max(1,(n+9)//10)
    try:p=max(1,min(pages,int(args.get('pagina','1'))))
    except (TypeError,ValueError):p=1
    rows=query(conn,'SELECT * FROM listing_goal_notifications WHERE subscription_id=%s ORDER BY id DESC LIMIT 10 OFFSET %s',(sid,(p-1)*10))
    return dict(rows=rows,page=p,pages=pages)


def register(app,login_required,can_view,bank,query,execute,shop_page,ready=configured):
    @app.route('/anuncios/<int:cid>/<item_id>/metas/avisos/<kind>/<int:goal_id>',methods=['GET','POST'])
    @login_required
    def listing_goal_notifications(cid,item_id,kind,goal_id):
        if session.get('tipo')!='admin' or not can_view(cid):return 'Acesso restrito',403
        if not re.fullmatch(r'MLB[0-9]{1,20}',item_id):return 'Anúncio não encontrado',404
        token=session.setdefault('_csrf',secrets.token_urlsafe(32));uid=session['usuario_id'];message='';status=200
        if request.method=='POST' and not hmac.compare_digest(token.encode(),request.form.get('_csrf','').encode()):return 'Formulário expirado. Recarregue a página.',400
        if request.method=='POST':
            try:
                with bank() as conn:save(conn,query,cid,item_id,kind,goal_id,uid,request.form,int(time.time()))
                return redirect(request.path,code=303)
            except LookupError:return 'Meta não encontrada neste anúncio.',404
            except ValueError as exc:message,status=str(exc),400
        with bank() as conn:
            execute(conn,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            shops=query(conn,'SELECT cliente FROM conexoes WHERE id=%s',(cid,))
            if not shops:return 'Loja não encontrada',404
            try:goal=parent(conn,query,cid,item_id,kind,goal_id)
            except LookupError:return 'Meta não encontrada neste anúncio.',404
            users=query(conn,"SELECT email FROM usuarios WHERE id=%s AND tipo='admin'",(uid,))
            email=users[0]['email'] if users else None
            pref=preference(conn,query,cid,item_id,kind,goal_id,uid)
            attempts=history(conn,query,pref['id'] if pref else None,request.args)
        return shop_page('Avisos da meta',cid,shops[0]['cliente'],'anuncios',render(cid,item_id,kind,goal,email,pref,attempts,token,ready(),message)),status
