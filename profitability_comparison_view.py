"""Read-only comparison and source-aware next steps inside the navy financial page."""
from html import escape
from decimal import Decimal
from urllib.parse import urlencode
from freight_comparison import format_brl

STYLE = '''<style>
.pf .pf-comparison-table{min-width:860px}.pf .pf-deltas{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:18px 0}.pf .pf-delta{padding:18px;border:1px solid #34516e;background:#142940;border-radius:12px;min-width:0}.pf .pf-delta strong{display:block;font-size:24px;margin:8px 0;overflow-wrap:anywhere}.pf .pf-delta span{color:#b6c7dc;font-size:12px}.pf .pf-direction-positive{color:#88e0bf}.pf .pf-direction-negative{color:#ffafb3}.pf .pf-findings{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin:18px 0}.pf .pf-finding{border:1px solid #3d5471;border-left:3px solid #e9bf6b;border-radius:10px;padding:16px;min-width:0}.pf .pf-finding h4{margin:0 0 8px;color:#fff;font-size:15px}.pf .pf-finding p{margin:8px 0;font-size:13px}.pf .pf-comparison-caption{font-size:12px}.pf .pf-source-link{display:inline-block;padding:10px 12px;border:1px solid #426184;border-radius:9px;margin-top:8px}
@media(max-width:700px){.pf .pf-deltas{grid-template-columns:1fr}.pf .pf-findings{grid-template-columns:1fr}}
</style>'''


def signed_money(value):
    if Decimal(format(value,'.2f')) == 0:
        value = Decimal(0)
    return ('+ ' if value>0 else '')+format_brl(value)


def points(value):
    if Decimal(format(value,'.2f')) == 0:
        value = Decimal(0)
    return ('+' if value>0 else '')+format(value,'.2f').replace('.',',')+' p.p.'


def render_comparison(comparison,start,end,previous_start,previous_end,current_record=None,previous_record=None,previous_accessible=True):
    esc=lambda value:escape(str(value),quote=True)
    prior_query=urlencode(dict(inicio=previous_start.isoformat(),fim=previous_end.isoformat()))
    out=STYLE+'<section class="pf-card" id="pf-comparacao" aria-label="Evolução da rentabilidade"><h3>Evolução da contribuição e da margem</h3>'
    out+='<p>Atual: '+start.strftime('%d/%m/%Y')+' a '+end.strftime('%d/%m/%Y')+' · Anterior: '+previous_start.strftime('%d/%m/%Y')+' a '+previous_end.strftime('%d/%m/%Y')+'. Janelas consecutivas de mesma duração, sem sobreposição.</p>'
    if not comparison['available']:
        out+='<p class="pf-alert">'+esc(comparison['reason'])+'</p><p>Período atual: '+('custos documentados e vendas verificadas' if comparison['current']['available'] else esc(comparison['current']['reason']))+'.<br>Período anterior: '+('custos documentados e vendas verificadas' if comparison['previous']['available'] else esc(comparison['previous']['reason']))+'.</p>'
    else:
        delta=comparison['contribution_delta'];margin=comparison['margin_delta_pp']
        out+='<div class="pf-deltas">'
        for label,value,number in [
            ('Variação da contribuição',signed_money(delta),delta),
            ('Variação da margem',points(margin) if margin is not None else 'Indisponível',margin),
            ('Unidades vendidas',str(comparison['previous_units'])+' → '+str(comparison['current_units']),None)]:
            cls='pf-direction-positive' if number is not None and number>0 else 'pf-direction-negative' if number is not None and number<0 else ''
            out+='<article class="pf-delta"><span>'+label+'</span><strong class="'+cls+'">'+esc(value)+'</strong></article>'
        out+='</div><p>A diferença em reais inclui mudanças no volume vendido. A participação de cada custo no valor bruto permite comparar o peso financeiro mesmo quando os volumes são diferentes. Sem valor bruto, a margem e as participações não são calculadas.</p>'
        out+='<div class="pf-table"><table class="pf-comparison-table"><caption class="pf-comparison-caption">Composição aritmética da variação · valores em R$ · tabela com rolagem horizontal no celular</caption><thead><tr><th>Componente</th><th>Anterior</th><th>Atual</th><th>Variação do valor</th><th>Efeito na contribuição</th><th>Participação anterior → atual</th></tr></thead><tbody>'
        for row in comparison['rows']:
            share=('—' if row['current_share'] is None or row['previous_share'] is None else format(row['previous_share'],'.2f').replace('.',',')+'% → '+format(row['current_share'],'.2f').replace('.',',')+'% ('+points(row['share_delta_pp'])+')')
            impact=row['impact'];cls='pf-direction-positive' if impact>0 else 'pf-direction-negative' if impact<0 else ''
            out+='<tr><td>'+esc(row['label'])+'</td><td>'+format_brl(row['previous'])+'</td><td>'+format_brl(row['current'])+'</td><td>'+signed_money(row['delta'])+'</td><td><span class="'+cls+'">'+signed_money(impact)+'</span></td><td>'+esc(share)+'</td></tr>'
        out+='<tr><th>Contribuição documentada</th><td>'+format_brl(comparison['previous']['contribution'])+'</td><td>'+format_brl(comparison['current']['contribution'])+'</td><td>'+signed_money(delta)+'</td><td>'+signed_money(delta)+'</td><td>Custos variáveis informados</td></tr></tbody></table></div><p>A soma dos efeitos reconcilia exatamente com a diferença de contribuição. O efeito de um custo é o inverso de sua variação em reais; não é uma projeção de recuperação nem comprovação de causa.</p>'
        if current_record and previous_record:
            out+='<p>Fontes: registro atual #'+esc(current_record['id'])+' · registro anterior #'+esc(previous_record['id'])+'. Referências declaradas pelo administrador; documentos não são validados automaticamente.</p>'
    if comparison['findings']:
        out+='<h3>Pontos para conferir nas fontes</h3><div class="pf-findings">'
        for finding in comparison['findings']:
            value=format_brl(finding['evidence']) if finding['code']=='negative_contribution' else points(finding['evidence'])
            out+='<article class="pf-finding"><h4>'+esc(finding['title'])+'</h4><strong>'+esc(value)+'</strong><p>'+esc(finding['action'])+'</p></article>'
        out+='</div><p>Leitura determinística dos registros documentados. Nenhum preço, anúncio, promoção ou campanha será alterado automaticamente.</p>'
    if previous_accessible:
        out+='<a class="pf-source-link" href="?'+esc(prior_query)+'">Conferir período anterior e suas fontes ↗</a>'
    return out+'</section>'
