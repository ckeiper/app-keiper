"""Human review before marketplace changes; no editable client payload."""
from html import escape
from copy import deepcopy
import time
from attribute_completion import EXTRACTOR_VERSION
from profitability_view import CSS
from contextual_help import tip,STYLE as HELP_STYLE
from content_technical_view import render as inventory

STATES={'reading':'Análise em andamento','ready':'Pronta para revisão','sending':'Envio em andamento ou sem resposta final','confirmed':'Gravação confirmada','uncertain':'Gravação não confirmada','rejected':'Envio não realizado','stale':'Nova leitura necessária','closed':'Encerrada após conferência manual'}


def render(cid,item,title,csrf,key,plan=None,message='',history=None,manual_form=None):
    esc=lambda v:escape(str(v),quote=True)
    path='/anuncios/'+str(cid)+'/'+esc(item)
    out=CSS+'<main class="pf attribute-editor"><header class="pf-hero"><h2>Completar ficha técnica</h2><p>'+esc(title or item)+'</p></header>'
    out+='<section class="pf-card"><h3>Analisar anúncio'+tip('Análise','Lê título, descrição, atributos, variações e regras da categoria. Sugere valores explícitos em rótulos Campo: valor e frases como O material é aço. Perguntas, alternativas e frases condicionais ficam pendentes. Não interpreta fotos, não inventa dados e não substitui valores existentes. Atributos próprios de variação são preenchidos por dado informado e revisão individual; cor/tamanho que definem combinações não são editados. Campos ocultos são identificados pelas regras retornadas. Atualizações do catálogo, identidade do produto e vínculos compartilhados ficam bloqueadas nesta etapa.')+'</h3>'
    out+='<form method="post"><input type="hidden" name="_csrf" value="'+esc(csrf)+'"><input type="hidden" name="action" value="analyze"><input type="hidden" name="analysis_key" value="'+esc(key)+'"><button>Analisar e completar ficha técnica</button></form></section>'
    if message:out+='<p role="status" class="pf-card">'+esc(message)+'</p>'
    if plan:
        data=deepcopy(plan['data']);result=plan.get('result') or {};state=plan['state']
        confirmed={field['id'] for field in result.get('fields',[]) if field['confirmed']}
        for row in data.get('inventory',{}).get('rows',[]):
            if row['id'] in confirmed:row.update(state='informed',message='Valor confirmado por nova leitura do anúncio')
        outdated=data.get('extractor_version')!=EXTRACTOR_VERSION
        expired=bool(plan.get('created_at') and int(time.time())-plan['created_at']>900)
        display_state='stale' if state=='ready' and (outdated or expired) else state
        out+='<section class="pf-card"><h3>'+STATES[display_state]+'</h3><p role="status">'+esc(result.get('message',''))+'</p>'
        if data.get('blocked'):out+='<p class="ae-blocked" role="status">'+esc(data['blocked'])+'</p>'
        for warning in data.get('warnings',[]):out+='<p>'+esc(warning)+'</p>'
        proposals=data.get('proposals',[])
        if data:
            count=len(proposals);hidden_count=sum(p['hidden'] for p in proposals)
            out+='<p>'+str(count)+(' sugestão' if count==1 else ' sugestões')+' nesta análise · '+str(hidden_count)+(' para campo oculto' if hidden_count==1 else ' para campos ocultos')+'</p>'
            if data.get('proposal_total',0)>50:out+='<p>Exibidas as primeiras 50 de '+str(data['proposal_total'])+' sugestões. Após aplicar, uma nova análise poderá conferir os demais campos.</p>'
        if state=='ready' and (outdated or expired):out+='<p role="status">'+('O leitor foi atualizado.' if outdated else 'A análise expirou.')+' Analise novamente antes de enviar.</p>'
        can_send=state=='ready' and not data.get('blocked') and bool(proposals) and not outdated and not expired
        out+='<form method="post" class="ae-apply"><input type="hidden" name="_csrf" value="'+esc(csrf)+'"><input type="hidden" name="action" value="apply"><input type="hidden" name="plan" value="'+esc(plan['id'])+'">'
        for p in proposals:
            out+='<article class="ae-proposal"><label><input type="checkbox" name="selected" value="'+esc(p['id'])+'"'+('' if can_send else ' disabled')+'> '+esc(p['name'])+(' <span class="ae-hidden">Oculto</span>' if p['hidden'] else '')+'</label><small>'+esc(p.get('attribute_id',p['id']))+'</small><div class="ae-diff"><span>Antes: sem valor identificado</span><strong>'+('Gravado: ' if p['id'] in confirmed else 'Informado: ' if p.get('manual') else 'Sugestão: ')+esc(p['value'])+'</strong></div>'
            for e in p['evidence']:out+='<blockquote><small>'+esc(e['source'])+'</small><br>'+esc(e['text'])+'</blockquote>'
            out+='</article>'
        if not proposals and data:out+='<p>Sem sugestões automáticas'+tip('Sem sugestões','Não foi identificada fonte explícita suficiente. Confira o inventário ou informe um dado faltante para adicioná-lo à revisão.')+'</p>'
        if can_send:
            if any(p.get('variation_id') for p in proposals):out+='<p>Envio por variação'+tip('Envio por variação','Preserva os IDs de todas as variações e os atributos anteriores. Não envie edições simultâneas de variações pelo Mercado Livre ou por outro integrador durante esta operação. A API não oferece uma transação compartilhada com este painel.')+'</p>'
            out+='<button>Aplicar selecionadas no Mercado Livre</button>'
        out+='</form>'
        if result.get('successor_plan'):
            from attribute_editor import valid_plan
            if valid_plan(result['successor_plan']):out+='<a class="ae-history" href="'+path+'/completar-ficha?plan='+esc(result['successor_plan'])+'">Continuar revisão atualizada</a>'
        if state=='ready' and not data.get('blocked') and not outdated and not expired and data.get('manual_fields'):
            from attribute_manual_view import render as manual_view
            out+=manual_view(data['manual_fields'],csrf,plan['id'],key,manual_form)
        if state in ('sending','uncertain'):
            out+='<form method="post"><input type="hidden" name="_csrf" value="'+esc(csrf)+'"><input type="hidden" name="action" value="verify"><input type="hidden" name="plan" value="'+esc(plan['id'])+'"><button>Confirmar envio por nova leitura</button></form><details><summary>Conferência manual</summary><form method="post"><input type="hidden" name="_csrf" value="'+esc(csrf)+'"><input type="hidden" name="action" value="close"><input type="hidden" name="plan" value="'+esc(plan['id'])+'"><label><input type="checkbox" name="manual_checked" value="1" required> Já conferi os campos no Mercado Livre e quero encerrar este envio sem reenviá-lo.</label><button>Encerrar após conferência manual</button></form></details>'
        for field in result.get('fields',[]):out+='<p>'+esc(field['name'])+': '+('Confirmado' if field['confirmed'] else 'Não confirmado')+'</p>'
        out+='</section>'
        if data.get('inventory'):out+='<section class="pf-card"><h3>Inventário desta análise</h3>'+inventory(data['inventory'])+'</section>'
    if history:
        out+='<section class="pf-card"><h3>Análises recentes</h3>'
        for row in history:out+='<a class="ae-history" href="'+path+'/completar-ficha?plan='+esc(row['id'])+'">'+esc(STATES[row['state']])+' · '+esc(row['stamp'])+'</a>'
        out+='</section>'
    from attribute_manual_view import SCRIPT
    out+=SCRIPT
    return out+'<a class="pf-card ae-history" href="'+path+'/conteudo">Voltar à revisão do anúncio</a></main>'+HELP_STYLE+STYLE

