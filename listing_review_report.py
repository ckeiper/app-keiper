"""Read-only operational listing report, printable through the browser."""
from datetime import datetime
from html import escape
import re
import time
from sales_metrics import SAO_PAULO
from listing_content import CRITERIA,STATES as REVIEW_STATES
from listing_tasks import STATES as TASK_STATES
from listing_priority_sources import listing_signals


def load(conn,query,cid,item):
    shops=query(conn,'''SELECT c.cliente,a.item_id,a.titulo,a.quantidade,a.atualizado_em,a.fotos,a.clips
        FROM conexoes c JOIN anuncios a ON a.conexao_id=c.id WHERE c.id=%s AND a.item_id=%s''',(cid,item))
    if not shops:return None
    reviews=query(conn,'''SELECT DISTINCT ON(criterion) * FROM listing_content_reviews
        WHERE conexao_id=%s AND item_id=%s ORDER BY criterion,id DESC''',(cid,item))
    counts=query(conn,'SELECT status,COUNT(*) AS n FROM listing_tasks WHERE conexao_id=%s AND item_id=%s GROUP BY status',(cid,item))
    tasks=query(conn,'''SELECT id,title,responsible,due_date,status FROM listing_tasks
        WHERE conexao_id=%s AND item_id=%s ORDER BY due_date,id LIMIT 11''',(cid,item))
    questions=query(conn,'SELECT status,COUNT(*) AS n FROM perguntas WHERE conexao_id=%s AND item_id=%s GROUP BY status',(cid,item))
    return dict(shop=shops[0],reviews={r['criterion']:r for r in reviews},counts=counts,tasks=tasks[:10],tasks_limited=len(tasks)>10,questions=questions)


def render(cid,item,data,now):
    esc=lambda v:escape(str(v),quote=True);shop=data['shop']
    def stamp(v):
        try:return datetime.fromtimestamp(int(v),SAO_PAULO).strftime('%d/%m/%Y %H:%M')
        except (ValueError,TypeError,OverflowError,OSError):return 'não verificada'
    signal=listing_signals([shop],{},1,now=now)[item]
    stock=str(int(signal['stock'])) if signal['stock_verified'] else 'não verificado (leitura ausente, inválida ou superior a seis horas)'
    out='<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Revisão do anúncio '+esc(item)+'</title>'+STYLE+'</head><body><main class="lr-report"><nav class="lr-controls"><a href="/diagnostico/'+str(int(cid))+'/'+item+'">Voltar ao diagnóstico</a><button type="button" onclick="window.print()">Imprimir / Salvar como PDF</button></nav><header><p class="lr-brand">KEIPER CONSULTORIA</p><h1>Relatório de revisão do anúncio</h1><p>'+esc(shop['cliente'])+' · '+esc(item)+'</p><h2>'+esc(shop.get('titulo') or 'Título não informado')+'</h2><p>Emitido em '+stamp(now)+' · Brasília</p><p>Escopo: situação operacional registrada nesta emissão. Não certifica histórico integral, rentabilidade ou causas de variação de vendas. Para exportar, escolha Salvar como PDF na janela de impressão do navegador.</p></header><section><h2>Leitura do catálogo</h2><p>Fonte: catálogo sincronizado · coleta '+stamp(shop.get('atualizado_em'))+'.</p><p>Estoque observado: '+stock+'. Não representa inventário por variação/Full nem previsão de ruptura.</p><p>Fotos registradas: '+esc(shop.get('fotos') if shop.get('fotos') is not None else 'não verificadas')+' · clips: '+esc(shop.get('clips') if shop.get('clips') is not None else 'não verificados')+'. Quantidade não mede qualidade.</p></section><section><h2>Checklist de conteúdo</h2><p>Última revisão manual de cada critério. Pareceres datados não certificam o conteúdo atual da oferta.</p>'
    for code,(label,_) in CRITERIA.items():
        r=data['reviews'].get(code)
        out+='<article><h3>'+label+'</h3>'
        if r:out+='<p>'+REVIEW_STATES[r['verdict']]+' · '+stamp(r['created_at'])+' · Usuário #'+str(r['created_by'])+'</p><p class="lr-note">'+esc(r['note'])+'</p>'
        else:out+='<p>Sem revisão registrada.</p>'
        out+='</article>'
    out+='</section><section><h2>Tarefas e próximos passos</h2><p>Fonte: tarefas internas deste anúncio. Concluir uma tarefa não comprova alteração executada no marketplace.</p><p>'+esc(' · '.join(TASK_STATES[r['status']]+': '+str(r['n']) for r in data['counts']) or 'Nenhuma tarefa registrada')+'</p>'
    if data['tasks_limited']:out+='<p class="lr-limit">Exibidas as primeiras dez tarefas por prazo e identificador. Consulte a tela de tarefas para a lista completa; os totais acima incluem todas.</p>'
    for r in data['tasks']:out+='<article><h3>'+esc(r['title'])+'</h3><p>Prazo: '+r['due_date'].strftime('%d/%m/%Y')+' · '+TASK_STATES[r['status']]+' · responsável: '+esc(r['responsible'])+' · tarefa #'+str(r['id'])+'</p></article>'
    out+='</section><section><h2>Perguntas registradas</h2><p>Fonte: base local de perguntas. A coleta consulta até 50 perguntas por loja por atualização; a base preservada pode conter status antigos. Ausência de registros não comprova ausência de dúvidas. Avaliações de compradores não integram este relatório.</p>'
    out+='<p>'+esc(' · '.join((r['status'] or 'Status não informado')+': '+str(r['n']) for r in data['questions']) or 'Nenhuma pergunta registrada')+'</p></section><footer>Keiper Consultoria · '+esc(item)+' · emissão '+stamp(now)+' · dados restritos ao anúncio e à loja identificados.</footer></main></body></html>'
    return out


