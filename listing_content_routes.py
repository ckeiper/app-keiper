"""Admin-only review workflow, CSRF protected and scoped to a store listing."""
import hmac
import re
import secrets
from flask import request,session,redirect
from listing_content import validate,save,load,StaleReview
from listing_content_view import render


def register_content(app,login_required,can_view,bank,query,execute,shop_page):
    @app.route('/anuncios/<int:cid>/<item_id>/conteudo',methods=['GET','POST'])
    @login_required
    def listing_content_review(cid,item_id):
        if session.get('tipo')!='admin' or not can_view(cid):return 'Acesso restrito',403
        if not re.fullmatch(r'MLB[0-9]{1,20}',item_id):return 'Anúncio não encontrado',404
        token=session.setdefault('_csrf',secrets.token_urlsafe(32))
        if request.method=='POST' and not hmac.compare_digest(token.encode(),request.form.get('_csrf','').encode()):return 'Formulário expirado. Recarregue a página.',400
        with bank() as conn:
            shops=query(conn,'''SELECT c.cliente,a.titulo,a.fotos,a.clips,a.atualizado_em FROM conexoes c
                JOIN anuncios a ON a.conexao_id=c.id WHERE c.id=%s AND a.item_id=%s''',(cid,item_id))
        if not shops:return 'Anúncio não encontrado nesta loja.',404
        path=f'/anuncios/{cid}/{item_id}/conteudo';message='Revisão registrada.' if request.args.get('salvo')=='1' else '';status=200;values={}
        if request.method=='POST':
            values=dict(request.form)
            try:
                data=validate(request.form)
                with bank() as conn:save(conn,query,execute,cid,item_id,data,session['usuario_id'])
                return redirect(path+'?salvo=1#lc-historico',code=303)
            except StaleReview as exc:message,status=str(exc),409
            except ValueError as exc:message,status=str(exc),400
        with bank() as conn:
            execute(conn,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            model=load(conn,query,cid,item_id,request.args)
        return shop_page('Revisão de conteúdo',cid,shops[0]['cliente'],'anuncios',render(cid,item_id,shops[0],model,token,values,message)),status