STYLE='''<style>html:not([data-theme=light]):has(.attribute-editor),html:not([data-theme=light]) body:has(.attribute-editor),html:not([data-theme=light]) body:has(.attribute-editor) :is(.wrap,.layout,.conteudo){background:#081426!important;color-scheme:dark}html[data-theme=light] body .attribute-editor .pf-hero{background:#e6f0fd!important;color:#193a60!important}html[data-theme=light] body .attribute-editor>a.pf-card{background:#fff!important}.attribute-editor{min-width:0}.ae-field-filters{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:12px}.ae-field-count{font-size:13px;overflow-wrap:anywhere}@media(max-width:600px){.ae-field-filters{grid-template-columns:minmax(0,1fr);gap:0}}.ae-manual-row{min-width:0;border:1px solid #426184;border-radius:10px;padding:12px;margin:12px 0}.ae-manual button{margin:5px 8px 5px 0}.ae-manual [hidden]{display:none!important}.ae-manual label{display:block;margin:12px 0}.ae-manual :is(input,select){display:block;box-sizing:border-box;width:100%;max-width:100%;min-width:0;padding:10px}.attribute-editor form{margin:12px 0}.ae-proposal{border:1px solid #426184;border-radius:12px;padding:16px;margin:14px 0;overflow-wrap:anywhere}.ae-proposal label{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-weight:700}.ae-proposal small{font-size:12px}.ae-diff{display:flex;flex-direction:column;gap:8px;margin:12px 0}.ae-proposal blockquote{margin:10px 0;border-left:3px solid #7892aa;padding-left:12px;white-space:pre-wrap;overflow-wrap:anywhere}.ae-hidden{font-size:11px;padding:4px 8px;border:1px solid #4a9ccc;border-radius:6px}.ae-history{display:block;padding:12px;margin:8px 0;border:1px solid #426184;border-radius:8px}.ae-blocked{border-left:3px solid #c08d54;padding-left:12px}.attribute-editor :is(button,strong){overflow-wrap:anywhere;white-space:normal}.attribute-editor button{max-width:100%}</style>'''
