"""Read-only differences between documented versions of the same verified basis."""
from decimal import Decimal, InvalidOperation
from html import escape
from listing_profitability import COMPONENTS
from profitability_store import result_for
from freight_comparison import format_brl


def compare_versions(summary,current,selected):
    def unavailable(reason):return dict(available=False,reason=reason,rows=[])
    if not current or not selected:return unavailable('Selecione um registro para comparar com a última versão.')
    if current['id']==selected['id']:return unavailable('O registro consultado já é a última versão do período.')
    if any(current.get(k)!=selected.get(k) for k in ('conexao_id','item_id','inicio','fim')):
        return unavailable('Os registros não pertencem ao mesmo anúncio, loja e período.')
    if any(str(current[k])!=str(summary[k2]) for k,k2 in [('inicio','start'),('fim','end')]):
        return unavailable('O período do registro não corresponde à base selecionada.')
    now,old=result_for(summary,current),result_for(summary,selected)
    if not now['available'] or not old['available']:
        return unavailable('As duas versões precisam corresponder à mesma base atual de vendas verificadas e ter custos e fontes completos. Não comparamos valores de bases diferentes.')
    values=list(now['costs'].values())+list(old['costs'].values())
    try:cent_values=all(value==value.quantize(Decimal('.01')) for value in values)
    except InvalidOperation:cent_values=False
    if not cent_values:
        return unavailable('A comparação exige totais monetários documentados em centavos.')
    rows=[]
    for key,label in COMPONENTS.items():
        rows.append(dict(label=label,previous=old['costs'][key],current=now['costs'][key],
            delta=now['costs'][key]-old['costs'][key],
            source_changed=current['sources'][key]!=selected['sources'][key]))
    delta=sum((r['delta'] for r in rows),Decimal(0))
    return dict(available=True,rows=rows,cost_delta=delta,contribution_delta=-delta,
                current_id=current['id'],selected_id=selected['id'],
                changed_values=sum(r['delta']!=0 for r in rows),changed_sources=sum(r['source_changed'] for r in rows))


def render(summary,current,selected):
    if selected is None:return ''
    result=compare_versions(summary,current,selected)
    out='<section class="pf-card pf-revisions" aria-label="Comparação das versões de custos"><h3>O que mudou entre os registros</h3>'
    if not result['available']:
        return out+'<p class="pf-alert">'+escape(result['reason'])+'</p></section>'
    def signed(value):return ('+ ' if value>0 else '')+format_brl(value)
    out+='<p>Registro consultado #'+escape(str(result['selected_id']))+' → última versão #'+escape(str(result['current_id']))+'. Mesma base de vendas verificada. Componentes com valores alterados: '+str(result['changed_values'])+'; referências alteradas: '+str(result['changed_sources'])+'.</p>'
    out+='<details><summary>Conferir diferenças por componente</summary><div class="pf-table"><table class="pf-revision-table"><thead><tr><th>Componente</th><th>Registro consultado</th><th>Última versão</th><th>Diferença do custo</th><th>Referência</th></tr></thead><tbody>'
    for row in result['rows']:
        out+='<tr><td>'+escape(row['label'])+'</td><td>'+format_brl(row['previous'])+'</td><td>'+format_brl(row['current'])+'</td><td>'+signed(row['delta'])+'</td><td>'+('Alterada' if row['source_changed'] else 'Mesmo texto declarado')+'</td></tr>'
    out+='</tbody></table></div></details><p>Revisão total dos custos: <strong>'+signed(result['cost_delta'])+'</strong>. Revisão aritmética da contribuição: <strong>'+signed(result['contribution_delta'])+'</strong>.</p>'
    return out+'<p>São alterações dos registros documentais do mesmo período, sem auditoria automática dos documentos. Não representam evolução operacional, economia realizada ou recuperação financeira. Consultar não restaura nem altera versões.</p></section><style>.pf .pf-revision-table{min-width:720px}</style>'
