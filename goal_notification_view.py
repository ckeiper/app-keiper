"""Administrator's own opt-in and notification attempt history."""
from datetime import datetime
from html import escape
from listing_calendar import STYLE
from sales_metrics import SAO_PAULO
from goal_notifications import email_valid


def render(cid,item,kind,goal,email,subscription,history,token,ready,message=''):
    esc=lambda v:escape(str(v),quote=True)
    base=f'/anuncios/{int(cid)}/{item}/'+('metas' if kind=='stock' else 'metas-vendas')
    active=bool(subscription and subscription['enabled'] and subscription['email']==email)
    out=STYLE+'''<style>.goal-notifications{overflow-wrap:anywhere}.goal-notifications article{border:1px solid #426184;border-radius:10px;padding:14px;margin:14px 0}.goal-notifications .gn-choice{display:flex;align-items:start;gap:10px;line-height:1.6}.goal-notifications input[type=checkbox]{width:20px;height:20px;flex:none}.goal-notifications form{align-items:stretch}.goal-notifications button{width:fit-content}@media(max-width:700px){.goal-notifications form{flex-direction:column}}</style>'''
    out+='<section class="lc goal-notifications"><h2>Avisos por e-mail</h2><nav><a href="'+base+'">Voltar às metas</a></nav><p>'+esc(item)+' · Meta #'+str(goal['id'])+' · '+('Estoque mínimo' if kind=='stock' else 'Vendas')+'</p>'
    if message:out+='<p role="alert">'+esc(message)+'</p>'
    out+='<p><strong>'+('Ativados para sua conta' if active else 'Desativados')+'</strong></p>'
    out+='<p>Destinatário: '+(esc(email) if email_valid(email) else 'cadastre um e-mail válido na sua conta administrativa')+'.</p>'
    if not ready:out+='<p>Envio indisponível: SMTP ainda não configurado. Nenhuma tentativa será feita até a configuração estar disponível.</p>'
    if subscription and subscription['enabled'] and subscription['email']!=email:out+='<p>O e-mail da conta mudou. Confira o endereço e autorize novamente; o endereço anterior não receberá novos avisos.</p>'
    if goal.get('cancelled_at') is not None:out+='<p>Meta cancelada: novos envios bloqueados.</p>'
    out+='<form method="post"><input type="hidden" name="_csrf" value="'+esc(token)+'"><input type="hidden" name="confirmed_email" value="'+esc(email or '')+'">'
    out+='<label class="gn-choice"><input type="checkbox" name="enabled" value="yes"'+(' checked' if active else '')+(' disabled' if not email_valid(email) or goal.get('cancelled_at') is not None else '')+'>Autorizo receber alertas desta meta no e-mail da minha conta indicado acima.</label><button>Salvar preferência</button></form>'
    out+='<p>Desativado por padrão. A ativação aguarda uma nova avaliação elegível da sincronização. No máximo uma tentativa por dia de Brasília, por meta e conta. Cancelamento, loja inativa, mudança de e-mail ou avaliação mais recente sem alerta impedem novas tentativas. Uma tentativa já iniciada pode terminar após a desativação.</p>'
    out+='<p>'+('Estoque: avaliação de alerta e leitura do catálogo com até seis horas, coincidente com a leitura atual. Não prevê ruptura.' if kind=='stock' else 'Vendas: meta abaixo do objetivo somente após o prazo, com cobertura completa e avaliação de até 24 horas. Reavaliações até 30 dias após o fim.')+'</p>'
    out+='<h3>Histórico das tentativas</h3><p>Aceito pelo SMTP não confirma entrega à caixa de entrada. Resultado incerto não é repetido automaticamente no mesmo dia.</p>'
    labels={'sending':'Iniciada · resultado ainda não confirmado','accepted':'Aceito pelo SMTP · entrega não confirmada','uncertain':'Resultado incerto · sem repetição automática'}
    for row in history['rows']:
        stamp=datetime.fromtimestamp(row['attempted_at'],SAO_PAULO).strftime('%d/%m/%Y %H:%M:%S')
        out+='<article><strong>'+labels[row['state']]+'</strong><p>'+stamp+' · Brasília</p></article>'
    if not history['rows']:out+='<p>Nenhuma tentativa registrada.</p>'
    out+='<nav aria-label="Paginação das tentativas">Página '+str(history['page'])+' de '+str(history['pages'])
    for label,p in [('Anterior',history['page']-1),('Próxima',history['page']+1)]:
        if 1<=p<=history['pages']:out+=' <a href="?pagina='+str(p)+'">'+label+'</a>'
    return out+'</nav></section>'
