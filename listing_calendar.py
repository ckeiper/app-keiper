"""Read-only calendar of deadlines entered in listing tasks."""
import calendar
from datetime import date
from html import escape
from urllib.parse import urlencode
from listing_tasks import STATES


def load(conn,query,cid,item,args,today):
    raw=args.get('mes',today.strftime('%Y-%m'))
    try:
        if len(raw)!=7:raise ValueError
        first=date.fromisoformat(raw+'-01')
        if not 2000<=first.year<=2100:raise ValueError
    except (ValueError,TypeError):raise ValueError('Informe um mês entre 2000-01 e 2100-12.') from None
    end=date(first.year+1,1,1) if first.month==12 else date(first.year,first.month+1,1)
    status=args.get('status','open')
    if status not in (*STATES,'all'):status='open'
    where='conexao_id=%s AND item_id=%s AND due_date>=%s AND due_date<%s'
    params=[cid,item,first,end]
    if status!='all':where+=' AND status=%s';params.append(status)
    counts=query(conn,'SELECT due_date,COUNT(*) AS n FROM listing_tasks WHERE '+where+' GROUP BY due_date',tuple(params))
    total=sum(row['n'] for row in counts);pages=max(1,(total+9)//10)
    try:page=max(1,min(pages,int(args.get('pagina','1'))))
    except (ValueError,TypeError):page=1
    rows=query(conn,'SELECT id,title,responsible,due_date,status FROM listing_tasks WHERE '+where+' ORDER BY due_date,id LIMIT 10 OFFSET %s',tuple(params+[(page-1)*10]))
    return dict(first=first,status=status,counts={r['due_date']:r['n'] for r in counts},total=total,pages=pages,page=page,rows=rows)


def render(cid,item,shop,model,today):
    esc=lambda s:escape(str(s),quote=True)
    path=f'/anuncios/{int(cid)}/{item}/calendario';tasks=f'/anuncios/{int(cid)}/{item}/tarefas'
    first=model['first'];month=first.strftime('%Y-%m')
    def url(**changes):return esc(path+'?'+urlencode(dict(mes=month,status=model['status'],**changes)))
    out=STYLE+'<section class="lc"><h2>Calendário do anúncio</h2><p>'+esc(shop.get('titulo') or item)+' · '+esc(item)+'</p><a href="'+tasks+'">Gerenciar tarefas e responsáveis</a><p>Prazos informados nas tarefas · Brasília. Não executa alterações no Mercado Livre. Atrasadas: tarefas abertas com prazo anterior a hoje.</p><form method="get"><label>Mês<input type="month" name="mes" min="2000-01" max="2100-12" required value="'+month+'"></label><label>Status<select name="status">'
    out+=''.join('<option value="'+s+'"'+(' selected' if model['status']==s else '')+'>'+label+'</option>' for s,label in [('open','Abertas'),('done','Concluídas'),('cancelled','Canceladas'),('all','Todas')])+'</select></label><button>Exibir</button></form>'
    out+='<p>'+str(model['total'])+' tarefas no mês e filtro selecionados. O calendário inclui todas as páginas da agenda.</p><div class="lc-grid" role="list" aria-label="Dias do mês">'
    for day in range(1,calendar.monthrange(first.year,first.month)[1]+1):
        d=date(first.year,first.month,day);n=model['counts'].get(d,0)
        out+='<div role="listitem" class="lc-day'+(' lc-today' if d==today else '')+'"><strong>'+d.strftime('%d/%m')+'</strong><small>'+('Seg','Ter','Qua','Qui','Sex','Sáb','Dom')[d.weekday()]+'</small><span>'+str(n)+' tarefas</span>'+('<small>Hoje</small>' if d==today else '')+'</div>'
    out+='</div><h3>Agenda do mês</h3>'
    if not model['rows']:out+='<p>Nenhuma tarefa neste mês e filtro.</p>'
    for row in model['rows']:
        link=tasks+'?status=all&tarefa='+str(int(row['id']))+'#lt-historico'
        out+='<a class="lc-task" href="'+esc(link)+'"><strong>'+esc(row['title'])+'</strong><span>'+esc(row['responsible'])+'</span><span>'+row['due_date'].strftime('%d/%m/%Y')+' · '+STATES[row['status']]+(' · Atrasada' if row['status']=='open' and row['due_date']<today else '')+'</span></a>'
    out+='<nav aria-label="Paginação da agenda">Página '+str(model['page'])+' de '+str(model['pages'])
    for label,p in [('Anterior',model['page']-1),('Próxima',model['page']+1)]:
        if 1<=p<=model['pages']:out+=' <a href="'+url(pagina=p)+'">'+label+'</a>'
    return out+'</nav></section>'

STYLE='''<style>.lc{background:#102238;color:#eaf2ff;border:1px solid #34516e;border-radius:15px;padding:20px;min-width:0;box-sizing:border-box}.lc :is(h2,h3,strong){color:#eaf2ff!important}.lc p,.lc small{color:#bdcce1;line-height:1.6;font-size:12px}.lc a{color:#b9e5ff!important;text-decoration:none}.lc form{display:flex;gap:12px;flex-wrap:wrap;align-items:end;margin:16px 0}.lc label{display:grid;gap:6px;font-size:12px;min-width:0}.lc input,.lc select{background:#0b192c;color:#eaf2ff;color-scheme:dark;border:1px solid #426184;padding:10px;border-radius:8px;max-width:100%;box-sizing:border-box}.lc button{background:#287ac1;color:white;padding:11px;border:0;border-radius:8px}.lc-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:8px;margin:16px 0}.lc-day{background:#182e49;border:1px solid #426184;border-radius:8px;padding:10px;display:grid;gap:5px;font-size:12px;overflow-wrap:anywhere}.lc-today{border:2px solid #85c8ec}.lc-task{display:grid;gap:8px;padding:14px;background:#182e49;border:1px solid #426184;border-radius:10px;margin:12px 0;overflow-wrap:anywhere;font-size:12px}.lc :focus-visible{outline:3px solid #85c8ec;outline-offset:3px}.lc nav{display:flex;gap:14px;flex-wrap:wrap;font-size:12px}@media(max-width:700px){.lc-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.lc{padding:12px}}@media(max-width:360px){.lc-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}</style>'''
