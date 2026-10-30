"""Evidence-first content checklist. Verdicts are manual, never an AI score."""
from html import escape
from datetime import datetime
import secrets
from sales_metrics import SAO_PAULO
from listing_content import CRITERIA,STATES
from listing_calendar import STYLE


def render(cid,item,shop,model,token,values=None,message=''):
    values=values or {};esc=lambda v:escape(str(v),quote=True)
    path=f'/anuncios/{int(cid)}/{item}/conteudo'
    def when(row):return datetime.fromtimestamp(row['created_at'],SAO_PAULO).strftime('%d/%m/%Y %H:%M')
    out=STYLE+EXTRA+'<section class="lc content-review"><h2>Revisão de conteúdo</h2><p>'+esc(shop.get('titulo') or item)+' · '+esc(item)+'</p><p>Avaliação manual com evidências. Nenhum critério é aprovado automaticamente. A revisão descreve o que foi conferido naquela data; não comprova o conteúdo atual nem garante conversão.</p><nav><a href="/diagnostico/'+str(int(cid))+'/'+item+'">Diagnóstico</a><a href="/anuncios/'+str(int(cid))+'/'+item+'/tarefas">Planejar ajustes</a></nav>'
    photos=shop.get('fotos');clips=shop.get('clips')
    out+='<p><a href="/anuncios/'+str(int(cid))+'/'+item+'/conteudo-atual">Conferir conteúdo atual no Mercado Livre ↗</a></p>'
    out+='<p><a href="/anuncios/'+str(int(cid))+'/'+item+'/perguntas">Consultar perguntas registradas</a></p>'
    out+='<p>Última contagem coletada: fotos '+esc(photos if photos is not None else 'não verificadas')+' · clips '+esc(clips if clips is not None else 'não verificados')+'. Contagem não mede qualidade. Confira o anúncio antes de registrar.</p>'
    if message:out+='<p role="status">'+esc(message)+'</p>'
    counts={s:sum(r['verdict']==s for r in model['latest'].values()) for s in STATES}
    out+='<div class="cr-counts">'+''.join('<article><strong>'+str(n)+'</strong><span>'+label+'</span></article>' for label,n in [('Sem revisão',len(CRITERIA)-len(model['latest'])),('Conferidos',counts['approved']),('Para ajustar',counts['revise']),('Não se aplicam',counts['na'])])+'</div>'
    for code,(label,prompt) in CRITERIA.items():
        row=model['latest'].get(code);failed=values.get('criterion')==code
        out+='<article class="cr-criterion"><h3>'+label+'</h3><p>'+prompt+'</p>'
        if row:out+='<p><strong>'+STATES[row['verdict']]+'</strong> · '+when(row)+' · Usuário #'+str(row['created_by'])+'</p><p class="cr-note">'+esc(row['note'])+'</p>'
        else:out+='<p>Sem revisão registrada.</p>'
        out+='<details'+(' open' if failed else '')+'><summary>Registrar nova revisão</summary><form method="post">'
        # Preserve the stale expected version on failed submission: an explicit reload is needed.
        expected=values.get('expected','0') if failed else row['id'] if row else 0
        for name,val in dict(_csrf=token,criterion=code,expected=expected,submission_key=values.get('submission_key','') if failed else secrets.token_urlsafe(24)).items():out+='<input type="hidden" name="'+name+'" value="'+esc(val)+'">'
        out+='<label>Resultado<select name="verdict" required><option value="">Selecione</option>'+''.join('<option value="'+s+'"'+(' selected' if failed and values.get('verdict')==s else '')+'>'+l+'</option>' for s,l in STATES.items())+'</select></label><label class="cr-evidence">Evidência ou justificativa<textarea name="note" required minlength="10" maxlength="1500" rows="3">'+esc(values.get('note','') if failed else '')+'</textarea></label><button>Salvar revisão</button></form></details></article>'
    out+='<section id="lc-historico"><h3>Histórico de revisões</h3><p>Datas em Brasília. Registros anteriores são preservados. '+str(model['total'])+' revisões.</p>'
    for row in model['history']:out+='<article class="cr-criterion"><strong>'+CRITERIA[row['criterion']][0]+' · '+STATES[row['verdict']]+'</strong><p>'+when(row)+' · Usuário #'+str(row['created_by'])+'</p><p class="cr-note">'+esc(row['note'])+'</p></article>'
    if not model['history']:out+='<p>Nenhuma revisão registrada.</p>'
    out+='<nav aria-label="Paginação do histórico">Página '+str(model['page'])+' de '+str(model['pages'])
    for label,p in [('Anterior',model['page']-1),('Próxima',model['page']+1)]:
        if 1<=p<=model['pages']:out+=' <a href="'+path+'?pagina='+str(p)+'#lc-historico">'+label+'</a>'
    return out+'</nav></section></section>'

EXTRA='''<style>.cr-counts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:16px 0}.cr-counts article,.cr-criterion{background:#182e49;border:1px solid #426184;border-radius:10px;padding:14px;margin:12px 0;overflow-wrap:anywhere}.cr-counts article{display:grid;gap:8px;font-size:12px}.cr-counts strong{font-size:24px}.cr-criterion summary{cursor:pointer;padding:12px 0;color:#b9e5ff}.content-review textarea{width:100%;box-sizing:border-box;background:#0b192c;color:#eaf2ff;border:1px solid #426184;border-radius:8px;padding:10px;font:inherit;resize:vertical}.content-review form{align-items:stretch}.cr-evidence{flex:1;min-width:200px!important}.cr-note{white-space:pre-wrap}.content-review label{max-width:100%}@media(max-width:700px){.cr-counts{grid-template-columns:repeat(2,minmax(0,1fr))}.content-review form{flex-direction:column}}</style>'''
