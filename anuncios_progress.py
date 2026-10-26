"""Release-versioned progress ledger. No finance, database, or network access."""
from collections import Counter
from datetime import date,datetime
from functools import lru_cache
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parent
STATES={'concluida':'Concluída','em_andamento':'Em desenvolvimento','parcial':'Parcial','pendente':'Pendente','bloqueada':'Bloqueada'}
ORDER={'em_andamento':0,'bloqueada':1,'pendente':2,'parcial':3,'concluida':4}


def validate(model,root=ROOT):
    if model.get('meta_original')!=90:raise ValueError('Meta original inválida.')
    if not re.fullmatch(r'[0-9a-f]{40}',model.get('base_sha','')):raise ValueError('Base inválida.')
    rows=model['capacidades'];ids=set();numbers=set()
    for row in rows:
        if not re.fullmatch(r'[a-z0-9-]{1,80}',row['id']) or row['id'] in ids:raise ValueError('Identificador inválido ou repetido.')
        ids.add(row['id']);state=row['estado']
        if state not in STATES:raise ValueError('Estado inválido.')
        date.fromisoformat(row['atualizado_em'])
        if type(row['prioridade']) is not int or row['prioridade']<1:raise ValueError('Prioridade inválida.')
        if state=='concluida' and (not row['implementado'] or row['falta'] or not row['fontes'] or not row['testes']):
            raise ValueError('Conclusão sem evidências ou com lacuna aberta.')
        if state in ('parcial','pendente','bloqueada') and not row['falta']:raise ValueError('Lacuna não descrita.')
        for name in row['fontes']+row['testes']:
            path=(root/name).resolve()
            if not path.is_relative_to(root.resolve()) or not path.is_file():raise ValueError('Referência ausente ou inválida.')
        if any(type(n) is not int or n<=0 for n in row['prs']):raise ValueError('PR inválido.')
        n=row['numero_original']
        if n is not None:
            if type(n) is not int or not 1<=n<=90 or n in numbers:raise ValueError('Associação original inválida.')
            numbers.add(n)
    if model.get('lista_original_completa'):
        if numbers!=set(range(1,91)):raise ValueError('Lista original incompleta.')
        expected=sum(r['estado']=='concluida' for r in rows if r['numero_original'] is not None)
        if model.get('contagem_das_90')!=expected:raise ValueError('Contagem original inconsistente.')
    elif model.get('contagem_das_90') is not None:raise ValueError('Não contar as 90 sem a lista original.')
    last_day=None
    for event in model['historico']:
        day=date.fromisoformat(event['data'])
        if last_day is not None and day<last_day:raise ValueError('Histórico fora de ordem.')
        last_day=day
        if event.get('base') not in ('frentes_auditadas','originais'):raise ValueError('Base da medição inválida.')
        if any(k not in STATES or type(n) is not int or n<0 for k,n in event['contagens'].items()):raise ValueError('Contagens inválidas.')
        if sum(event['contagens'].values())!=event['total']:raise ValueError('Histórico inconsistente.')
    if not model['historico']:raise ValueError('Histórico vazio.')
    current=summary(model);last=model['historico'][-1]
    if last['base']!=current['base'] or last['total']!=current['total'] or any(last['contagens'].get(k,0)!=v for k,v in current['counts'].items()) or any(current['counts'].get(k,0)!=v for k,v in last['contagens'].items()):raise ValueError('Medição final divergente.')
    for release in model['publicacoes']:
        stamp=datetime.fromisoformat(release['horario_brasilia'])
        if stamp.utcoffset() is None or type(release['pr']) is not int or release['pr']<=0:raise ValueError('Publicação inválida.')
    return model


@lru_cache(maxsize=1)
def read():
    return validate(json.loads((ROOT/'anuncios_progresso.json').read_text(encoding='utf-8')))


def summary(model):
    rows=[row for row in model['capacidades'] if row['numero_original'] is not None] if model['lista_original_completa'] else model['capacidades']
    return dict(total=len(rows),counts=Counter(row['estado'] for row in rows),base='originais' if model['lista_original_completa'] else 'frentes_auditadas')