def register_report(app,login_required,can_view,bank,query,execute):
    from flask import session
    @app.route('/anuncios/<int:cid>/<item_id>/relatorio-revisao',methods=['GET'])
    @login_required
    def listing_operational_report(cid,item_id):
        if session.get('tipo')!='admin' or not can_view(cid):return 'Acesso restrito',403
        if not re.fullmatch(r'MLB[0-9]{1,20}',item_id):return 'Anúncio não encontrado',404
        with bank() as conn:
            execute(conn,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            data=load(conn,query,cid,item_id)
        if data is None:return 'Anúncio não encontrado nesta loja.',404
        return render(cid,item_id,data,int(time.time()))

STYLE='''<style>*{box-sizing:border-box}body{margin:0;background:#0b1426;color:#eaf2ff;font:14px/1.6 Arial,sans-serif}.lr-report{max-width:980px;margin:24px auto;padding:24px;background:#102238;border:1px solid #34516e;border-radius:14px}h1{font-size:26px}h2{font-size:20px}h3{font-size:15px}p{color:#bdcce1}header,section{border-bottom:1px solid #426184;padding:12px 0}article{background:#182e49;border:1px solid #426184;border-radius:8px;padding:12px;margin:12px 0;overflow-wrap:anywhere}.lr-note{white-space:pre-wrap}.lr-brand{font-weight:bold;letter-spacing:2px}.lr-controls{display:flex;gap:14px;align-items:center;flex-wrap:wrap}.lr-controls a{color:#b9e5ff}.lr-controls button{background:#287ac1;color:white;border:0;border-radius:8px;padding:12px;cursor:pointer}footer{font-size:11px;margin-top:20px;overflow-wrap:anywhere}:focus-visible{outline:3px solid #85c8ec;outline-offset:3px}@media(max-width:700px){.lr-report{margin:12px;padding:16px}h1{font-size:22px}}@page{size:A4;margin:14mm}@media print{body{background:white;color:#17283d;font-size:10pt;line-height:1.45}.lr-report{max-width:none;margin:0;padding:0;border:0;border-radius:0;background:white;color:#17283d}.lr-controls{display:none}p{color:#263b50}h1{font-size:18pt}h2{font-size:14pt;break-after:avoid}h3{font-size:11pt;break-after:avoid}article{background:white;border-color:#a9b8c5;break-inside:avoid;padding:8px;margin:8px 0}header,section{border-color:#a9b8c5}footer{font-size:8pt}}</style>'''
