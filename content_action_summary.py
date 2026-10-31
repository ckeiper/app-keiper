"""Actionable summary of existing evidence, without new marketplace rules."""
from html import escape


def actions(result):
    rows = []
    requirements = result.get('requirements', {})
    if requirements.get('state') != 'read':
        rows.append(('unknown', 'Requisitos da categoria', 'Tente consultar novamente; não foi possível conferir os requisitos.'))
    else:
        if requirements.get('total', 0) > len(requirements.get('rows', [])):
            rows.append(('unknown', 'Cobertura dos requisitos', 'A lista exibida é limitada; confira os demais requisitos no Mercado Livre.'))
        for row in requirements.get('rows', []):
            confirmed = row.get('required') is True or row.get('conditional_confirmed') is True
            if row.get('state') == 'review':
                action = ('Confira o preenchimento no anúncio e nas variações aplicáveis; nenhum erro de publicação foi confirmado.' if confirmed else
                          'Confira a aplicabilidade da regra condicional antes de recomendar preenchimento.')
                rows.append(('review' if confirmed else 'unknown', row['name'], action))
            elif row.get('state') == 'unknown':
                rows.append(('unknown', row['name'], 'Confira o valor no Mercado Livre; a resposta não permite determinar o preenchimento.'))
            if row.get('length_findings'):
                rows.append(('review', row['name'], 'Confira os valores que excedem o comprimento retornado pela categoria; os detalhes estão abaixo.'))
    for key, label in [('attribute_units', 'Unidades'), ('boolean_values', 'Atributos sim/não'), ('list_values', 'Opções de lista'), ('number_values', 'Números simples')]:
        group = result.get(key, {})
        if group.get('state') != 'read':
            rows.append(('unknown', label, 'Consulta não verificada; repita a leitura antes de concluir sobre os valores.'))
            continue
        for row in group.get('rows', []):
            if row.get('state') not in ('review', 'unknown'):
                continue
            location = row.get('location', '')
            if row.get('managed'):
                action = 'Campo gerenciado pelo Mercado Livre: confira a origem da informação, sem recomendar edição direta.'
            elif row['state'] == 'review':
                action = 'Confira o valor e a regra retornada pela categoria nos detalhes abaixo; a divergência não confirma erro de publicação.'
            else:
                action = 'Confira o valor na ficha do Mercado Livre; a resposta não permite validá-lo.'
            rows.append((row['state'], row.get('name', label) + (' · '+location if location else ''), action))
        if group.get('variation_unknown') or group.get('truncated'):
            rows.append(('unknown', label+' · cobertura', 'A leitura não cobre integralmente as variações ou os atributos; confira os limites nos detalhes.'))
    return rows


def render(result):
    rows = actions(result)
    counts = {state: sum(row[0] == state for row in rows) for state in ('review', 'unknown')}
    esc = lambda value: escape(str(value), quote=True)
    out = '<section class="cs-actions" aria-label="Próximas ações de conteúdo"><h4>Próximas ações</h4>'
    out += '<p>'+str(counts['review'])+' pontos para conferir · '+str(counts['unknown'])+' pontos não verificados ou com aplicabilidade pendente.</p>'
    out += '<p>Contagens de apontamentos, sem nota de qualidade ou percentual de completude. Ficha técnica opcional e revisão de imagens permanecem nos detalhes.</p>'
    if not rows:
        out += '<p>Nenhum apontamento nas regras conferidas. Isso não certifica a validade ou a qualidade integral do anúncio.</p>'
    else:
        out += '<ol>'
        for state, name, action in rows[:100]:
            out += '<li data-action-state="'+state+'"><strong>'+esc(name)+'</strong><p>'+esc(action)+'</p></li>'
        out += '</ol>'
        if len(rows) > 100:
            out += '<p>Exibidos os primeiros 100 de '+str(len(rows))+' apontamentos. Confira os detalhes abaixo.</p>'
    return out+'</section><style>.cs-actions{border:1px solid #426184;border-radius:12px;padding:16px;margin:16px 0;overflow-wrap:anywhere}.cs-actions ol{padding-left:24px}.cs-actions li{padding:10px 8px;border-bottom:1px solid #426184}.cs-actions li[data-action-state=review]{border-left:3px solid #c08d54}.cs-actions li p{margin:6px 0}</style>'
