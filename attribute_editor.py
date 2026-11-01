"""Scoped admin workflow. GET never calls the marketplace; only explicit POST writes."""
import hmac
import re
import secrets
import time
from uuid import UUID
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
import psycopg2
from flask import request,session,redirect
from attribute_completion import gather,analyze,owned
from attribute_edit_workflow import apply,verification,selected_proposals,confirmed
import attribute_edit_store as store
from attribute_edit_view import render
from listing_content_snapshot import ContentUnavailable


def valid_plan(value):
    try:return isinstance(value,str) and str(UUID(value))==value
    except (ValueError,TypeError,AttributeError):return False


def budgeted(get):
    deadline=time.monotonic()+20
    def call(url,**kwargs):
        remaining=deadline-time.monotonic()
        if remaining<1:raise ContentUnavailable('Tempo de consulta excedido. Faça uma nova leitura.')
        kwargs['timeout']=(min(3,remaining),min(8,remaining))
        return get(url,**kwargs)
    return call


def register(app,login_required,can_view,bank,query,shop_page,resolve_token,get,put=requests.put):
    @app.route('/anuncios/<int:cid>/<item_id>/completar-ficha',methods=['GET','POST'])
    @login_required
    def attribute_editor(cid,item_id):
        actor=session.get('usuario_id')
        if session.get('tipo')!='admin' or type(actor) is not int or not can_view(cid):return 'Acesso restrito.',403
        if not re.fullmatch(r'MLB[0-9]{1,20}',item_id):return 'Anúncio inválido.',404
        csrf=session.setdefault('_csrf',secrets.token_urlsafe(32))
        if request.method=='POST' and (not isinstance(request.form.get('_csrf'),str) or not hmac.compare_digest(csrf,request.form.get('_csrf',''))):return 'Formulário inválido.',400
        with bank() as conn:
            shops=query(conn,'''SELECT c.*,a.titulo FROM conexoes c JOIN anuncios a ON a.conexao_id=c.id
                WHERE c.id=%s AND a.item_id=%s''',(cid,item_id))
        if not shops:return 'Anúncio não encontrado nesta loja.',404
        shop=shops[0];plan=None;message='';plan_id=request.args.get('plan')
        if request.method=='POST':
            action=request.form.get('action');plan_id=request.form.get('plan')
            try:
                if action not in ('analyze','manual','apply','verify','close'):raise ValueError('Ação inválida.')
                with store.locked(bank,query,cid,item_id) as conn:
                    if action=='analyze':
                        key=request.form.get('analysis_key','')
                        if not re.fullmatch(r'[A-Za-z0-9_-]{20,64}',key):raise ValueError('Recarregue o formulário de análise.')
                        pending=store.active(conn,query,cid,item_id)
                        if pending:
                            if pending[0]['conexao_id']!=cid:raise ValueError('Há um envio pendente para este anúncio em outra conexão. Confira o histórico dessa conexão antes de continuar.')
                            return redirect(request.path+'?plan='+str(pending[0]['id']),303)
                        plan,created=store.create(conn,query,cid,item_id,actor,key)
                        if created:
                            try:
                                facts=gather(resolve_token(shop),shop['user_id'],item_id,budgeted(get));data=analyze(facts)
                                store.transition(conn,query,plan,actor,'ready',dict(message='Selecione os valores que conferiu antes de enviar.'),data=data)
                            except ContentUnavailable as exc:store.transition(conn,query,plan,actor,'rejected',dict(message=str(exc)))
                    else:
                        if not valid_plan(plan_id):raise ValueError('Análise inválida.')
                        plan=store.load(conn,query,cid,item_id,actor,plan_id)
                        persist=lambda state,result,**kw:store.transition(conn,query,plan,actor,state,result,**kw)
                        if action=='manual':
                            from attribute_manual import add
                            plan=add(conn,query,cid,item_id,actor,plan,request.form,shop,lambda:resolve_token(shop),budgeted(get))
                        elif action=='apply':
                            if plan['state']!='ready':raise ValueError('Esta análise já foi usada. Nenhuma atualização foi reenviada.')
                            if shop.get('status')!='ativa':raise ValueError('Conexão inativa: envio indisponível.')
                            selected_proposals(plan['data'],request.form.getlist('selected'))
                            if store.active(conn,query,cid,item_id):raise ValueError('Há um envio pendente de confirmação. Nenhum reenvio foi feito.')
                            apply(plan,request.form.getlist('selected'),resolve_token(shop),shop['user_id'],item_id,budgeted(get),put,persist)
                        elif action=='verify':
                            if plan['state'] not in ('sending','uncertain'):raise ValueError('Este envio não está pendente de confirmação.')
                            try:
                                result=verification(plan['data'],plan['selected'],owned(resolve_token(shop),shop['user_id'],item_id,budgeted(get)))
                                persist('confirmed' if confirmed(result) else 'uncertain',result)
                            except ContentUnavailable as exc:persist('uncertain',dict(message=str(exc)))
                        else:
                            if plan['state'] not in ('sending','uncertain') or request.form.get('manual_checked')!='1':raise ValueError('Confirme a conferência manual antes de encerrar.')
                            persist('closed',dict(message='Encerrado pelo administrador após conferência manual. Nenhuma atualização foi reenviada.'))
                    return redirect(request.path+'?plan='+str(plan['id']),303)
            except (ValueError,ContentUnavailable) as exc:message=str(exc)
            except psycopg2.Error:message='Não foi possível registrar a operação com segurança. Confira o histórico antes de continuar.'
        if plan_id and not valid_plan(plan_id):return 'Análise inválida.',400
        if valid_plan(plan_id):
            with bank() as conn:
                try:plan=store.load(conn,query,cid,item_id,actor,plan_id)
                except ValueError:return 'Análise não encontrada nesta loja.',404
        with bank() as conn:history=query(conn,'''SELECT id,state,created_at FROM listing_attribute_plans
            WHERE conexao_id=%s AND item_id=%s AND created_by=%s ORDER BY created_at DESC,id DESC LIMIT 10''',(cid,item_id,actor))
        for row in history:row['stamp']=datetime.fromtimestamp(row['created_at'],ZoneInfo('America/Sao_Paulo')).strftime('%d/%m %H:%M')
        return shop_page('Completar ficha técnica',cid,shop['cliente'],'anuncios',render(cid,item_id,shop['titulo'],csrf,secrets.token_urlsafe(24),plan,message,history,request.form if request.method=='POST' else None),refresh=False)
