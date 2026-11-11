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
    out+='<section class="pf-card ae-analysis"><h3>Analisar anúncio'+tip('Análise','Lê título, descrição, atributos, variações e regras oficiais da categoria. Sugere valores com fonte explícita e preserva os existentes. Com variações, o leitor exige uma seção comum verificável para sugerir frases; contextos específicos ou ambíguos ficam para conferência. Campos próprios de variação exigem dado informado. Catálogo, identidade e vínculos compartilhados ficam bloqueados. Não interpreta fotos.')+'</h3>'
    out+='<form method="post"><input type="hidden" name="_csrf" value="'+esc(csrf)+'"><input type="hidden" name="action" value="analyze"><input type="hidden" name="analysis_key" value="'+esc(key)+'"><button>Ler e preencher ficha técnica</button></form></section>'
    if message:out+='<p role="status" class="pf-card">'+esc(message)+'</p>'
    if plan:
        data=deepcopy(plan['data']);result=plan.get('result') or {};state=plan['state']
        confirmed={field['id'] for field in result.get('fields',[]) if field['confirmed']}
        for row in data.get('inventory',{}).get('rows',[]):
            if row['id'] in confirmed:row.update(state='informed',message='Valor confirmado por nova leitura do anúncio')
        proposed={p['id'] for p in data.get('proposals',[])}
        pending=[field for field in data.get('manual_fields',[])
                 if field['id'] not in proposed and field['id'] not in confirmed]
        pending_codes={field.get('attribute_id',field['id']) for field in pending}
        for row in data.get('inventory',{}).get('rows',[]):
            row['manual_pending']=row['id'] in pending_codes
        outdated=data.get('extractor_version')!=EXTRACTOR_VERSION
        expired=bool(plan.get('created_at') and int(time.time())-plan['created_at']>900)
        display_state='stale' if state=='ready' and (outdated or expired) else state
        compact_only=display_state=='ready' and bool(pending) and not data.get('proposals') and not data.get('blocked')
        out+='<section class="pf-card">'
        if not compact_only:out+='<h3>'+STATES[display_state]+'</h3>'
        if result.get('message') and (not compact_only or result.get('message')!='Selecione os valores que conferiu antes de enviar.') and (not isinstance(result.get('conditional'),dict) or result.get('message')!=result['conditional'].get('message')):out+='<p role="status">'+esc(result.get('message',''))+'</p>'
        from attribute_conditional_review import render as conditional_view
        out+=conditional_view(result.get('conditional'))
        if data.get('blocked'):out+='<p class="ae-blocked" role="status">'+esc(data['blocked'])+'</p>'
        for warning in data.get('warnings',[]):out+='<p>'+esc(warning)+'</p>'
        proposals=data.get('proposals',[])
        if data.get('proposal_total',0)>50:out+='<p>Exibidas as primeiras 50 de '+str(data['proposal_total'])+' sugestões. Após aplicar, uma nova análise poderá conferir os demais campos.</p>'

        if state=='ready' and (outdated or expired):out+='<p role="status">'+('O leitor foi atualizado.' if outdated else 'A análise expirou.')+' Analise novamente antes de enviar.</p>'
        can_send=state=='ready' and not data.get('blocked') and bool(proposals) and not outdated and not expired
        out+='<form method="post" class="ae-apply"><input type="hidden" name="_csrf" value="'+esc(csrf)+'"><input type="hidden" name="action" value="apply"><input type="hidden" name="plan" value="'+esc(plan['id'])+'">'
        for p in proposals:
            out+='<article class="ae-proposal"><label><input type="checkbox" name="selected" value="'+esc(p['id'])+'"'+('' if can_send else ' disabled')+'> '+esc(p['name'])+(' <span class="ae-hidden">Oculto</span>' if p['hidden'] else '')+'</label><div class="ae-diff"><strong>'+('Selecionado: ' if p['id'] in confirmed else 'Informado: ' if p.get('manual') else 'Sugestão: ')+esc(p['value'])+'</strong></div>'
            out+='<details class="ae-source"><summary>Ver fonte</summary><small>'+esc(p.get('attribute_id',p['id']))+'</small>'
            for e in p['evidence']:out+='<blockquote><small>'+esc(e['source'])+'</small><br>'+esc(e['text'])+'</blockquote>'
            out+='</details></article>'
        if can_send:
            if any(p.get('variation_id') for p in proposals):out+='<p>Envio por variação'+tip('Envio por variação','Preserva os IDs de todas as variações e os atributos anteriores. Não envie edições simultâneas de variações pelo Mercado Livre ou por outro integrador durante esta operação. A API não oferece uma transação compartilhada com este painel.')+'</p>'
            out+='<button>Aplicar selecionadas no Mercado Livre</button>'+tip('Antes do envio','Quando a categoria retorna regras condicionais, os campos selecionados são conferidos em consulta oficial antes de gravar. Consulta inconclusiva ou presença não verificada interrompe o envio; não confirma erro no anúncio.')
        out+='</form>'
        from attribute_review_recovery import eligible as recoverable
        if recoverable(plan):out+='<form method="post" class="ae-recover"><input type="hidden" name="_csrf" value="'+esc(csrf)+'"><input type="hidden" name="action" value="recover"><input type="hidden" name="plan" value="'+esc(plan['id'])+'"><input type="hidden" name="recovery_key" value="'+esc(key)+'"><button>Reanalisar mantendo dados informados</button>'+tip('Reanalisar mantendo dados','Faz uma nova leitura e reaproveita somente dados declarados ainda elegíveis. Campos já preenchidos ou indisponíveis não são reaproveitados. Requer nova seleção e não envia ao Mercado Livre.')+'</form>'
        recovery=result.get('recovery',{})
        if isinstance(recovery,dict) and recovery.get('omitted'):
            out+='<details class="ae-recovery-omitted"><summary>Campos não reaproveitados</summary><ul>'+''.join('<li>'+esc(code)+'</li>' for code in recovery['omitted'][:50])+'</ul></details>'
        if result.get('successor_plan'):
            from attribute_editor import valid_plan
            if valid_plan(result['successor_plan']):out+='<a class="ae-history" href="'+path+'/completar-ficha?plan='+esc(result['successor_plan'])+'">Continuar revisão atualizada</a>'
        if state=='ready' and not data.get('blocked') and not outdated and not expired and data.get('manual_fields'):
            from attribute_manual_view import render as manual_view,compact
            if pending and manual_form is None:out+=compact(pending,csrf,plan['id'],key)
            out+=manual_view(data['manual_fields'],csrf,plan['id'],key,manual_form)
        if state in ('sending','uncertain'):
            out+='<form method="post"><input type="hidden" name="_csrf" value="'+esc(csrf)+'"><input type="hidden" name="action" value="verify"><input type="hidden" name="plan" value="'+esc(plan['id'])+'"><button>Confirmar envio por nova leitura</button></form><details><summary>Conferência manual</summary><form method="post"><input type="hidden" name="_csrf" value="'+esc(csrf)+'"><input type="hidden" name="action" value="close"><input type="hidden" name="plan" value="'+esc(plan['id'])+'"><label><input type="checkbox" name="manual_checked" value="1" required> Já conferi os campos no Mercado Livre e quero encerrar este envio sem reenviá-lo.</label><button>Encerrar após conferência manual</button></form></details>'
        from attribute_readback import render as readback_view
        out+=readback_view(result.get('fields',[]))
        out+='</section>'
        if data.get('inventory'):out+='<details class="pf-card ae-details"><summary>Ver detalhes da ficha técnica</summary>'+inventory(data['inventory'])+'</details>'
    if history:
        out+='<details class="pf-card ae-details"><summary>Análises recentes</summary>'
        for row in history:out+='<a class="ae-history" href="'+path+'/completar-ficha?plan='+esc(row['id'])+'">'+esc(STATES[row['state']])+' · '+esc(row['stamp'])+'</a>'
        out+='</details>'
    from attribute_manual_view import SCRIPT
    out+=SCRIPT
    return out+'<a class="pf-card ae-history" href="'+path+'/conteudo">Voltar à revisão do anúncio</a></main>'+HELP_STYLE+STYLE

