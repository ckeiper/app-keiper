"""Freight audit presentation. All calculations and writes stay in existing services."""
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from html import escape
from freight_comparison import format_brl
from sales_metrics import SAO_PAULO, reporting_today


def esc(value):
    return escape(str(value),quote=True)


def summary(report):
    value=report['resumo']
    return json.loads(value) if isinstance(value,str) else value


def day(value):
    try:return date.fromisoformat(str(value)).strftime('%d/%m/%Y')
    except (ValueError,TypeError):return 'Data não informada'


def period(data):
    return day(data.get('period_start'))+' a '+day(data.get('period_end'))


def imported(value):
    try:
        stamp=value if isinstance(value,datetime) else datetime.fromisoformat(str(value))
        return stamp.astimezone(SAO_PAULO).strftime('%d/%m/%Y às %H:%M') if stamp.tzinfo else 'Horário não verificado'
    except (ValueError,TypeError):return 'Horário não informado'


def history(reports):
    out="<section class='fa-panel' id='fa-history'><div class='fa-section-head'><div><span class='fa-kicker'>Histórico preservado</span><h3>Importações desta loja</h3></div><span class='fa-tag'>Últimos 10 registros</span></div>"
    if not reports:
        return out+"<div class='fa-empty'><span class='fa-empty-mark' aria-hidden='true'>＋</span><h4>Seu primeiro relatório começa aqui</h4><p>Importe uma planilha para guardar os indicadores desta loja e consultar os períodos depois.</p><a href='#fa-upload'>Selecionar relatório</a></div></section>"
    out+="<div class='fa-table-scroll' role='region' aria-label='Histórico de importações' tabindex='0'><table class='fa-history-table'><thead><tr><th>Período do relatório</th><th>Lançamentos</th><th>Frete informado</th><th>Importado em · Brasília</th></tr></thead><tbody>"
    for report in reports:
        data=summary(report)
        label=esc(period(data))
        if report.get('id'):label='<a href="?relatorio='+str(int(report['id']))+'#fa-differences">'+label+'</a>'
        out+='<tr><th scope="row">'+label+'</th><td>'+str(int(data['rows']))+'</td><td>'+format_brl(data['seller_shipping_total'])+'</td><td>'+esc(imported(report.get('importado_em')))+'</td></tr>'
    return out+"</tbody></table></div><p class='fa-caption'>Cada linha é um relatório independente. Períodos sobrepostos não são somados; importar não atualiza pedidos nem a coleta diária.</p></section>"


def coverage(reports,today=None):
    today=today or reporting_today()
    covered={str(row['dia'])[:10] for row in reports}
    total=sum((Decimal(summary(row)['seller_shipping_total']) for row in reports),Decimal('0'))
    count=len(reports)
    out="<section class='fa-panel' id='fa-coverage'><div class='fa-section-head'><div><span class='fa-kicker'>Relatórios completos confirmados</span><h3>Consolidação dos últimos 30 dias</h3></div><span class='fa-tag'>"+str(count)+" / 30 dias</span></div><div class='fa-coverage-grid'><div><strong class='fa-large'>"+(format_brl(total) if count else 'Sem cobertura')+"</strong><p>Frete informado nos dias cobertos</p></div><div class='fa-days' aria-label='Cobertura diária dos últimos 30 dias'>"
    for i in range(30):
        current=today-timedelta(days=29-i);known=current.isoformat() in covered
        label=current.strftime('%d/%m/%Y')+(' · com relatório confirmado' if known else ' · sem relatório')
        out+="<span class='fa-day"+(' is-covered' if known else '')+"' title='"+esc(label)+"' aria-label='"+esc(label)+"'></span>"
    return out+"</div></div><p class='fa-caption'>"+str(count)+" de 30 dias com relatório completo confirmado. Dias sem relatório não são considerados zero. A consolidação substitui somente os dias confirmados e preserva os demais.</p></section>"


