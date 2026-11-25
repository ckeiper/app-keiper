"""Exact bounded option names for input assistance, never inferred values."""
def choices(rule):
    if rule.get('value_type') not in ('string', 'list', 'boolean'):
        return []
    values = rule.get('values')
    if not isinstance(values, list):
        return []
    result = []
    for row in values[:10]:
        name = row.get('name') if isinstance(row, dict) else None
        if (isinstance(name, str) and 0 < len(name) <= 1000 and name.strip()
                and not any(ord(c) < 32 or ord(c) == 127 for c in name)
                and name not in result):
            result.append(name)
    return result