STYLE='''<style>html:not([data-theme=light]):has(.attribute-editor),html:not([data-theme=light]) body:has(.attribute-editor),html:not([data-theme=light]) body:has(.attribute-editor) :is(.wrap,.layout,.conteudo){background:#081426!important;color-scheme:dark}html[data-theme=light] body .attribute-editor .pf-hero{background:#e6f0fd!important;color:#193a60!important}html[data-theme=light] body .attribute-editor>a.pf-card{background:#fff!important}.attribute-editor{min-width:0}.ae-field-filters{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:12px}.ae-field-count{font-size:13px;overflow-wrap:anywhere}@media(max-width:600px){.ae-field-filters{grid-template-columns:minmax(0,1fr);gap:0}}.ae-manual-row{min-width:0;border:1px solid #426184;border-radius:10px;padding:12px;margin:12px 0}.ae-manual button{margin:5px 8px 5px 0}.ae-manual [hidden]{display:none!important}.ae-manual input[name=manual_value]:placeholder-shown{border:1px solid #f19c9c}.ae-manual input[name=manual_value]::placeholder{color:#ffb4b4;opacity:1}@layer keiper-appearance{html[data-theme=light] body .ae-manual input[name=manual_value]:placeholder-shown{border-color:#b4232b!important}html[data-theme=light] body .ae-manual input[name=manual_value]::placeholder{color:#a51d28!important}}.ae-manual label{display:block;margin:12px 0}.ae-manual :is(input,select){display:block;box-sizing:border-box;width:100%;max-width:100%;min-width:0;padding:10px}.attribute-editor form{margin:12px 0}.ae-proposal{border:1px solid #426184;border-radius:12px;padding:16px;margin:14px 0;overflow-wrap:anywhere}.ae-proposal label{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-weight:700}.ae-proposal small{font-size:12px}.ae-diff{display:flex;flex-direction:column;gap:8px;margin:12px 0}.ae-proposal blockquote{margin:10px 0;border-left:3px solid #7892aa;padding-left:12px;white-space:pre-wrap;overflow-wrap:anywhere}.ae-hidden{font-size:11px;padding:4px 8px;border:1px solid #4a9ccc;border-radius:6px}.ae-verification h5{font-size:16px;margin:0 0 8px}.ae-verified-field{border:1px solid #426184;border-radius:12px;padding:16px;margin:12px 0;overflow-wrap:anywhere}.ae-verified-field dl{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:16px 0 0}.ae-verified-field dt{font-size:12px;opacity:.8}.ae-verified-field dd{margin:6px 0;font-weight:600}.attribute-editor .ae-confirmed{color:#78dfb0!important}.attribute-editor .ae-unconfirmed{color:#ffd28a!important}@layer keiper-appearance{html[data-theme=light] body .attribute-editor .ae-confirmed{color:#17633e!important}html[data-theme=light] body .attribute-editor .ae-unconfirmed{color:#825011!important}}@media(max-width:600px){.ae-verified-field dl{grid-template-columns:minmax(0,1fr);gap:8px}}.ae-history{display:block;padding:12px;margin:8px 0;border:1px solid #426184;border-radius:8px}.ae-conditional{border:1px solid #426184;border-radius:10px;padding:12px;margin:12px 0;overflow-wrap:anywhere}.ae-conditional li{margin:10px 0}.ae-blocked{border-left:3px solid #c08d54;padding-left:12px}.attribute-editor :is(button,strong){overflow-wrap:anywhere;white-space:normal}.attribute-editor button{max-width:100%}</style>'''

