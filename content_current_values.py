"""Bounded display of returned values; never validates or infers product facts."""
import math

TEXT_LIMIT = 256
VARIATION_VALUES_LIMIT = 1000


def text(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    try:
        raw = str(value)
    except (ValueError, OverflowError):
        return None
    raw = raw[:TEXT_LIMIT + 1]
    result = ' '.join(raw.split())
    return result[:TEXT_LIMIT] + ('… [resumido]' if len(raw) > TEXT_LIMIT else '') if result else None


def simple(row, name='value_name', identifier='value_id', structure='value_struct'):
    if not isinstance(row, dict):
        return None
    parts = []
    label, code = text(row.get(name)), text(row.get(identifier))
    raw_id = row.get(identifier)
    na = raw_id == '-1' or type(raw_id) is int and raw_id == -1
    if na:
        parts.append('Não aplicável declarado (ID -1)')
    if label:
        parts.append(label)
    if code and not na:
        parts.append('ID ' + code)
    raw = row.get(structure)
    if isinstance(raw, dict):
        number, unit = text(raw.get('number')), text(raw.get('unit'))
        if number is not None and unit is not None:
            parts.append('Estruturado: ' + number + ' ' + unit)
    return ' · '.join(parts) if parts else None


def describe(row):
    if not isinstance(row, dict):
        return 'Formato não exibido'
    parts = []
    value = simple(row)
    if value:
        parts.append(value)
    values = row.get('values')
    if isinstance(values, list) and values:
        # Keep multi-value evidence distinct from the simple top-level value.
        displayed = [simple(v, 'name', 'id', 'struct') or 'Formato não exibido' for v in values[:3]]
        parts.append('Valores: ' + '; '.join(displayed))
        if len(values) > 3:
            parts.append('3 de ' + str(len(values)) + ' valores [resumido]')
    result = ' | '.join(parts) if parts else 'Formato vazio ou não exibido'
    return result if len(result) <= TEXT_LIMIT else result[:TEXT_LIMIT] + '… [resumido]'


def collect(index, codes):
    details = {}
    main = index.value_groups[0]
    if main is not None:
        for code, row in main.items():
            if code in codes:
                details.setdefault(code, {})['main'] = describe(row)
    used = 0
    limited = False
    if index.variants is not None:
        for group_number, group in enumerate(index.value_groups[1:]):
            if group is None:
                continue
            variant = str(group_number // 2)
            source = 'Atributo da variação: ' if group_number % 2 == 0 else 'Combinação: '
            for code, row in group.items():
                if code not in codes:
                    continue
                if used >= VARIATION_VALUES_LIMIT:
                    limited = True
                    break
                details.setdefault(code, {}).setdefault('variants', {}).setdefault(variant, []).append(source + describe(row))
                used += 1
            if limited:
                break
    return dict(details=details, limited=limited)
