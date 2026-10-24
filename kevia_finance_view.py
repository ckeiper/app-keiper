"""Administrator-only documented financial evidence, separate from paid interpretation."""
from datetime import date,datetime,timezone
from decimal import Decimal, InvalidOperation
from html import escape
from urllib.parse import urlencode,quote
from profitability_view import stamp
from freight_comparison import format_brl

STYLE='''<style>
.kyra .ky-finance-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:13px;margin:16px 0}.kyra .ky-finance-stat{min-width:0;border:1px solid #304760;border-radius:12px;background:#101e30;padding:18px}.kyra .ky-finance-stat span{font-size:11px;color:#abc1db}.kyra .ky-finance-stat strong{display:block;font-size:25px;margin:9px 0;color:#91ddd8}.kyra .ky-finance-note{color:#a6b9d0;font-size:11px;line-height:1.7;margin-top:12px}.kyra .ky-finance-meter{height:6px;background:#273347;border-radius:6px;overflow:hidden;margin:12px 0}.kyra .ky-finance-meter span{display:block;height:100%;background:#64d4d2;width:var(--coverage)}.kyra .ky-finance-finding{padding:18px;border:1px solid #35455f;border-left:3px solid #efbe78;border-radius:12px;margin-top:13px;background:#111d2e;min-width:0}.kyra .ky-finance-finding h3{font-size:16px;margin:6px 0}.kyra .ky-finance-finding p{font-size:12px;color:#bdcbdc;margin:8px 0}.kyra .ky-finance-finding a{display:inline-block;font-size:12px;color:#94d8ef;padding:9px 0}.kyra .ky-finance-value{color:#ffb5b7;font-size:20px}.kyra .ky-finance-private{color:#9fd5ef;border:1px solid #365573;border-radius:6px;padding:5px 8px;font-size:10px}.kyra .ky-finance-table{overflow-x:auto}.kyra .ky-finance-finding h3,.kyra .ky-finance-value{overflow-wrap:anywhere}
@media(max-width:640px){.kyra .ky-finance-grid{grid-template-columns:1fr}.kyra .ky-finance-stat{padding:14px 18px}.kyra .ky-finance-stat strong{font-size:23px}}
</style>'''


def money(value):
    try:
        number=Decimal(str(value))
        return format_brl(number) if number.is_finite() else 'Indisponível'
    except (ValueError,TypeError,InvalidOperation):
        return 'Indisponível'


def count(value):
    return str(value) if type(value) is int and value>=0 else '—'


def period_day(value):
    try:return date.fromisoformat(value).strftime('%d/%m/%Y')
    except (ValueError,TypeError):return '—'


