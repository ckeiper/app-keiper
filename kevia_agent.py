"""Bounded, read-only mission planner over existing shop-scoped diagnoses.

Stage one uses deterministic planning, never a provider or marketplace client.
Only the caller may retrieve records, after authorizing the selected shop.
"""
from datetime import timedelta
from html import escape
from urllib.parse import quote
import json

MISSIONS = {'prioridades': 'Três prioridades da loja', 'ads': 'Revisar publicidade',
            'vendas': 'Investigar vendas'}


def plan(daily, campaigns, today, mission='prioridades'):
    if mission not in MISSIONS:
        mission = 'prioridades'
    output = dict(mission=mission, tasks=[], sources=[], limitations=[])
    candidates = []
    for name, run in [('loja', daily), ('campanhas', campaigns)]:
        if mission == 'vendas' and name == 'campanhas':
            continue
        run = run or {}
        result = run.get('result')
        result = result if isinstance(result, dict) else {}
        expected_end = (today-timedelta(days=1)).isoformat()
        ready = (run.get('status') == 'completed' and str(run.get('day')) == today.isoformat()
                 and str(result.get('end')) == expected_end)
        source = dict(name=name, day=str(run.get('day') or ''),
                      start=str(result.get('start') or ''), end=str(result.get('end') or ''), ready=ready)
        output['sources'].append(source)
        if not ready:
            output['limitations'].append('Diagnóstico de '+name+' indisponível, incompleto ou antigo; aguardar a rotina diária.')
            continue
        if result.get('limited'):
            output['limitations'].append('Leitura de campanhas limitada; prioridades de campanhas bloqueadas.')
            continue
        output['limitations'].extend(str(x) for x in result.get('quality', []) if isinstance(x, str))
        output['limitations'].extend(str(x) for x in result.get('caveats', []) if isinstance(x, str))
        for item in (result.get('recommendations') or [])[:3]:
            if not isinstance(item, dict):
                continue
            code = str(item.get('code', ''))
            # Private finance never becomes an input or task of this mission.
            if code.startswith('finance_'):
                continue
            category = 'qualidade' if code == 'data_quality' else (
                'vendas' if code in ('revenue', 'orders') else 'ads')
            if mission == 'ads' and category == 'vendas':
                continue
            if mission == 'vendas' and category == 'ads':
                continue
            if not item.get('action') or not item.get('title'):
                continue
            evidence = item.get('evidence') if name == 'loja' else {
                'campanha': item.get('name'), 'atual': item.get('current'),
                'anterior': item.get('previous'), 'meta_roas_atual': item.get('target_roas'),
                'criterio': item.get('why'), 'ressalvas': item.get('quality')}
            if not isinstance(evidence, dict) or not evidence:
                continue
            try:
                priority = max(0, min(100, int(item.get('priority', 0))))
            except (ValueError, TypeError, OverflowError):
                continue
            candidates.append(dict(code=code, priority=priority, title=str(item['title']),
                action=str(item['action']), category=category, source=source, evidence=evidence,
                campaign_id=str(item.get('campaign_id') or '') if name == 'campanhas' else ''))
    candidates.sort(key=lambda x: (-x['priority'], x['source']['name'], x['campaign_id'], x['code']))
    seen = set()
    for task in candidates:
        key = (task['source']['name'], task['campaign_id'], task['code'])
        if key not in seen:
            output['tasks'].append(task)
            seen.add(key)
        if len(output['tasks']) == 3:
            break
    output['limitations'] = list(dict.fromkeys(output['limitations']))
    return output


def render(mission, cid):
    cid = str(int(cid))
    safe = lambda value: escape(str(value), quote=True)
    out = """<style>
#kevia-agent{margin-bottom:18px}#kevia-agent form{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:16px 0}
#kevia-agent select,#kevia-agent button{font:inherit;color:inherit;background:var(--card,#17233b);border:1px solid var(--border,#334155);border-radius:8px;padding:10px;max-width:100%}
#kevia-agent button{cursor:pointer}#kevia-agent article{border-top:1px solid var(--border,#334155);padding:16px 0}#kevia-agent summary{cursor:pointer}#kevia-agent pre{font-size:12px}#kevia-agent a{color:inherit}
</style><section class='card' id='kevia-agent'><h2>"""+"KEVIA · Missão do agente</h2>"
    out += "<form method='get' action='/ia-keiper/"+cid+"#kevia-agent'><label for='kevia-mission'>Objetivo</label> <select name='missao' id='kevia-mission'>"
    for key, label in MISSIONS.items():
        out += "<option value='"+key+"'"+(' selected' if mission['mission']==key else '')+">"+label+"</option>"
    out += "</select> <button type='submit'>Analisar prioridades</button></form>"
    out += '<details><summary>Fontes e limites</summary><p>Planejamento por regras sobre os diagnósticos salvos. Até três sinais de cada fonte; não é uma revisão de todos os anúncios. Sem chamadas pagas ou alterações no Mercado Livre.</p><ul>'
    for source in mission['sources']:
        out += '<li>'+safe(source['name'])+' · '+safe(source['day'] or 'sem análise')+' · '+('disponível' if source['ready'] else 'bloqueada')+'</li>'
    for reason in mission['limitations']:
        out += '<li>'+safe(reason)+'</li>'
    out += '</ul></details>'
    if not mission['tasks']:
        out += '<p>Nenhuma prioridade sustentada pelas fontes disponíveis para este objetivo.</p>'
    for index, task in enumerate(mission['tasks'], 1):
        href = '/ads/'+cid if task['category']=='ads' else '/vendas/'+cid
        if task['category']=='qualidade':
            href = '/painel/'+cid
        if task['campaign_id']:
            href = '/ads/'+cid+'/campanha/'+quote(task['campaign_id'], safe='')
        out += '<article><h3>'+str(index)+'. '+safe(task['title'])+'</h3><p>'+safe(task['action'])+'</p>'
        source = task['source']
        out += '<details><summary>Evidências e plano preparado</summary><p>Fonte: '+safe(source['name'])+' · '+safe(source['start'])+' a '+safe(source['end'])+'</p>'
        out += '<pre style="white-space:pre-wrap;overflow-wrap:anywhere">'+safe(json.dumps(task['evidence'],ensure_ascii=False,indent=2,default=str))+'</pre>'
        out += '<ol><li>Conferir o período e as ressalvas da fonte.</li><li>'+safe(task['action'])+'</li><li>Registrar a decisão e comparar o próximo diagnóstico antes de ampliar a intervenção.</li></ol></details>'
        out += '<a href="'+safe(href)+'">Conferir na origem ↗</a></article>'
    return out+'</section>'
