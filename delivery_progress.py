"""Delivery stages are distinct from audited capability completion and chart totals."""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from html import escape

STAGES = {
    'planejada': 'Planejada',
    'em_desenvolvimento': 'Em desenvolvimento',
    'aguardando_testes': 'Aguardando testes',
    'aprovada': 'Aprovada',
    'publicada': 'Publicada em produção',
    'parcialmente_concluida': 'Parcialmente concluída',
    'concluida': 'Concluída',
}
PUBLISHED = {'publicada', 'parcialmente_concluida', 'concluida'}


def stamp(value):
    if not isinstance(value, str):
        raise ValueError('Data da entrega ausente.')
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() != timedelta(hours=-3):
        raise ValueError('Registre a data da entrega no horário de Brasília.')
    return parsed


def sha(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{40}', value) is not None


def validate(model, capability_ids):
    if not isinstance(model, dict) or type(model.get('versao')) is not int or model.get('versao') != 1 or not isinstance(model.get('entregas'), list):
        raise ValueError('Registro de entregas inválido.')
    seen = set()
    for row in model['entregas']:
        if not isinstance(row, dict):
            raise ValueError('Entrega inválida.')
        key = row.get('id')
        if not isinstance(key, str) or not re.fullmatch(r'[a-z0-9-]{1,100}', key) or key in seen:
            raise ValueError('Identificador de entrega inválido ou repetido.')
        seen.add(key)
        state = row.get('etapa')
        if state not in STAGES:
            raise ValueError('Etapa de entrega inválida.')
        if not isinstance(row.get('escopo'), str) or not row['escopo'].strip():
            raise ValueError('Descreva o escopo da entrega.')
        fronts = row.get('frentes')
        if (not isinstance(fronts, list) or not fronts or any(not isinstance(f, str) or f not in capability_ids for f in fronts)
                or len(fronts) != len(set(fronts))):
            raise ValueError('Entrega sem associação verificável às frentes auditadas.')
        stamp(row.get('atualizado_em'))
        if row.get('pr') is not None and (type(row['pr']) is not int or row['pr'] <= 0):
            raise ValueError('PR inválido.')
        if row.get('head_sha') is not None and not sha(row['head_sha']):
            raise ValueError('Commit inválido.')
        if not isinstance(row.get('lacuna'), str):
            raise ValueError('Declare a lacuna da entrega, mesmo quando vazia.')
        if state not in {'planejada', 'em_desenvolvimento'}:
            if type(row.get('pr')) is not int or row['pr'] <= 0 or not sha(row.get('head_sha')):
                raise ValueError('Etapa exige PR e commit identificado.')
        if state in PUBLISHED | {'aprovada'}:
            checks = row.get('checks')
            if not isinstance(checks, list) or not checks:
                raise ValueError('Aprovação sem evidências de checks.')
            for check in checks:
                if (not isinstance(check, dict) or not isinstance(check.get('nome'), str) or not check['nome'].strip()
                        or type(check.get('run_id')) is not int or check['run_id'] <= 0
                        or check.get('resultado') != 'success' or check.get('head_sha') != row['head_sha']):
                    raise ValueError('Check não aprovado ou de outro commit.')
        publication = row.get('publicacao')
        if state in PUBLISHED:
            if (not isinstance(publication, dict) or publication.get('status') != 'live'
                    or not re.fullmatch(r'dep-[a-z0-9]+', str(publication.get('deploy_id', '')))
                    or not sha(publication.get('commit'))):
                raise ValueError('Publicação sem deploy live e commit identificado.')
            if stamp(publication.get('horario_brasilia')) > stamp(row['atualizado_em']):
                raise ValueError('Registro da entrega anterior à publicação.')
        elif publication is not None:
            raise ValueError('Etapa anterior à publicação não pode registrar deploy publicado.')
        if state == 'parcialmente_concluida' and not row['lacuna'].strip():
            raise ValueError('Entrega parcial sem lacuna descrita.')
        if state == 'concluida' and (row['lacuna'].strip() or row.get('escopo_concluido') is not True):
            raise ValueError('Conclusão sem escopo integral conferido.')
    return model


def read(capability_ids):
    path = Path(__file__).with_name('anuncios_entregas.json')
    return validate(json.loads(path.read_text(encoding='utf-8')), capability_ids)['entregas']


def render_latest(rows):
    if not rows:
        return ''
    latest = max(rows, key=lambda row: stamp(row['atualizado_em']))
    text = 'Última entrega registrada: '+STAGES[latest['etapa']]
    if latest.get('pr'):
        text += ' · PR #'+str(latest['pr'])
    return '<p class="ap-delivery-stage" title="'+escape(latest['escopo'], quote=True)+'">'+escape(text)+'<br>Etapa da entrega; a conclusão das frentes continua contabilizada separadamente.</p>'