def render(snapshot,cid=None):
    esc=lambda value:escape(str(value),quote=True)
    out=STYLE+'<section class="ky-section" id="ky-finance" aria-label="Financeiro documentado"><div class="ky-section-head"><div><p class="ky-overline">EVIDÊNCIAS FINANCEIRAS · REGRAS LOCAIS</p><h2>Custos documentados, decisões com contexto</h2></div><span class="ky-finance-private">ADMINISTRADOR</span></div><div class="ky-panel">'
    try:
        checked=stamp(datetime.fromtimestamp(snapshot['checked_at'],timezone.utc))
    except (ValueError,TypeError,OverflowError,OSError,KeyError):checked='Data não verificável'
    status=snapshot.get('status')
    if status!='pending':out+='<p class="ky-finance-note">Retrato da execução em '+esc(checked)+'. Período: '+period_day(snapshot.get('start'))+' a '+period_day(snapshot.get('end'))+'. Dados salvos da execução; alterações posteriores não estão incluídas.</p>'
    status=snapshot.get('status')
    if status!='ready':
        messages=dict(pending='Aguardando a primeira execução financeira desta versão.',no_records='Aguardando custos documentados para esta janela.',
            unverified_sales='Vendas sem cobertura ou vínculo verificável; análise financeira indisponível.',
            unverified_costs='Os custos registrados não correspondem à base de vendas ou estão incompletos.',
            failed='A análise financeira não pôde ser concluída. Dados ausentes não são custos zero.')
        out+='<h3>'+esc(messages.get(status,'Análise financeira indisponível.'))+'</h3><p class="ky-finance-note">As análises de vendas e publicidade continuam separadas. A próxima execução diária poderá conferir novamente as fontes.</p>'
    else:
        out+='<div class="ky-finance-grid">'
        for label,value in [('Anúncios com custos atuais documentados',snapshot.get('documented_current')),
                            ('Com contribuição negativa documentada',snapshot.get('negative_count')),
                            ('Com margem comparável nos dois períodos',snapshot.get('comparable_margins'))]:
            out+='<article class="ky-finance-stat"><span>'+label+'</span><strong>'+count(value)+'</strong></article>'
        out+='</div>'
        total,covered=snapshot.get('current_sold_items'),snapshot.get('covered_sold_items')
        if type(total) is int and type(covered) is int and 0<=covered<=total:
            out+='<p class="ky-finance-note">Cobertura dos anúncios com vendas pagas verificadas: '+str(covered)+' de '+str(total)+'. Registros de custos sem vendas podem existir.</p>'
            if total>0:
                percent=Decimal(covered)*100/total
                out+='<div class="ky-finance-meter" style="--coverage:'+format(percent,'.2f')+'%" aria-label="Cobertura de custos: '+str(covered)+' de '+str(total)+' anúncios vendidos"><span></span></div>'
        out+='<p class="ky-finance-note">Soma das contribuições negativas documentadas: <strong>'+money(snapshot.get('negative_contribution_sum'))+'</strong>. Somente o subconjunto conferido nesta execução; não é o resultado total da loja nem lucro líquido. Não compensa contribuições positivas.</p>'
        if type(snapshot.get('declining_margin_count')) is int:
            out+='<p class="ky-finance-note">Anúncios com margem documentada menor: '+str(snapshot['declining_margin_count'])+', entre os '+count(snapshot.get('comparable_margins'))+' com comparação válida.</p>'
        if type(snapshot.get('flagged_count')) is int:
            out+='<p class="ky-finance-note">'+(('Exibindo '+str(min(3,snapshot['flagged_count']))+' de '+str(snapshot['flagged_count'])+(' anúncio' if snapshot['flagged_count']==1 else ' anúncios')+' com sinais nos registros documentados.') if snapshot['flagged_count'] else 'Nenhum sinal financeiro atingiu os critérios nos registros documentados desta execução.')+'</p>'
        for finding in (snapshot.get('findings') or [])[:3]:
            evidence=finding.get('evidence') or {}
            out+='<article class="ky-finance-finding"><h3>'+esc(finding.get('title','Conferir fontes'))+'</h3>'
            if finding.get('kind')=='negative':
                out+='<strong class="ky-finance-value">'+money(evidence.get('contribution_current'))+'</strong>'
            if evidence.get('margin_previous_pct') is not None and evidence.get('margin_current_pct') is not None:
                try:
                    before,now=Decimal(str(evidence['margin_previous_pct'])),Decimal(str(evidence['margin_current_pct']))
                    if before.is_finite() and now.is_finite():
                        out+='<p>Margem documentada: '+format(before,'.2f').replace('.',',')+'% → '+format(now,'.2f').replace('.',',')+'% ('+format(now-before,'+.2f').replace('.',',')+' p.p.).</p>'
                except (InvalidOperation,ValueError,TypeError):pass
            out+='<p>'+esc(finding.get('action','Conferir registros e fontes.'))+'</p>'
            if cid is not None and finding.get('item_id'):
                url='/anuncios/'+str(int(cid))+'/'+quote(str(finding['item_id']),safe='')+'/rentabilidade?'+urlencode(dict(inicio=snapshot.get('start',''),fim=snapshot.get('end','')))
                out+='<a href="'+esc(url)+'">Revalidar na rentabilidade do anúncio ↗</a>'
            out+='</article>'
    out+='<p class="ky-finance-note">Fontes declaradas pelo administrador, sem auditoria automática dos documentos. Regras determinísticas sobre vendas verificadas e custos documentados; não há interpretação paga destes dados nem alterações automáticas de preço ou campanha.</p>'
    if cid is not None:out+='<a class="ky-button secondary" href="/ranking-anuncios/'+str(int(cid))+'?dias=7">Abrir prioridades dos anúncios ↗</a>'
    return out+'</div></section>'