STYLE+='''<style>.attribute-editor{max-width:960px}.attribute-editor .pf-hero{background:transparent;border:0;padding:8px 0 18px;margin:0}.attribute-editor .pf-hero h2{font-size:24px}.attribute-editor .pf-hero p{margin:6px 0}.attribute-editor .ae-analysis{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 20px}.attribute-editor .ae-analysis h3{font-size:14px;margin:0}.attribute-editor .ae-analysis form{margin:0}.attribute-editor .pf-card{border-radius:12px;padding:20px}.attribute-editor h3{font-size:16px;margin-top:0}.attribute-editor .ae-pending-summary{font-size:13px;margin:8px 0 16px}.attribute-editor .ae-compact-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.attribute-editor .ae-compact label{font-size:14px}.attribute-editor .ae-compact input:placeholder-shown{border-color:#f19c9c}.attribute-editor .ae-compact input::placeholder{color:#ffb4b4;opacity:1}.attribute-editor .ae-compact button{margin-top:18px}.attribute-editor .ae-manual{margin-top:20px;border-top:1px solid var(--pf-line);padding-top:16px}.attribute-editor summary{cursor:pointer;font-size:13px;color:var(--pf-muted)}.attribute-editor .ae-source summary{font-size:12px}.attribute-editor .ae-proposal{border:0;border-bottom:1px solid var(--pf-line);border-radius:0;padding:14px 0;margin:0}.attribute-editor .ae-proposal input[type=checkbox]{width:auto;margin:0}.attribute-editor .ae-diff{margin:8px 0}.attribute-editor .ae-details{padding:16px 20px}.attribute-editor .ae-details[open]>summary{margin-bottom:20px}.attribute-editor .ae-compact input{min-height:44px}.attribute-editor .ae-compact small{display:block;font-size:12px;margin-top:6px}@layer keiper-appearance{html[data-theme=light] body .attribute-editor .pf-hero{background:transparent!important}html[data-theme=light] body .attribute-editor .ae-compact input:placeholder-shown{border-color:#b4232b!important}html[data-theme=light] body .attribute-editor .ae-compact input::placeholder{color:#a51d28!important}}@media(max-width:600px){.attribute-editor .ae-compact-grid{grid-template-columns:minmax(0,1fr)}.attribute-editor .ae-analysis{align-items:flex-start;flex-direction:column}.attribute-editor .pf-card{padding:16px}.attribute-editor .pf-hero h2{font-size:22px}}</style>'''

