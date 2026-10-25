"""Financial evidence view; values are escaped and unknowns never become zero."""
from html import escape
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlencode
from listing_profitability import COMPONENTS
from margin_recovery import render_recovery
from freight_comparison import format_brl

CSS = '''<style>
.pf{--pf-line:#29425f;--pf-muted:#b6c7dc;color:#eff5ff;max-width:1200px;margin:auto}
.pf .pf-hero,.pf .pf-card{background:#101f35;border:1px solid var(--pf-line);border-radius:16px;padding:24px;margin-bottom:18px}
.pf .pf-hero{background:linear-gradient(120deg,#101f35,#193b60)}
.pf h2,.pf h3,.pf strong,.pf label{color:#eff5ff}.pf h2{margin:8px 0;font-size:26px}
.conteudo .pf.fq h2{color:#eff5ff}.conteudo .pf .pf-hero h2{color:#eff5ff}.conteudo .pf .pf-table th{background:#1b3552;color:#dce9f7}
.pf p,.pf small{color:var(--pf-muted);line-height:1.65}.pf a{color:#9cd9ff;text-decoration:none}
.pf .pf-eyebrow{font-size:11px;letter-spacing:1.3px;text-transform:uppercase;color:#8ed8ef}
.pf .pf-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
.pf .pf-metric{background:#142940;border:1px solid var(--pf-line);padding:18px;border-radius:12px}
.pf .pf-metric strong{font-size:25px;display:block;margin:9px 0;overflow-wrap:anywhere}
.pf .pf-metric span{font-size:12px;color:var(--pf-muted)}.pf .pf-positive{color:#88e0bf}.pf .pf-negative{color:#ffafb3}
.pf .pf-recovery-list{display:grid;gap:12px;margin:18px 0}.pf .pf-recovery-list h4{color:#eff5ff;margin:0}
.pf .pf-fields{display:grid;grid-template-columns:1fr 2fr;gap:12px;align-items:end;margin-bottom:18px}
.pf label{display:block;font-size:13px}.pf input{display:block;box-sizing:border-box;width:100%;background:#0b192c;color:#eff5ff;border:1px solid #426184;padding:12px;border-radius:8px;margin-top:7px;min-width:0}
.pf input[type=checkbox]{display:inline;width:auto;margin-right:8px}.pf button,.pf .pf-button{display:inline-block;background:#287ac1;color:white;border:0;padding:12px 18px;border-radius:9px;font-weight:700;cursor:pointer}
.pf :focus-visible{outline:3px solid #91d9fa;outline-offset:3px}.pf .pf-filter{display:flex;flex-wrap:wrap;gap:12px;align-items:end;margin-top:18px}
.pf .pf-alert{background:#322c20;border:1px solid #836b34;padding:16px;border-radius:12px;color:#ffe1a1;margin:16px 0}
.pf .pf-unit-table{min-width:650px}.pf .pf-unit-table caption{text-align:left;color:#b6c7dc;padding:12px 0}
.pf .pf-table{overflow-x:auto}.pf table{width:100%;border-collapse:collapse}.pf th,.pf td{padding:13px 10px;border-bottom:1px solid var(--pf-line);text-align:left;color:#dce9f7;overflow-wrap:anywhere}.pf th{font-size:12px;color:#b6c7dc}.pf details summary{cursor:pointer;font-weight:700;padding:8px 0}.pf .pf-source{max-width:480px;white-space:pre-wrap}
.pf .pf-status-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:15px 0}.pf .pf-status-item{background:#142940;border:1px solid #34516e;border-radius:10px;padding:14px;min-width:0}.pf .pf-status-item span{display:block;color:#b6c7dc;font-size:12px}.pf .pf-status-item strong{display:block;font-size:14px;margin-top:8px;overflow-wrap:anywhere}.pf .pf-source-status .pf-status-link{display:inline-block;background:#1c3552;color:#b9e5ff;border:1px solid #426184;border-radius:9px;padding:10px 12px}
@media(max-width:700px){.pf .pf-status-grid{grid-template-columns:1fr}.pf .pf-grid,.pf .pf-fields{grid-template-columns:1fr}.pf .pf-card,.pf .pf-hero{padding:18px}.pf h2{font-size:22px}.pf .pf-filter label{flex:1 1 130px}.pf .pf-filter button{width:100%}}
</style>'''


