"""Read-only daily anomaly rules. No marketplace/API clients in this module."""
import json
from datetime import datetime, timedelta
from decimal import Decimal
from html import escape

from sales_metrics import SAO_PAULO, amount, change

VERSION = 'daily-v1'


def recommendations(report, ads, today, now):
    end = today - timedelta(days=1)
    start = end - timedelta(days=6)
    previous_start = start - timedelta(days=7)
    quality = list(report['reasons'])
    findings = []

    def add(code, priority, title, action, evidence):
        findings.append(dict(code=code, priority=priority, title=title,
                             action=action, evidence=evidence))

    current, previous = report['current'], report['previous']
    if report['eligible']:
        for key, threshold, minimum, title, action in (
            ('revenue', -20, 100, 'Queda de faturamento',
             'Investigar anúncios com perda de vendas, estoque e preços antes de intervir.'),
            ('orders', -20, 5, 'Queda de pedidos',
             'Conferir disponibilidade e os anúncios que perderam pedidos.')):
            pct = change(current[key], previous[key])
            if pct is not None and pct <= threshold and previous[key]-current[key] >= minimum:
                add(key, 80 if key == 'revenue' else 70, title, action,
                    dict(metric=key, current=float(current[key]), previous=float(previous[key]),
                         change_pct=float(pct)))

    by_day = {r['data']: r for r in ads}
    expected = [(previous_start+timedelta(days=i)).isoformat() for i in range(14)]
    valid_ads = True
    for day in expected:
        row = by_day.get(day)
        close = datetime.fromisoformat(day).replace(tzinfo=SAO_PAULO)+timedelta(days=1)
        if (not row or amount(row.get('gasto')) is None or amount(row.get('faturamento')) is None
                or not row.get('atualizado_em') or row['atualizado_em'] < close.timestamp()
                or row['atualizado_em'] > now or now-row['atualizado_em'] > 7*86400):
            valid_ads = False
            break
    if not valid_ads:
        quality.append('Ads: cobertura incompleta, inválida, antiga ou coletada antes do encerramento do dia')
    else:
        def total(key, days):
            return sum((amount(by_day[d][key]) for d in days), Decimal(0))
        spend, old_spend = total('gasto', expected[7:]), total('gasto', expected[:7])
        revenue, old_revenue = total('faturamento', expected[7:]), total('faturamento', expected[:7])
        if spend >= 50 and revenue == 0:
            add('ads_no_revenue', 95, 'Gasto em Ads sem receita atribuída',
                'Revisar atribuição, termos e desempenho das campanhas; considerar a janela de atribuição antes de decidir.',
                dict(spend=float(spend), attributed_revenue=0))
        elif spend >= 50 and old_spend >= 50 and old_revenue > 0:
            roas, old_roas = revenue/spend, old_revenue/old_spend
            if change(roas, old_roas) <= -25:
                add('roas', 90, 'Queda no retorno de Ads',
                    'Revisar campanhas com pior retorno e validar a maturação da atribuição antes de ajustar orçamento.',
                    dict(spend=float(spend), roas=float(roas), previous_roas=float(old_roas)))
        if report['eligible'] and current['revenue'] and previous['revenue']:
            tacos = spend/current['revenue']*100
            old_tacos = old_spend/previous['revenue']*100
            if spend >= 50 and tacos-old_tacos >= 5:
                add('tacos', 85, 'Aumento do TACOS',
                    'Investigar gasto em Ads frente às vendas totais antes de decidir sobre campanhas.',
                    dict(tacos_pct=float(tacos), previous_tacos_pct=float(old_tacos), spend=float(spend)))
    if quality:
        add('data_quality', 100, 'Validar qualidade dos dados',
            'Regularizar a coleta e conferir os períodos antes de tomar decisões.', dict(reasons=quality))
    findings.sort(key=lambda f: (-f['priority'], f['code']))
    return dict(version=VERSION, start=start.isoformat(), end=end.isoformat(),
                previous_start=previous_start.isoformat(), previous_end=(start-timedelta(days=1)).isoformat(),
                quality=quality, recommendations=findings[:3], interpretation=None)


def evidence_text(evidence):
    labels = dict(metric='Indicador', current='Atual', previous='Anterior', change_pct='Variação (%)',
                  spend='Gasto em Ads (R$)', attributed_revenue='Receita atribuída (R$)',
                  roas='ROAS atual', previous_roas='ROAS anterior', tacos_pct='TACOS atual (%)',
                  previous_tacos_pct='TACOS anterior (%)')
    if 'reasons' in evidence:
        return '; '.join(evidence['reasons'])
    return ' · '.join(labels.get(key,key)+': '+
                      (f'{value:.2f}' if isinstance(value,float) else
                       {'revenue':'Faturamento (R$)','orders':'Pedidos'}.get(str(value),str(value)))
                      for key,value in evidence.items())


def render(result, run_day=None, status=None, api_status=None, budget=None):
    html = "<section class='card'><h2>IA Keiper · Recomendações do dia</h2>"
    html += '<p>Análise diária de dados existentes. Toda decisão exige revisão humana.</p>'
    if not result:
        return html + '<p>Análise ainda não disponível'+(' · '+escape(status) if status else '')+'.</p></section>'
    html += '<p>Análise: '+escape(str(run_day))+' · Período: '+escape(result['start'])+' a '+escape(result['end'])
    html += ' · Comparação: '+escape(result['previous_start'])+' a '+escape(result['previous_end'])+'</p>'
    html += '<p>Qualidade: '+('com ressalvas' if result['quality'] else 'cobertura validada para as regras')+'</p>'
    for item in result['recommendations']:
        html += '<article><h3>'+escape(item['title'])+'</h3><p>'+escape(item['action'])+'</p>'
        html += '<p>Evidências: '+escape(evidence_text(item['evidence']))+'</p></article>'
    if not result['recommendations']:
        html += '<p>Nenhuma anomalia atingiu os critérios nesta execução.</p>'
    if result.get('interpretation'):
        html += '<h3>Interpretação por IA · revisar</h3><p>'+escape(result['interpretation'])+'</p>'
    html += '<p>API: '+escape(api_status or 'desabilitada')+'</p>'
    if budget:
        html += '<p>API no mês, todas as lojas: R$ '+escape(str(budget['used']))+' comprometidos de R$ '+escape(str(budget['limit']))+'. '
        html += escape(budget['alert'])+' Valores estimados; não representam uma fatura fixa.</p>'
    return html+'</section>'
