"""A human-controlled plan. Elapsed time is never task completion."""
from datetime import timedelta
from html import escape
import secrets
from listing_calendar import STYLE
from listing_tasks import STATES
from listing_onboarding import STEPS


def render(cid,item,shop,data,today,token,values=None,message=''):
    esc=lambda v:escape(str(v),quote=True);values=values or {};path=f'/anuncios/{int(cid)}/{item}'
    out=STYLE+'''<style>.ob-stages{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.ob-stage,.ob-summary{background:#182e49;border:1px solid #426184;border-radius:10px;padding:16px;margin:14px 0;overflow-wrap:anywhere}.ob-stage{margin:0}.ob-stage a{display:block;margin-top:12px}.ob-progress{width:100%;accent-color:#60baff}.onboarding form{align-items:end}.onboarding label{max-width:100%}.onboarding input{min-width:0}@media(max-width:700px){.ob-stages{grid-template-columns:1fr}.onboarding form{flex-direction:column;align-items:stretch}}</style>'''
    out+='<section class="lc onboarding"><h2>Primeiros 30 dias</h2><p>'+esc(shop.get('titulo') or item)+' · '+esc(item)+'</p><nav><a href="'+path+'/tarefas">Tarefas e histórico</a><a href="'+path+'/calendario">Calendário</a><a href="'+path+'/conteudo">Checklist de conteúdo</a><a href="'+path+'/perguntas">Perguntas</a></nav><p>Plano interno de revisão em quatro etapas. O início é informado pelo administrador e não representa a data oficial de publicação do anúncio. Criar o plano não altera o marketplace; passar um prazo não conclui tarefas.</p>'
    if message:out+='<p role="status">'+esc(message)+'</p>'
    if not data['plan']:
        out+='<h3>Planejar acompanhamento</h3><p>Será criado um único plano para este anúncio, com quatro tarefas e prazos nos dias 1, 7, 14 e 30. Início e responsável ficam preservados; os status podem ser gerenciados nas tarefas.</p><form method="post"><input type="hidden" name="_csrf" value="'+esc(token)+'"><input type="hidden" name="submission_key" value="'+esc(values.get('submission_key') or secrets.token_urlsafe(24))+'"><label>Início do acompanhamento · Brasília<input type="date" name="start_date" min="'+(today-timedelta(days=90)).isoformat()+'" max="'+(today+timedelta(days=90)).isoformat()+'" required value="'+esc(values.get('start_date',''))+'"></label><label>Responsável informado<input name="responsible" required maxlength="80" value="'+esc(values.get('responsible',''))+'"></label><button>Criar plano e quatro tarefas</button></form><h3>Etapas previstas</h3><div class="ob-stages">'
        for offset,title,description in STEPS:out+='<article class="ob-stage"><strong>Dia '+str(offset+1)+' · '+title+'</strong><p>'+description+'</p></article>'
        return out+'</div></section>'
    plan=data['plan'];steps=data['steps'];done=sum(r['status']=='done' for r in steps);cancelled=sum(r['status']=='cancelled' for r in steps)
    overdue=sum(r['status']=='open' and r['due_date']<today for r in steps)
    elapsed=(today-plan['start_date']).days+1
    label='Acompanhamento ainda não iniciado' if elapsed<1 else 'Janela de 30 dias encerrada' if elapsed>30 else 'Dia '+str(elapsed)+' de 30'
    out+='<div class="ob-summary"><strong>'+label+'</strong><p>Início informado: '+plan['start_date'].strftime('%d/%m/%Y')+' · término: '+(plan['start_date']+timedelta(days=29)).strftime('%d/%m/%Y')+' · responsável: '+esc(plan['responsible'])+'</p><label for="ob-progress">'+str(done)+' de 4 etapas concluídas</label><progress class="ob-progress" id="ob-progress" value="'+str(done)+'" max="4">'+str(done)+'/4</progress><p>'+str(overdue)+' atrasadas · '+str(cancelled)+' canceladas. Cancelamentos não contam como conclusão.</p></div>'
    if len(steps)!=4:out+='<p role="status">Vínculos de tarefas incompletos. O progresso não certifica a conclusão do plano; confira o histórico antes de agir.</p>'
    out+='<div class="ob-stages">'
    for row in steps:
        out+='<article class="ob-stage"><strong>Dia '+str(STEPS[row['step']][0]+1)+' · '+esc(row['title'])+'</strong><p>Prazo: '+row['due_date'].strftime('%d/%m/%Y')+' · '+STATES[row['status']]+(' · Atrasada' if row['status']=='open' and row['due_date']<today else '')+'</p><p>Responsável: '+esc(row['responsible'])+'</p><p>'+esc(row['description'])+'</p><a href="'+path+'/tarefas?status=all&amp;tarefa='+str(row['id'])+'#lt-historico">Gerenciar etapa e consultar histórico</a></article>'
    return out+'</div></section>'
