"""Authenticated, store-scoped manual actions. Writes are administrator-only."""
import hmac
import re
import secrets
import time
from datetime import datetime, timedelta
from html import escape
from urllib.parse import urlencode
from flask import request, session, redirect
from sales_metrics import reporting_today
from automatic_history import HISTORY, detail_html
from listing_interventions import KINDS, BR, CSS, validate, load_comparison, comparison_html


def register_interventions(app, login_required, can_view, bank, query, execute, shop_page, today=reporting_today):
    @app.route('/anuncios/<int:cid>/<item_id>/acoes',methods=['GET','POST'])
    @login_required
    def listing_interventions(cid,item_id):
        if not can_view(cid):
            return 'Acesso restrito',403
        admin=session.get('tipo')=='admin'
        if request.method=='POST' and not admin:
            return 'Somente o administrador pode registrar ou desconsiderar ações.',403
        if not re.fullmatch(r'MLB[0-9]{1,20}',item_id):
            return 'Anúncio não encontrado',404
        token=session.setdefault('intervention_csrf',secrets.token_urlsafe(32))
        if request.method=='POST' and not hmac.compare_digest(token.encode(),request.form.get('csrf_token','').encode()):
            return 'Formulário expirado. Recarregue a página.',400
        with bank() as conn:
            stores=query(conn,'''SELECT c.cliente,a.titulo FROM conexoes c JOIN anuncios a
                ON a.conexao_id=c.id WHERE c.id=%s AND a.item_id=%s''',(cid,item_id))
        if not stores:
            return 'Anúncio não encontrado nesta loja.',404
        path=f'/anuncios/{cid}/{item_id}/acoes'
        day=today()
        message,status='',200
        if request.method=='POST':
            try:
                operation=request.form.get('operation','create')
                if operation=='void':
                    try:
                        action_id=int(request.form.get('action_id','0'))
                    except ValueError:
                        raise ValueError('Registro inválido.') from None
                    if not 0<action_id<2**63:
                        raise ValueError('Registro inválido.')
                    with bank() as conn:
                        changed=query(conn,'''UPDATE listing_interventions SET void_at=%s,void_by=%s
                            WHERE id=%s AND conexao_id=%s AND item_id=%s AND void_at IS NULL RETURNING id''',
                            (int(time.time()),session['usuario_id'],action_id,cid,item_id))
                    if not changed:
                        return 'Registro não encontrado ou já desconsiderado.',404
                elif operation=='create':
                    event_date,kind,note,key=validate(request.form,day)
                    with bank() as conn:
                        execute(conn,'''INSERT INTO listing_interventions
                            (conexao_id,item_id,event_date,kind,note,created_at,created_by,submission_key)
                            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT(conexao_id,submission_key) DO NOTHING''',
                            (cid,item_id,event_date,kind,note,int(time.time()),session['usuario_id'],key))
                else:
                    raise ValueError('Operação inválida.')
                return redirect(path+'?salvo=1',code=303)
            except (ValueError,TypeError) as exc:
                message,status=str(exc) or 'Revise os campos do formulário.',400
        elif request.args.get('salvo')=='1':
            message='Registro atualizado.'
        with bank() as conn:
            if request.method=='GET':
                execute(conn,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            total=query(conn,'SELECT COUNT(*) AS n FROM '+HISTORY+' WHERE conexao_id=%s AND item_id=%s',(cid,item_id))[0]['n']
            pages=max(1,(total+9)//10)
            try:
                page=max(1,min(pages,int(request.args.get('pagina','1'))))
            except ValueError:
                page=1
            rows=query(conn,'SELECT * FROM '+HISTORY+' WHERE conexao_id=%s AND item_id=%s ORDER BY event_date DESC,created_at DESC,source,id DESC LIMIT 10 OFFSET %s',(cid,item_id,(page-1)*10))
            selected=next((r for r in rows if r['void_at'] is None),None)
            if request.args.get('acao'):
                try:
                    selected_id=int(request.args['acao'])
                    if not 0<selected_id<2**63:
                        raise ValueError()
                except ValueError:
                    return 'Registro inválido',400
                origin=request.args.get('origem','manual')
                if origin not in ('manual','automatic'):
                    return 'Origem inválida',400
                found=query(conn,'SELECT * FROM '+HISTORY+' WHERE id=%s AND conexao_id=%s AND item_id=%s AND source=%s',(selected_id,cid,item_id,origin))
                if not found:
                    return 'Registro não encontrado nesta loja e anúncio.',404
                selected=found[0]
            result=load_comparison(conn,query,cid,item_id,selected['event_date'],day,financial=admin and selected.get('kind')=='preco' and request.method=='GET') if selected and selected['void_at'] is None else None
        def hidden():
            return "<input type='hidden' name='csrf_token' value='"+escape(token,quote=True)+"'>"
        body=CSS+"<div class='interventions'><header class='iv-head'><h2>Histórico automático do anúncio</h2><p>"+escape(stores[0]['titulo'] or item_id)+' · '+escape(item_id)+"</p><p>Alterações detectadas nas coletas, sem preencher formulários. A primeira leitura cria a referência; falhas e campos ausentes não geram alterações.</p><a class='iv-btn' href='/diagnostico/"+str(cid)+'/'+item_id+"'>Voltar ao diagnóstico</a></header>"
        if message:
            body+="<p class='iv-status' role='status'>"+escape(message)+'</p>'
        if admin:
            values=request.form if request.method=='POST' and request.form.get('operation','create')=='create' else {}
            body+="<details"+(' open' if status==400 else '')+" class='iv-card'><summary>Adicionar observação manual (opcional)</summary><h3>Registrar ação realizada</h3><form class='iv-form' method='post'>"+hidden()
            body+="<input type='hidden' name='submission_key' value='"+escape(values.get('submission_key') or secrets.token_urlsafe(24),quote=True)+"'>"
            body+="<label>Tipo<select name='kind' aria-label='Tipo' required>"+''.join("<option value='%s'%s>%s</option>" % (key,' selected' if values.get('kind')==key else '',label) for key,label in KINDS.items())+'</select></label>'
            body+="<label>Data em que a ação foi feita<input name='event_date' type='date' required min='"+(day-timedelta(days=365)).isoformat()+"' max='"+day.isoformat()+"' value='"+escape(values.get('event_date') or day.isoformat(),quote=True)+"'></label>"
            body+="<label class='iv-wide'>O que foi alterado<textarea name='note' required minlength='10' maxlength='1500' placeholder='Ex.: foto principal substituída; descreva o que mudou e em qual variação.'>"+escape(values.get('note','')[:1500])+"</textarea></label><div class='iv-wide'><button class='iv-primary'>Registrar ação</button></div></form><p class='iv-meta'>Registro manual de uma ação já executada; este formulário não altera o anúncio no Mercado Livre. Horário de Brasília. Para corrigir, desconsidere o registro e crie outro.</p></details>"
        if selected:
            body+="<section class='iv-card'><h3>"+('Alteração detectada · ' if selected.get('source')=='automatic' else 'Observação manual · ')+selected['event_date'].strftime('%d/%m/%Y')+'</h3><b>'+escape(KINDS[selected['kind']])+"</b><p class='iv-note'>"+escape(selected['note'])+'</p>'
            body+=detail_html(selected)
            body+='<p class="iv-meta">Registrado em '+datetime.fromtimestamp(selected['created_at'],BR).strftime('%d/%m/%Y %H:%M')+('. Detecção automática nas coletas.' if selected.get('source')=='automatic' else '. Data da ação informada pelo administrador.')+'</p></section>'
            body+=comparison_html(result,selected) if result else "<p class='iv-status warn'>Registro desconsiderado. Ele permanece no histórico e não entra na comparação.</p>"
            if admin and result and 'financial' in result:
                from profitability_action import render as render_financial
                body+=render_financial(result['financial'],cid,item_id,result['periods'],day)

        body+="<section aria-label='Histórico de ações'><h3>Histórico · %s registros</h3>" % total
        for row in rows:
            body+="<article class='iv-card%s'><span class='iv-meta'>" % (' iv-void' if row['void_at'] is not None else '')+('Automático' if row.get('source')=='automatic' else 'Observação manual')+'</span><br><b>'+row['event_date'].strftime('%d/%m/%Y')+' · '+escape(KINDS[row['kind']])+"</b><p class='iv-note'>"+escape(row['note'])+'</p>'
            body+=detail_html(row)
            if row['void_at'] is not None:
                body+='<p class="iv-meta">Desconsiderado em '+datetime.fromtimestamp(row['void_at'],BR).strftime('%d/%m/%Y %H:%M')+'</p>'
            else:
                body+="<div class='iv-tools'><a class='iv-btn' href='?"+urlencode({'acao':row['id'],'origem':row.get('source','manual'),'pagina':page})+"'>Comparar períodos</a>"
                if admin and row.get('source','manual')=='manual':
                    body+="<form method='post'>"+hidden()+"<input type='hidden' name='operation' value='void'><input type='hidden' name='action_id' value='"+str(row['id'])+"'><button>Desconsiderar registro</button></form>"
                body+='</div>'
            body+='</article>'
        if not rows:
            body+="<p class='iv-card'>Ainda não há alterações detectadas. O histórico será preenchido automaticamente pelas próximas coletas; a primeira leitura é a referência.</p>"
        body+="<nav class='iv-tools' aria-label='Paginação de ações'>Página %s de %s" % (page,pages)
        for label,n in [('Anterior',page-1),('Próxima',page+1)]:
            if 1<=n<=pages:
                body+="<a class='iv-btn' href='?pagina=%s'>%s</a>" % (n,label)
        body+='</nav></section></div>'
        return shop_page('Histórico do anúncio',cid,stores[0]['cliente'],'anuncios',body),status