STYLE+='''<style>.attribute-editor .ae-compact{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:start;gap:10px;margin:0}.attribute-editor .ae-compact-grid{display:grid;grid-template-columns:minmax(0,1fr);gap:10px}.attribute-editor .ae-compact label{display:grid;grid-template-columns:minmax(100px,180px) minmax(0,1fr);align-items:center;gap:12px;margin:0;min-width:0}.attribute-editor .ae-compact input{margin:0;min-height:40px;padding:9px 12px}.attribute-editor .ae-compact button{margin:0;min-height:40px;padding:9px 14px;white-space:nowrap}.attribute-editor .ae-manual{margin-top:12px;padding-top:12px}.attribute-editor .ae-details{padding:12px 20px}.attribute-editor .ae-history{padding:10px 20px}.attribute-editor .ae-compact-limit{grid-column:1/-1;margin:0;font-size:12px}@media(max-width:600px){.attribute-editor .ae-compact label{grid-template-columns:minmax(0,1fr);gap:5px}.attribute-editor .ae-compact button{align-self:end}.attribute-editor .ae-compact-grid{gap:12px}.attribute-editor .ae-compact:has(label:nth-child(2)) button{align-self:start;margin-top:23px}.attribute-editor .ae-compact button{padding:9px 10px}}</style>'''

STYLE+='''<style>.attribute-editor .ae-apply:not(:has(.ae-proposal)){display:none}</style>'''

STYLE+='''<style>.attribute-editor .ae-compact{display:block}.attribute-editor .ae-field-group{margin:0 0 18px}.attribute-editor .ae-field-group:last-child{margin-bottom:0}.attribute-editor .ae-field-group h3{font-size:15px;margin:0 0 12px}.attribute-editor .ae-compact-row{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:start;gap:10px;min-width:0}.attribute-editor .ae-compact .ae-compact-row button{margin:0}@media(max-width:600px){.attribute-editor .ae-compact .ae-compact-row button{align-self:end;margin:0}}</style>'''
