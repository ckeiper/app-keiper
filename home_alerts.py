"""Read-only, store-scoped Ads alerts from persisted observations."""
from collections import defaultdict
from datetime import datetime, timedelta
from html import escape
from urllib.parse import quote

from ads_official_metrics import value
from sales_metrics import SAO_PAULO

LABELS = {
    'budget': ('critical', 'campanha sem orçamento disponível', 'campanhas sem orçamento disponível'),
    'forecast': ('warning', 'campanha pode esgotar o orçamento em 1 hora', 'campanhas podem esgotar o orçamento em 1 hora'),
    'pacing': ('warning', 'campanha gastando acima do ritmo previsto', 'campanhas gastando acima do ritmo previsto'),
    'delivery': ('warning', 'campanha sem impressões hoje', 'campanhas sem impressões hoje'),
    'cost': ('warning', 'campanha com retorno abaixo da meta', 'campanhas com retorno abaixo da meta'),
    'decline': ('warning', 'campanha com queda de desempenho', 'campanhas com queda de desempenho'),
    'quality': ('warning', 'campanha com dados ausentes ou desatualizados', 'campanhas com dados ausentes ou desatualizados'),
    'growth': ('good', 'campanha com oportunidade de ampliar orçamento', 'campanhas com oportunidade de ampliar orçamento'),
}


def recent(stamp, now, limit=7200):
    return stamp is not None and 0 <= now - float(stamp) <= limit


