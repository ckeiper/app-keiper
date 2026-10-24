"""Evidence-led review steps; no inferred causes, execution state or recovery forecast."""
from html import escape

STEPS={
 'stockout':('Conferir disponibilidade','Estoque confirmado em zero','Conferir reposição, variações e prazo de abastecimento.','Após repor, acompanhar novas leituras de estoque e pedidos pagos; reposição não comprova recuperação.'),
 'stock_coverage':('Conferir reposição','Cobertura estimada curta com velocidade observada','Conferir estoque, ritmo recente e prazo de abastecimento.','Atualizar a leitura e acompanhar cobertura; a estimativa não prevê demanda futura.'),
 'full':('Conferir Full e entrega','Full zerado observado no recorte','Revisar as datas de ruptura e a leitura mais recente antes de decidir reposição.','Acompanhar novas leituras de Full e pedidos pagos; uma leitura positiva não comprova recuperação.'),
 'negative_contribution':('Conferir contribuição negativa',None,'Conferir componentes e fontes na rentabilidade do anúncio.','Após corrigir dados ou realizar uma ação, comparar outro período encerrado com custos documentados; não estimar recuperação.'),
 'margin_decline':('Revisar a margem',None,'Conferir as fontes e o peso dos custos nos dois períodos.','Comparar margem em pontos percentuais somente com vendas e custos válidos; contribuição não é lucro líquido.'),
 'preco':('Revisar a oferta','Preço próprio alterado no recorte','Conferir preço final, promoção, frete, prazo e equivalência dos concorrentes.','Acompanhar pedidos pagos por visita e valor bruto nos próximos sete dias encerrados com cobertura completa.'),
 'eficiencia':('Revisar a eficiência','Eficiência observada de pedidos por visita caiu','Conferir oferta, disponibilidade e alterações; pedidos por visita não é conversão oficial.','Comparar o indicador com cobertura completa nos dois períodos, registrando outras mudanças.'),
 'trafego':('Conferir exposição','Visitas diminuíram no recorte','Conferir exposição, catálogo e campanhas vinculadas antes de atribuir uma causa.','Acompanhar visitas e pedidos pagos; mais visitas não garantem mais vendas.'),
 'ads_loja':('Verificar vínculo de Ads','Sinal de Ads refere-se à loja','Confirmar a campanha e os anúncios atendidos antes de interpretar esse contexto.','Acompanhar a campanha confirmada; não distribuir gasto ou receita da loja por suposição.'),
}
ORDER=('stockout','stock_coverage','full','negative_contribution','margin_decline','preco','eficiencia','trafego','ads_loja')


def build(row):
    codes=set(row.get('codes') or [])
    findings={r.get('code'):r for r in row.get('additional_findings',[]) if isinstance(r,dict)}
    codes.update(findings)
    if 'stockout' in codes:codes.difference_update(('stock_coverage','full'))
    if 'stock_coverage' in codes:codes.discard('full')
    # A documented negative contribution includes a margin check; avoid repeating it.
    if 'negative_contribution' in codes:codes.discard('margin_decline')
    plan=[]
    for code in ORDER:
        if code not in codes:continue
        title,evidence,action,follow_up=STEPS[code]
        finding=findings.get(code) or {}
        if evidence is None:
            evidence=finding.get('evidence')
            if not evidence:continue
        plan.append(dict(code=code,title=title,evidence=str(evidence),action=action,follow_up=follow_up))
    if not plan:
        plan=[dict(code='coverage',title='Completar a investigação',
            evidence='Perda bruta verificada sem sinal adicional suficiente para indicar uma causa.',
            action='Abrir o diagnóstico e conferir cobertura de visitas, Full, preço e histórico de alterações.',
            follow_up='Registrar a ação somente após executá-la e comparar sete dias encerrados com dados completos; sem atribuição causal.')]
    return dict(total=len(plan),steps=plan[:3])


def render(row,compact=False):
    plan=build(row);steps=plan['steps'][:1] if compact else plan['steps']
    out='<div class="kp-plan"><strong>Plano de revisão</strong><ol>'
    for step in steps:
        out+='<li><b>'+escape(step['title'])+'</b><p>'+escape(step['evidence'])+'</p><p>'+escape(step['action'])+'</p>'
        if not compact:out+='<p class="kp-followup">Como acompanhar: '+escape(step['follow_up'])+'</p>'
        out+='</li>'
    return out+'</ol><p>Ordem de conferência, sem ação executada ou causa confirmada. '+str(len(steps))+' de '+str(plan['total'])+' etapas aplicáveis exibidas.</p></div>'