def upload(csrf,admin):
    out="<section class='fa-panel fa-upload' id='fa-upload'><div class='fa-section-head'><div><span class='fa-kicker'>01 · Escolha o relatório</span><h3>Importar e conferir</h3></div><span class='fa-tag'>XLSX ou CSV · até 2 MB</span></div><form id='frete-upload-form' method='post' enctype='multipart/form-data'><input type='hidden' name='csrf_token' value='"+esc(csrf)+"'><label class='fa-file' for='fa-file'><span class='fa-file-icon' aria-hidden='true'>↑</span><span><strong>Relatório de conciliação por vendas</strong><span>Selecione o arquivo exportado pelo Mercado Livre.</span></span><input id='fa-file' type='file' name='arquivo' accept='.xlsx,.csv' required aria-describedby='fa-file-note'></label><p id='fa-file-note' class='fa-caption fa-file-name'>Nenhum arquivo selecionado.</p><div class='fa-actions'>"
    if admin:out+="<button class='fa-primary' type='submit' name='acao' value='importar'>Analisar diferenças e salvar</button>"
    out+="<button class='fa-secondary' type='submit'>Pré-visualizar planilha</button></div><p class='fa-caption'>Pré-visualizar não salva dados. A análise salva indicadores e a conferência por pedido, sem guardar o arquivo ou dados do comprador. Reenviar o mesmo arquivo atualiza a conferência, sem duplicar a importação.</p>"
    if admin:
        out+="<details class='fa-advanced'><summary>Consolidar relatório completo por dia</summary><p>Use somente se o relatório contém todos os lançamentos do período, sem filtros adicionais. Esta ação substitui os indicadores dos dias informados.</p><div class='fa-date-grid'><label for='fa-start'>Início do período<input id='fa-start' type='date' name='periodo_inicio'></label><label for='fa-end'>Fim do período<input id='fa-end' type='date' name='periodo_fim'></label></div><label class='fa-confirm'><input type='checkbox' name='completo' value='sim'><span>Confirmo que o arquivo contém todos os lançamentos do período informado, sem filtros adicionais.</span></label><p class='fa-caption'>Até 31 dias por arquivo. Dias sem movimentos são tratados como zero apenas com esta confirmação.</p><button class='fa-secondary' type='submit' name='acao' value='consolidar'>Atualizar consolidação diária</button></details>"
    return out+"</form><div id='frete-progresso' class='frete-progresso' role='status' aria-live='polite' hidden><span class='frete-spinner' aria-hidden='true'></span><span><b>Enviando e processando o arquivo…</b><small>Mantenha a página aberta até aparecer o resultado.</small></span></div></section>"


def render_page(csrf,admin,shop,reports=(),days=(),result='',current=None,report_id=None,args=None,cid=0):
    from freight_difference_view import render as render_differences
    selected=current if current is not None else summary(reports[0]) if admin and reports else None
    out=STYLE+"<div class='freight-audit'><header class='fa-hero'><div><span class='fa-kicker'>Conferência de frete por venda</span><h2>Onde o frete está diferente?</h2><p>Compare o valor da planilha com o frete em Vendas e prepare a relação para seus chamados.</p></div><span class='fa-shop'>"+esc(shop)+"</span></header><nav class='fa-tabs' aria-label='Seções da auditoria'><a href='#fa-differences'>Diferenças por venda</a><a href='#fa-upload'>Enviar ou reanalisar relatório</a>"
    if admin:out+="<a href='#fa-history'>Histórico</a>"
    out+='</nav>'+render_differences(selected,cid,report_id,args or {})
    has_comparison=selected and (selected.get('freight_review') or selected.get('sales_comparison'))
    if has_comparison:out+="<details class='fa-upload-toggle'><summary>Enviar ou reanalisar um relatório</summary>"
    out+=upload(csrf,admin)
    if has_comparison:out+='</details>'
    if result:out+="<details class='fa-secondary-panel' id='fa-results'><summary>Ver valores e demais detalhes do arquivo</summary>"+result+'</details>'
    if admin:out+="<details class='fa-secondary-panel'><summary>Histórico de relatórios e cobertura diária</summary>"+history(reports)+coverage(days)+'</details>'
    return out+'</div>'+SCRIPT