def evaluate(campaigns, days, now=None):
    now = now or datetime.now(SAO_PAULO)
    today = now.date()
    stamp = now.timestamp()
    grouped = defaultdict(dict)
    for row in days:
        grouped[(row['conexao_id'], str(row['campanha_id']))][str(row['data'])] = row
    result = defaultdict(lambda: defaultdict(list))
    for campaign in campaigns:
        if str(campaign.get('status') or '').lower() not in ('active', 'running'):
            continue
        cid, campaign_id = campaign['conexao_id'], str(campaign['campanha_id'])
        history = grouped[(cid, campaign_id)]
        row = history.get(today.isoformat(), {})
        def add(code, evidence):
            result[cid][code].append(dict(id=campaign_id, name=campaign.get('nome') or campaign_id, evidence=evidence))
        spend = value(row, 'gasto')
        fresh = recent(row.get('atualizado_em'), stamp) and recent(campaign.get('atualizado_em'), stamp)
        budget = value(campaign, 'orcamento')
        if not fresh or spend is None or budget is None or value(row, 'impressoes', True) is None:
            add('quality', 'Coleta ausente, com mais de 2 horas, ou métricas incompletas. Verificar a coleta; isso não comprova falha no rastreamento de conversões.')
        if fresh and spend is not None:
            observed = datetime.fromtimestamp(float(row['atualizado_em']), SAO_PAULO)
            hours = (observed - now.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()/3600
            if budget == 0:
                add('budget', 'Campanha ativa com orçamento cadastrado de R$ 0,00.')
            if budget is not None and budget > 0:
                ratio = spend/budget
                if ratio >= 1:
                    add('budget', f'Gasto de R$ {spend:.2f} / orçamento diário de R$ {budget:.2f}.')
                elif hours >= 2 and spend > 0:
                    remaining = (budget-spend)/(spend/hours)
                    age_hours = (stamp-float(row['atualizado_em']))/3600
                    if recent(row.get('atualizado_em'), stamp, 300) and 0 < remaining-age_hours <= 1:
                        add('forecast', f'Estimativa pela média de gasto desde 00h até a coleta das {observed:%H:%M}; cerca de {remaining*60:.0f} minutos restantes. O ritmo pode variar.')
                    if ratio >= .25 and ratio > hours/24*1.3:
                        add('pacing', 'Consumo pelo menos 30% acima de uma distribuição uniforme do orçamento ao longo do dia; não considera programação de horários.')
            if hours >= 2 and value(row, 'impressoes', True) == 0:
                add('delivery', f'Zero impressões desde 00h até a coleta das {observed:%H:%M}. Não representa uma janela móvel de 2 horas.')
        # Compare complete, closed days only; attribution can still mature.
        closed = []
        for offset in range(1, 15):
            day = today-timedelta(days=offset)
            item = history.get(day.isoformat(), {})
            close = datetime.combine(day+timedelta(days=1), datetime.min.time(), SAO_PAULO).timestamp()
            if (value(item, 'gasto') is None or value(item, 'faturamento') is None
                    or not recent(item.get('atualizado_em'), stamp, 7*86400)
                    or float(item['atualizado_em']) < close):
                break
            closed.append(item)
        if len(closed) < 7:
            continue
        spend7 = sum(float(r['gasto']) for r in closed[:7])
        revenue7 = sum(float(r['faturamento']) for r in closed[:7])
        target = value(campaign, 'roas_objetivo')
        if spend7 < 50 or revenue7 <= 0:
            continue
        roas = revenue7/spend7
        evidence = f'ROAS dos últimos 7 dias completos: {roas:.2f}x; investimento R$ {spend7:.2f}. A atribuição pode amadurecer.'
        if fresh and target and roas < target*.8:
            add('cost', evidence+f' Meta cadastrada: {target:.2f}x. Equivale a custo sobre receita acima da meta; não há meta de CPA cadastrada.')
        if fresh and target and roas >= target*1.3 and budget and spend is not None and spend >= budget*.8:
            add('growth', evidence+f' Meta: {target:.2f}x; pelo menos 80% do orçamento consumido hoje. Revisar antes de ampliar.')
        if fresh and len(closed) == 14:
            old_spend = sum(float(r['gasto']) for r in closed[7:])
            old_revenue = sum(float(r['faturamento']) for r in closed[7:])
            if old_spend >= 50 and old_revenue > 0 and roas <= old_revenue/old_spend*.75:
                add('decline', evidence+f' ROAS dos 7 dias anteriores: {old_revenue/old_spend:.2f}x; queda de pelo menos 25%.')
    return {str(cid): dict(groups) for cid, groups in result.items()}


def load(cid, bank, query):
    now = datetime.now(SAO_PAULO)
    with bank() as conn:
        from overview_read import bounded_query
        read = bounded_query(conn, query)
        campaigns = read(conn, 'SELECT conexao_id,campanha_id,nome,status,orcamento,roas_objetivo,atualizado_em FROM ads_campanhas WHERE conexao_id=%s', (cid,))
        days = read(conn, 'SELECT conexao_id,campanha_id,data,gasto,faturamento,impressoes,atualizado_em FROM ads_campanha_dia WHERE conexao_id=%s AND data BETWEEN %s AND %s',
                    (cid, (now.date()-timedelta(days=14)).isoformat(), now.date().isoformat()))
    return evaluate(campaigns, days, now).get(str(cid), {}), bool(campaigns)


def label(code, count):
    return str(count)+' '+LABELS[code][1 if count == 1 else 2]


def render(groups, cid, known):
    out = '<section class="card"><h2>Alertas da loja</h2><p>Leituras de Ads · horários de Brasília · dados recentes: até 2 horas.</p>'
    if not groups:
        out += '<p>'+('Nenhum alerta identificado nos dados disponíveis. Isso não garante cobertura completa de todas as métricas.' if known else 'Campanhas ainda não sincronizadas.')+'</p>'
    for code in LABELS:
        items = groups.get(code, [])
        if not items:
            continue
        out += '<section id="alert-'+code+'"><h3>'+escape(label(code, len(items)))+'</h3><ul>'
        for item in items:
            url = '/ads/'+str(cid)+'/campanha/'+quote(item['id'], safe='')
            out += '<li><a href="'+escape(url, quote=True)+'">'+escape(item['name'])+'</a><p>'+escape(item['evidence'])+'</p></li>'
        out += '</ul></section>'
    return out+'<p>Ausência de dados não é tratada como zero. Nenhuma campanha é alterada automaticamente.</p></section>'
