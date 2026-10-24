"""Deterministic campaign investigations from closed-day snapshots only.

No marketplace clients, LLM calls, estimates of missing metrics or writes.
Thresholds identify investigations; they are not profitability/causality claims.
"""
import math
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from sales_metrics import SAO_PAULO, amount, change

VERSION = 'campaign-v1'
MAX_CAMPAIGNS = 500
MAX_DAILY_ROWS = MAX_CAMPAIGNS * 14
ACTIVE = {'active', 'ativa'}


def fresh(stamp, now, closed=None, age=7*86400):
    if isinstance(stamp, bool):
        return False
    try:
        stamp = float(stamp)
        return math.isfinite(stamp) and stamp <= now and now-stamp <= age and (closed is None or stamp >= closed)
    except (ValueError, TypeError, OverflowError):
        return False


def official_count(raw):
    if isinstance(raw, bool):
        return None
    value = amount(raw)
    return value if value is not None and value == value.to_integral_value() else None


def analyze(campaigns, rows, today, now, limited=False):
    end = today-timedelta(days=1)
    days = [(end-timedelta(days=i)).isoformat() for i in range(13,-1,-1)]
    by_campaign = defaultdict(lambda: defaultdict(list))
    expected = set(days)
    for row in rows:
        if str(row.get('data')) in expected:
            by_campaign[str(row.get('campanha_id'))][str(row['data'])].append(row)
    result = dict(version=VERSION, start=days[7], end=days[-1],
                  previous_start=days[0], previous_end=days[6], limited=limited,
                  observed=len(campaigns), active=0, comparable=0, current_ready=0,
                  campaigns=[], recommendations=[], caveats=[
                      'Receita atribuída pode mudar com a janela de atribuição do Mercado Livre.',
                      'Margem, estoque e concorrência não são validados por estas regras.'])
    candidates = []
    for campaign in campaigns[:MAX_CAMPAIGNS]:
        if str(campaign.get('status', '')).lower() not in ACTIVE:
            continue
        result['active'] += 1
        cid = str(campaign['campanha_id'])
        metadata_ok = fresh(campaign.get('atualizado_em'), now, age=86400)
        entry = dict(campaign_id=cid, name=str(campaign.get('nome') or 'Campanha '+cid),
                     metadata_fresh=metadata_ok, quality=[], current=None, previous=None,
                     current_days=0, previous_days=0)
        if not metadata_ok:
            entry['quality'].append('Status, orçamento ou meta sem atualização válida nas últimas 24 horas.')

        def window(selected):
            valid = []
            official_valid = []
            missing = []
            for d in selected:
                items = by_campaign[cid].get(d, [])
                closed = (datetime.fromisoformat(d).replace(tzinfo=SAO_PAULO)+timedelta(days=1)).timestamp()
                row = items[0] if len(items)==1 else None
                if (row is None or amount(row.get('gasto')) is None or amount(row.get('faturamento')) is None
                        or not fresh(row.get('atualizado_em'), now, closed)):
                    missing.append(d)
                else:
                    valid.append(row)
                    if fresh(row.get('metricas_vendas_coletadas_em'), now, closed):
                        official_valid.append(row)
            if len(valid)!=7:
                return None, len(valid), missing
            spend = sum((amount(r['gasto']) for r in valid), Decimal(0))
            revenue = sum((amount(r['faturamento']) for r in valid), Decimal(0))
            sales_values = [official_count(r.get('vendas_atribuidas')) for r in official_valid]
            organic_values = [amount(r.get('faturamento_sem_ads')) for r in official_valid]
            sales = sum(sales_values, Decimal(0)) if len(sales_values)==7 and all(v is not None for v in sales_values) else None
            organic = sum(organic_values, Decimal(0)) if len(organic_values)==7 and all(v is not None for v in organic_values) else None
            total = revenue+organic if organic is not None else None
            return dict(spend=spend, revenue=revenue, roas=revenue/spend if spend>0 else None,
                        acos=spend/revenue*100 if revenue>0 else None, attributed_sales=sales,
                        organic_revenue=organic, tacos=spend/total*100 if total is not None and total>0 else None), 7, []

        current, current_days, current_missing = window(days[7:])
        previous, previous_days, previous_missing = window(days[:7])
        entry.update(current=current, previous=previous, current_days=current_days, previous_days=previous_days)
        if current_missing:
            entry['quality'].append('Período atual: '+str(current_days)+'/7 dias válidos. Ausentes, inválidos ou desatualizados: '+', '.join(current_missing)+'.')
        if previous_missing:
            entry['quality'].append('Período anterior: '+str(previous_days)+'/7 dias válidos. Ausentes, inválidos ou desatualizados: '+', '.join(previous_missing)+'.')
        if current and current['attributed_sales'] is None:
            entry['quality'].append('Quantidade oficial de vendas atribuídas incompleta; potencial de escala não é avaliado.')
        if current and (current['tacos'] is None or previous is None or previous['tacos'] is None):
            entry['quality'].append('Receita orgânica oficial ou base de comparação insuficiente; variação de TACOS não é avaliada.')
        result['campaigns'].append(entry)
        if not current or not metadata_ok or limited:
            continue
        result['current_ready'] += 1
        if previous:
            result['comparable'] += 1
        target = amount(campaign.get('roas_objetivo'))
        if not target:
            target = None
        roas_delta = change(current['roas'], previous['roas']) if previous and current['roas'] is not None and previous['roas'] else None
        findings = []

        def add(code, priority, title, why, action):
            findings.append(dict(code=code, priority=priority, campaign_id=cid, name=entry['name'],
                                 title=title, why=why, action=action, current=current, previous=previous,
                                 target_roas=target, roas_change_pct=roas_delta,
                                 quality=entry['quality']))

        if current['spend'] >= 50 and current['revenue']==0:
            add('spend_without_revenue', 100, 'Investigar gasto sem receita atribuída',
                'Pelo menos R$50 investidos em sete dias completos e nenhuma receita atribuída registrada.',
                'Conferir maturação da atribuição, anúncios atendidos, preços e disponibilidade. Se o padrão persistir, avaliar manualmente a redistribuição do investimento; não pausar apenas por este sinal.')
        if previous and current['spend']>=50 and previous['spend']>=50 and roas_delta is not None and roas_delta<=-25:
            add('roas_drop', 90, 'Investigar perda de eficiência',
                'ROAS caiu pelo menos 25% entre dois períodos completos, com investimento de pelo menos R$50 em cada um.',
                'Abrir a campanha e comparar anúncios, receita e investimento. Conferir alterações de meta ou orçamento e a janela de atribuição antes de decidir sobre a verba.')
        if target and current['spend']>=50 and current['roas'] is not None and current['roas']<=target*Decimal('.8'):
            add('below_target', 80, 'Revisar distância para a meta de ROAS',
                'ROAS dos sete dias está pelo menos 20% abaixo da meta atualmente cadastrada. A meta pode ter mudado durante o período.',
                'Validar se a meta atual é adequada à margem. Investigar anúncios que concentram gasto e pouco retorno antes de alterar orçamento ou objetivo.')
        if previous and current['spend']>=50 and current['tacos'] is not None and previous['tacos'] is not None and current['tacos']-previous['tacos']>=5:
            add('tacos_rise', 75, 'Revisar aumento do peso da publicidade',
                'TACOS da campanha aumentou pelo menos cinco pontos percentuais, usando receita Ads e orgânica oficial dos mesmos anúncios.',
                'Conferir se o gasto adicional foi acompanhado pelo faturamento total dos anúncios da campanha. Avaliar margem e composição das vendas antes de redistribuir investimento.')
        if (previous and target and current['spend']>=50 and previous['spend']>=50
                and current['roas'] is not None and current['roas']>=target*Decimal('1.3')
                and current['attributed_sales'] is not None and current['attributed_sales']>=5
                and roas_delta is not None and roas_delta>=-10):
            add('scale_review', 50, 'Avaliar potencial de escala',
                'ROAS pelo menos 30% acima da meta atual, cinco ou mais vendas atribuídas e sem queda de ROAS superior a 10% entre períodos completos.',
                'Validar margem, estoque e capacidade de atendimento. Se houver espaço, considerar um teste manual de aumento gradual e acompanhar o retorno; o histórico não garante resultado futuro.')
        if findings:
            # One coherent next investigation per campaign; risk always wins.
            candidates.append(sorted(findings, key=lambda f:(-f['priority'],f['code']))[0])
    candidates.sort(key=lambda f:(-f['priority'],-f['current']['spend'],f['campaign_id']))
    result['recommendations'] = candidates[:3]
    result['flagged'] = len(candidates)
    result['blocked'] = result['active']-result['current_ready']
    if limited:
        result['caveats'].insert(0, 'Limite de leitura atingido. Recomendações suprimidas; não é possível priorizar toda a carteira com segurança.')
    # JSON-ready without lossy rounding before rule comparisons.
    def encode(value):
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, dict):
            return {k:encode(v) for k,v in value.items()}
        if isinstance(value, list):
            return [encode(v) for v in value]
        return value
    return encode(result)