STYLE='''<style>
.freight-audit{--fa-bg:#0c1b2e;--fa-panel:#10243a;--fa-line:#2b4762;--fa-text:#e9f2fc;--fa-muted:#abc0d4;--fa-accent:#69d9ec;color:var(--fa-text);max-width:1440px;margin:auto;font-family:Arial,sans-serif;line-height:1.55}
.freight-audit *{box-sizing:border-box}.freight-audit h2,.freight-audit h3,.freight-audit h4,.freight-audit p{margin-top:0}.freight-audit h2{font-size:34px;letter-spacing:-1px;line-height:1.2;margin-bottom:12px}.freight-audit h3{font-size:21px;letter-spacing:-.4px;margin-bottom:8px}.freight-audit p{color:var(--fa-muted)}.freight-audit a{color:var(--fa-accent)}
.fa-hero{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;padding:32px;border:1px solid #345674;border-radius:20px;background:linear-gradient(125deg,#10243a,#1a3c5c)}.fa-hero p{margin:0;max-width:620px}.fa-kicker{display:block;text-transform:uppercase;letter-spacing:1.5px;font-size:10px;font-weight:700;color:var(--fa-accent);margin-bottom:10px}.fa-shop,.fa-tag{padding:7px 12px;border:1px solid #3c5871;border-radius:30px;color:#c2d5e8;font-size:11px;white-space:normal;max-width:100%;overflow-wrap:anywhere}.fa-shop{background:#132b43;font-size:12px}
.fa-tabs{display:flex;gap:22px;flex-wrap:wrap;padding:18px 4px;margin-bottom:2px}.fa-tabs a{font-size:12px;text-decoration:none;padding:4px 0;border-bottom:2px solid transparent}.fa-tabs a:hover{border-color:var(--fa-accent)}
.fa-overview{display:grid;grid-template-columns:1.25fr 1fr 1fr;gap:14px;margin:0 0 24px}.fa-overview article{background:var(--fa-bg);border:1px solid var(--fa-line);border-radius:14px;padding:20px;min-width:0}.fa-overview span{display:block;font-size:11px;color:var(--fa-muted)}.fa-overview strong{display:block;font-size:22px;letter-spacing:-.5px;margin:9px 0;overflow-wrap:anywhere}.fa-overview article:first-child strong{font-size:18px}.fa-overview small{font-size:10px;color:#8ba5bf}
.fa-workspace{display:grid;grid-template-columns:minmax(0,1.8fr) minmax(230px,1fr);gap:20px;align-items:start;margin-bottom:24px}.fa-panel,.fa-guide{background:var(--fa-panel);border:1px solid var(--fa-line);border-radius:18px;padding:26px;min-width:0;margin-bottom:22px}.fa-workspace .fa-panel{margin:0}.fa-section-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:20px}.fa-section-head h3{margin-bottom:0}.fa-guide{background:#0d2035;margin:0}.fa-guide h3{font-size:18px}.fa-guide ol{list-style:none;padding:0;counter-reset:fa-steps;margin:24px 0}.fa-guide li{counter-increment:fa-steps;position:relative;padding:0 0 22px 36px}.fa-guide li:before{content:counter(fa-steps);position:absolute;left:0;top:0;border:1px solid #375b76;border-radius:50%;width:23px;height:23px;text-align:center;font-size:11px;color:var(--fa-accent)}.fa-guide li strong{display:block;font-size:12px;margin-bottom:5px}.fa-guide li span,.fa-guide>p{display:block;font-size:11px;color:var(--fa-muted)}.fa-guide>p{border-top:1px solid var(--fa-line);padding-top:18px;margin:0}
.freight-audit form{display:block;margin:0;padding:0;background:transparent;border:0}.fa-file{display:flex;flex-wrap:wrap;align-items:center;gap:14px;padding:23px;border:1px dashed #527491;border-radius:12px;background:#0b1d30;cursor:pointer}.fa-file>span:nth-child(2){flex:1;min-width:140px}.fa-file strong{display:block;font-size:14px}.fa-file>span>span{display:block;font-size:11px;color:var(--fa-muted);margin-top:5px}.fa-file-icon{width:36px;height:36px;border-radius:10px;background:#1b4058;color:var(--fa-accent);font-size:23px;text-align:center;line-height:36px}.fa-file input{width:100%;max-width:100%;font-size:11px;color:var(--fa-muted);margin-top:12px;background:transparent;border:0;padding:0}.fa-file input::file-selector-button{padding:8px 12px;margin-right:12px;border:1px solid #436783;border-radius:7px;background:#173650;color:#e9f2fc;cursor:pointer}.fa-actions{display:flex;gap:10px;flex-wrap:wrap;margin:22px 0 14px}.freight-audit button{font:inherit;font-size:12px;font-weight:700;padding:12px 16px;border-radius:9px;cursor:pointer;max-width:100%;white-space:normal;line-height:1.4}.freight-audit .fa-primary{background:#6cdeed;border:1px solid #6cdeed;color:#082336;box-shadow:none}.freight-audit .fa-secondary{background:#17334d;border:1px solid #45657f;color:#e4f2fc;box-shadow:none}.freight-audit button:hover{filter:brightness(1.08)}.freight-audit :focus-visible{outline:3px solid #a5ebf3;outline-offset:4px}.fa-caption{font-size:11px;line-height:1.65;color:var(--fa-muted);margin:12px 0 0}.fa-file-name{overflow-wrap:anywhere}.fa-advanced{margin-top:24px;border-top:1px solid var(--fa-line);padding-top:18px}.fa-advanced summary{cursor:pointer;font-size:12px;font-weight:700;color:#bdddea;padding:8px 0}.fa-advanced p{font-size:11px;margin:14px 0}.fa-date-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.fa-date-grid label{font-size:11px;color:var(--fa-muted)}.fa-date-grid input{display:block;width:100%;min-width:0;padding:11px;margin-top:6px;background:#0a1c30;color:var(--fa-text);border:1px solid #45657f;border-radius:8px;color-scheme:dark}.fa-confirm{display:flex;gap:10px;align-items:flex-start;font-size:11px;line-height:1.6;margin:18px 0}.fa-confirm input{flex:none;width:16px;height:16px;accent-color:#64d6e5;margin:2px 0 0}
.fa-table-scroll{overflow-x:auto}.freight-audit table{width:100%;border-collapse:collapse;background:transparent}.fa-history-table{min-width:650px}.freight-audit th,.freight-audit td{padding:16px 12px;border-bottom:1px solid var(--fa-line);text-align:left;color:var(--fa-text);font-size:12px}.freight-audit th{background:#142e48;color:#b5cee3;font-weight:600}.fa-history-table tbody th{background:transparent;color:var(--fa-text)}.fa-empty{text-align:center;padding:24px 16px 12px}.fa-empty-mark{display:inline-block;width:44px;height:44px;border-radius:12px;background:#18394f;color:var(--fa-accent);font-size:24px;margin-bottom:12px}.fa-empty h4{font-size:16px;margin-bottom:10px}.fa-empty p{font-size:12px;max-width:460px;margin:0 auto 16px}.fa-empty a{font-size:12px}
.fa-coverage-grid{display:grid;grid-template-columns:1fr 1fr;align-items:center;gap:24px}.fa-large{font-size:26px;letter-spacing:-.6px}.fa-coverage-grid p{font-size:11px;margin:6px 0 0}.fa-days{display:grid;grid-template-columns:repeat(15,1fr);gap:5px;min-width:0}.fa-day{display:block;height:16px;border:1px solid #34536b;border-radius:3px;background:#192e42}.fa-day.is-covered{background:#66d7e6;border-color:#66d7e6}
.conteudo .freight-audit .card{background:var(--fa-panel);border:1px solid var(--fa-line);border-radius:16px;padding:24px;margin:16px 0;color:var(--fa-text)}.conteudo .freight-audit .card h3,.conteudo .freight-audit .card h4{color:var(--fa-text)}.conteudo .freight-audit .card p{color:var(--fa-muted);font-size:12px}.freight-audit .frete-metricas{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,170px),1fr));gap:12px;margin:20px 0}.freight-audit .frete-metrica{background:#0d1f33;border:1px solid var(--fa-line);border-radius:11px;padding:18px;display:flex;flex-direction:column;gap:10px;min-width:0}.freight-audit .frete-metrica span{font-size:11px;color:var(--fa-muted)}.freight-audit .frete-metrica strong{font-size:23px;color:var(--fa-text);overflow-wrap:anywhere}.freight-audit .frete-detalhes{margin-top:18px;border-top:1px solid var(--fa-line);padding-top:14px}.freight-audit .frete-detalhes summary{color:#a6dbe9;font-size:12px;cursor:pointer}.freight-audit .aviso{background:#17374a;color:#d2edf3;border:1px solid #315c70;border-radius:10px;padding:16px;font-size:12px}.freight-audit #fa-results{margin:28px 0;scroll-margin-top:24px}.freight-audit #fa-results ul{font-size:12px;color:var(--fa-muted)}
.freight-audit .frete-progresso{display:flex;gap:12px;align-items:center;padding:16px;margin-top:20px;background:#173c50;color:#d6f6fa;border:1px solid #326175;border-radius:10px}.freight-audit .frete-progresso[hidden]{display:none}.freight-audit .frete-progresso small{display:block;font-size:11px;margin-top:5px;color:#b0d7e0}.frete-spinner{width:21px;height:21px;border:2px solid #406479;border-top-color:#6cdeed;border-radius:50%;animation:fa-spin .8s linear infinite;flex:none}#frete-upload-form[aria-busy=true] button{opacity:.6;cursor:wait}@keyframes fa-spin{to{transform:rotate(360deg)}}
.conteudo .freight-audit .fa-hero h2{color:#e9f2fc;font-size:34px;line-height:1.2}.freight-audit .fa-tabs a{color:#225473;font-weight:700}.conteudo .freight-audit .fa-history-table th,.conteudo .freight-audit .fa-order-table th,.conteudo .freight-audit .card th{background:#142e48;color:#b5cee3}.conteudo .freight-audit .fa-history-table tbody th,.conteudo .freight-audit .fa-order-table tbody th{background:transparent;color:#e9f2fc}
.fa-difference-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:22px 0}.fa-difference-cards article{background:#0b1c2f;border:1px solid #31516c;border-radius:12px;padding:20px;min-width:0}.fa-difference-cards span,.fa-difference-cards small{display:block;color:#abc0d4;font-size:11px}.fa-difference-cards strong{display:block;font-size:29px;line-height:1.25;margin:12px 0;overflow-wrap:anywhere}.fa-difference-cards .fa-diff-above{border-top:3px solid #ffb76b}.fa-diff-above strong{color:#ffca8e}.fa-difference-cards .fa-diff-below{border-top:3px solid #6cdeed}.fa-diff-below strong{color:#8de5ed}.fa-order-heading{margin-top:30px;align-items:center}.fa-order-heading h4{font-size:20px;margin:0 0 5px}.fa-order-heading p{font-size:12px;margin:0}.fa-export{border:1px solid #4f788f;padding:10px 14px;border-radius:8px;font-size:12px;text-decoration:none}.freight-audit .fa-order-filter{display:flex;flex-wrap:wrap;align-items:end;gap:14px;margin:20px 0}.fa-order-filter label{font-size:11px;color:#b2c6d8;display:grid;gap:6px}.fa-order-filter select{background:#0c1c2f;color:#e9f2fc;border:1px solid #45657f;border-radius:8px;padding:11px;font-size:12px;max-width:100%}.fa-order-table{min-width:960px}.fa-order-id{font-family:monospace;user-select:all}.fa-delta.above{color:#ffca8e;font-weight:700}.fa-delta.below{color:#8de5ed;font-weight:700}.fa-pagination{display:flex;flex-wrap:wrap;gap:16px;font-size:12px;margin:18px 0}.fa-missing-detail{padding:18px;border:1px solid #577083;border-radius:10px;margin:24px 0;background:#142c42}.fa-missing-detail p,.fa-missing-detail a{font-size:12px}.fa-upload-toggle,.fa-secondary-panel{border:1px solid #34516c;background:#10243a;color:#d8e8f6;border-radius:14px;margin:20px 0;padding:20px}.fa-upload-toggle>summary,.fa-secondary-panel>summary{cursor:pointer;font-weight:700;font-size:13px}.fa-upload-toggle[open]>.fa-upload,.fa-secondary-panel[open]>.fa-panel{margin-top:20px}.fa-differences{scroll-margin-top:18px}.fa-differences>.fa-advanced p{font-size:12px}.fa-differences ul{font-size:12px;color:#abc0d4}@media(max-width:650px){.fa-difference-cards{grid-template-columns:1fr}.fa-difference-cards strong{font-size:26px}.freight-audit .fa-order-filter{display:grid;grid-template-columns:1fr}.fa-order-filter select{width:100%;min-width:0}.fa-upload-toggle,.fa-secondary-panel{padding:16px}.fa-upload-toggle .fa-panel{padding:0;border:0}}
@media(max-width:1050px){.fa-workspace{grid-template-columns:1fr}.fa-guide ol{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}.fa-guide li{padding-bottom:0}.fa-guide>p{margin-top:18px}}@media(max-width:650px){.fa-hero{padding:24px;flex-direction:column;gap:18px}.conteudo .freight-audit .fa-hero h2{font-size:29px}.fa-overview{grid-template-columns:1fr;gap:10px}.fa-overview article{padding:17px}.fa-tabs{gap:14px}.fa-panel,.fa-guide{padding:20px}.fa-section-head{flex-direction:column;gap:10px}.fa-guide ol{grid-template-columns:1fr;gap:20px}.fa-actions{flex-direction:column}.fa-actions button{width:100%}.fa-date-grid,.fa-coverage-grid{grid-template-columns:1fr}.fa-file{padding:16px}.fa-large{font-size:24px}.conteudo .freight-audit .card{padding:18px}.fa-shop{max-width:100%}}@media(prefers-reduced-motion:reduce){.frete-spinner{animation:none}.freight-audit *{scroll-behavior:auto!important}}
</style>'''

SCRIPT='''<script>document.addEventListener('DOMContentLoaded',function(){
var form=document.getElementById('frete-upload-form'),status=document.getElementById('frete-progresso');if(!form||!status)return;
var file=form.querySelector('input[type=file]'),note=document.getElementById('fa-file-note');
if(file&&note)file.addEventListener('change',function(){note.textContent=file.files.length?file.files[0].name:'Nenhum arquivo selecionado.';});
form.addEventListener('submit',function(event){if(form.getAttribute('aria-busy')==='true'){event.preventDefault();return;}if(!form.checkValidity())return;form.setAttribute('aria-busy','true');form.querySelectorAll('button[type=submit]').forEach(function(button){button.setAttribute('aria-disabled','true');});status.hidden=false;var msg=status.querySelector('b');if(msg)msg.textContent='Enviando e analisando: '+(file&&file.files.length?file.files[0].name:'arquivo');status.scrollIntoView({block:'nearest'});});
window.addEventListener('pageshow',function(){form.removeAttribute('aria-busy');form.querySelectorAll('button[type=submit]').forEach(function(button){button.removeAttribute('aria-disabled');});status.hidden=true;});
});</script>'''