def stamp(value):
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            return 'Data não verificável'
        return parsed.astimezone(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y às %H:%M · Brasília')
    except (ValueError,TypeError,OverflowError):
        return 'Data não verificável'


def render_source_status(summary,result,record):
    verified=summary.get('orders') is not None
    cost_state=('Vinculados à base verificada' if result['available'] else
                'Registro requer conferência' if record else 'Ainda não registrados')
    out='<section class="pf-card pf-source-status" aria-label="Validação do período"><h3>Validação do período</h3><div class="pf-status-grid">'
    for label,value in [('Vendas','Base verificada' if verified else 'Verificação pendente'),
                        ('Custos documentados',cost_state),
                        ('Documentos','Referências declaradas, sem auditoria automática')]:
        out+='<article class="pf-status-item"><span>'+label+'</span><strong>'+escape(value)+'</strong></article>'
    out+='</div>'
    if verified:
        out+='<a class="pf-status-link" href="#pf-fontes">Conferir fontes e registrar custos</a>'
    else:
        out+='<p>Conclua a verificação das vendas antes de registrar custos para esta base. Registros anteriores permanecem preservados.</p>'
    return out+'</section>'


def render_inspection(record):
    if record is None:return ''
    esc=lambda value:escape(str(value),quote=True)
    out='<section class="pf-card pf-inspection" id="pf-registro" aria-label="Consulta do registro de custos"><h3 tabindex="-1">Consulta do registro #'+esc(record['id'])+'</h3>'
    out+='<p>'+record['inicio'].strftime('%d/%m/%Y')+' a '+record['fim'].strftime('%d/%m/%Y')+' · Informado em '+esc(stamp(record['created_at']))+'</p>'
    out+='<p>Base original: '+esc(record['units'])+' unidades · '+format_brl(record['gross_items'])+' em valor bruto dos itens.</p><p class="pf-alert">Somente consulta. Selecionar este registro não altera os indicadores, que continuam usando a última versão do período e a verificação atual das vendas. Não é possível restaurar ou editar uma versão por esta consulta.</p>'
    out+='<div class="pf-table"><table><thead><tr><th>Componente registrado</th><th>Total no período</th><th>Referência declarada</th></tr></thead><tbody>'
    for field,label in COMPONENTS.items():
        out+='<tr><td>'+label+'</td><td>'+format_brl(record['costs'].get(field))+'</td><td class="pf-source">'+esc(record['sources'].get(field,''))+'</td></tr>'
    query=urlencode(dict(inicio=record['inicio'].isoformat(),fim=record['fim'].isoformat()))
    return out+'</tbody></table></div><p>Documentos não são auditados automaticamente. O registro pode ter uma base de vendas diferente da atual.</p><a href="?'+esc(query)+'#pf-historico">Voltar ao histórico do período</a></section>'


def render(cid, item_id, title, start, end, summary, result, record, history, csrf, key, values=None, message='', comparison_html='', inspected_record=None):
    values = values or {}
    esc = lambda value: escape(str(value), quote=True)
    out = CSS + '<div class="pf"><header class="pf-hero"><span class="pf-eyebrow">Anúncios 2.0 · Evidências financeiras</span><h2>Rentabilidade por anúncio</h2><p>'+esc(title or item_id)+' · '+esc(item_id)+'</p><a href="/diagnostico/'+str(cid)+'/'+esc(item_id)+'">← Diagnóstico do anúncio</a><p>Contribuição sobre o valor bruto dos itens vendidos, após os custos documentados abaixo. Não representa lucro líquido nem repasse bancário.</p>'
    out += '<form method="get" class="pf-filter"><label>Início<input type="date" name="inicio" value="'+start.isoformat()+'" required></label><label>Fim<input type="date" name="fim" value="'+end.isoformat()+'" required></label><button>Aplicar período</button></form></header>'
    out += '<p><a class="pf-button" href="/anuncios/'+str(cid)+'/'+esc(item_id)+'/simulacao-descontos">Simular descontos progressivos ↗</a></p>'
    if message:
        out += '<p class="pf-alert" role="status">'+esc(message)+'</p>'
    verified = summary.get('orders') is not None
    contribution = result.get('contribution')
    margin = result.get('margin_pct')
    out += '<section class="pf-card"><div class="pf-grid">'
    for label, value, note in [
        ('Valor bruto dos itens', format_brl(summary['gross_items']) if verified else 'Indisponível', str(summary['units'])+' unidades verificadas' if verified else 'Sem base completa'),
        ('Contribuição documentada', format_brl(contribution) if result['available'] else 'Indisponível', 'Custos variáveis informados pelo administrador'),
        ('Margem de contribuição', format(margin,'.2f').replace('.',',')+'%' if margin is not None else '—', 'Contribuição ÷ valor bruto dos itens')]:
        out += '<article class="pf-metric"><span>'+label+'</span><strong>'+esc(value)+'</strong><small>'+esc(note)+'</small></article>'
    out += '</div>'
    if not result['available']:
        out += '<p class="pf-alert">'+esc(result['reason'])+'</p>'
    out += '<p>Pedidos pagos e aprovados, cobertura diária completa e vínculo dos itens. Períodos encerrados em horário de Brasília. Despesas fixas e operacionais não estão incluídas. Não há rateio automático de frete, publicidade ou valores da conta.</p></section>'
    out += render_source_status(summary,result,record)
    out += comparison_html
    out += render_recovery(summary, record)
    if record:
        if not result['available']:
            out += '<section class="pf-card pf-record-warning"><h3>Este registro não valida o cálculo atual</h3><p class="pf-alert">'+esc(result['reason'])+'</p><p>Base registrada: '+esc(record.get('units'))+' unidades · '+format_brl(record.get('gross_items'))+' em valor bruto dos itens. Os componentes abaixo são históricos; não substituem a conferência da base selecionada.</p></section>'
        out += '<section class="pf-card"><h3>'+('Composição e fontes' if result['available'] else 'Registro preservado para conferência')+' · registro #'+str(record['id'])+'</h3><p>Informado pelo administrador em '+esc(stamp(record['created_at']))+'. As fontes são referências declaradas, sem validação automática de documentos.</p><div class="pf-table"><table><thead><tr><th>Componente</th><th>Total no período</th><th>Fonte informada</th></tr></thead><tbody>'
        for field, label in COMPONENTS.items():
            out += '<tr><td>'+label+'</td><td>'+format_brl(record['costs'].get(field))+'</td><td class="pf-source">'+esc(record['sources'].get(field,''))+'</td></tr>'
        out += '</tbody></table></div></section>'
    if verified:
        out += '<section class="pf-card" id="pf-fontes"><details'+(' open' if values else '')+'><summary>Registrar custos documentados do período</summary><p>Informe totais exclusivos deste anúncio, das unidades e das datas selecionadas. Zero também exige uma fonte. Se algum custo não é conhecido, aguarde a conferência. Não use o custo atual para representar custos históricos diferentes.</p><form method="post"><input type="hidden" name="_csrf" value="'+esc(csrf)+'"><input type="hidden" name="submission_key" value="'+esc(key)+'"><input type="hidden" name="basis" value="'+esc(summary['fingerprint'])+'">'
        for field, label in COMPONENTS.items():
            out += '<div class="pf-fields"><label>'+label+' (R$)<input name="'+field+'" inputmode="decimal" required maxlength="15" value="'+esc(values.get(field,''))+'" placeholder="Total do período"></label><label>Fonte e abrangência<input name="'+field+'_source" required minlength="5" maxlength="500" value="'+esc(values.get(field+'_source',''))+'" placeholder="Documento ou relatório, datas e critério"></label></div>'
        out += '<p>Descontos, devoluções e ajustes: inclua somente reduções adicionais ainda não refletidas no preço dos itens, sem duplicar valores. Não há sincronização automática de todos os ajustes financeiros.</p><label><input type="checkbox" name="confirmed" value="yes" required>Conferi as fontes, o período, todas as unidades e os custos deste anúncio, inclusive valores zero. Não incluí custos de outras lojas ou anúncios nem contei ajustes duas vezes.</label><p><button>Salvar nova versão</button></p><small>Cada versão preserva a anterior. Nenhum anúncio, preço ou campanha será alterado.</small></form></details></section>'
    out += render_inspection(inspected_record)
    from profitability_revisions import render as render_revisions
    out += render_revisions(summary,record,inspected_record)
    out += '<section class="pf-card" id="pf-historico"><h3>Últimos registros deste anúncio</h3>'
    for row in history:
        query = urlencode({'inicio':row['inicio'].isoformat(),'fim':row['fim'].isoformat()})
        out += '<p><a href="?'+esc(query)+'">'+row['inicio'].strftime('%d/%m/%Y')+' a '+row['fim'].strftime('%d/%m/%Y')+'</a> · registro #'+str(row['id'])+' · '+esc(stamp(row['created_at']))+' · abre a última versão do período. <a class="pf-inspect-link" href="?'+esc(query+'&registro='+str(row['id']))+'#pf-registro">Conferir registro #'+esc(row['id'])+'</a></p>'
    return out + ('<p>Nenhum custo documentado registrado.</p>' if not history else '')+'</section></div>'
