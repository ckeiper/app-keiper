"""Global BRL budget, durable reservations and opt-in Responses API adapter."""
import json
import os
from contextlib import closing
from decimal import Decimal, InvalidOperation, ROUND_CEILING

from sales_metrics import reporting_today

INSTRUCTIONS = ('Interprete em português apenas as evidências fornecidas. Não invente causas ou números. '
                'Explique incertezas e até três próximos passos para revisão humana. '
                'Não execute ações nem recomende mudanças automáticas. Máximo 120 palavras.')
OUTPUT_TOKENS = 500


def positive(value):
    try:
        number = Decimal(str(value))
        if number.is_finite() and number > 0:
            return number
    except (InvalidOperation, ValueError, TypeError):
        pass
    raise ValueError('Configuração financeira inválida')


def limit_brl(env=None):
    env = os.environ if env is None else env
    try:
        return positive(env.get('KEIPER_AI_MONTHLY_BRL', '50'))
    except ValueError:
        return Decimal(0)  # Fail closed, including NaN/Infinity.


def settings(env=None):
    env = os.environ if env is None else env
    if (env.get('KEIPER_AI_PAID_ENABLED') != 'true' or
            env.get('KEIPER_AI_PAID_CONFIRMATION') != 'APPROVED' or
            not env.get('OPENAI_API_KEY') or not env.get('KEIPER_AI_MODEL')):
        return None
    try:
        return dict(model=env['KEIPER_AI_MODEL'],
                    input_rate=positive(env.get('KEIPER_AI_INPUT_USD_PER_MILLION')),
                    output_rate=positive(env.get('KEIPER_AI_OUTPUT_USD_PER_MILLION')),
                    fx=positive(env.get('KEIPER_AI_USD_BRL')))
    except ValueError:
        return None


def price(input_tokens, output_tokens, config):
    return ((Decimal(input_tokens)*config['input_rate'] +
             Decimal(output_tokens)*config['output_rate']) * config['fx'] /
            Decimal(1000000)).quantize(Decimal('.000001'), rounding=ROUND_CEILING)


def budget_status(conn, query, today=None):
    month = (today or reporting_today()).replace(day=1)
    rows = query(conn, '''SELECT COALESCE(SUM(committed_brl),0) AS used,
        COALESCE(bool_or(status='overrun'),false) AS overrun
        FROM keiper_ai_usage WHERE month=%s''', (month,))
    used, cap = rows[0]['used'], limit_brl()
    blocked = cap <= 0 or used >= cap or rows[0]['overrun']
    return dict(used=used, limit=cap, blocked=blocked,
                alert='Bloqueio de novas chamadas.' if blocked else
                ('Alerta: 80% do limite comprometido.' if used >= cap*Decimal('.8') else 'Dentro do limite.'))


def interpret(run_id, result, banco, query, execute, post=None):
    config = settings()
    if config is None:
        return None, 'desabilitada ou configuração incompleta'
    relevant = [r for r in result['recommendations'] if r['code'] != 'data_quality']
    if not relevant:
        return None, 'sem caso relevante'
    # Only aggregate numeric evidence and fixed rule text: no customer, shop,
    # campaign names, credentials, order IDs or personal data leave the app.
    payload = json.dumps(dict(start=result['start'], end=result['end'],
                              quality=result['quality'], findings=relevant), ensure_ascii=True)
    if len(payload.encode('utf-8')) > 12000:
        return None, 'evidências acima do limite'
    # Conservative byte bound plus framing margin; all output/reasoning bounded.
    reserved = price(len((INSTRUCTIONS+payload).encode('utf-8'))+1024, OUTPUT_TOKENS, config)
    today = reporting_today()
    month = today.replace(day=1)
    with closing(banco()) as conn, conn:
        query(conn, 'SELECT pg_advisory_xact_lock(880146)')
        state = budget_status(conn, query, today)
        if state['blocked'] or state['used']+reserved > state['limit']:
            return None, 'bloqueada pelo limite mensal'
        rows = query(conn, '''INSERT INTO keiper_ai_usage
            (run_id,month,model,pricing,reserved_brl,committed_brl,status)
            VALUES (%s,%s,%s,%s::jsonb,%s,%s,'reserved')
            ON CONFLICT(run_id) DO NOTHING RETURNING id''',
            (run_id, month, config['model'], json.dumps(config, default=str), reserved, reserved))
        if not rows:
            return None, 'chamada já reservada; sem repetição automática'
        usage_id = rows[0]['id']
    # Reservation is committed BEFORE network I/O. Timeouts/crashes retain it.
    # Never retry an ambiguous call, even after a worker restart.
    try:
        if post is None:
            import requests
            post = requests.post
        response = post('https://api.openai.com/v1/responses',
                        headers={'Authorization': 'Bearer '+os.environ['OPENAI_API_KEY']},
                        json=dict(model=config['model'], instructions=INSTRUCTIONS, input=payload,
                                  max_output_tokens=OUTPUT_TOKENS, store=False), timeout=(5, 40))
        response.raise_for_status()
        data = response.json()
        usage = data['usage']
        tokens = (usage['input_tokens'], usage['output_tokens'])
        if any(type(t) is not int or t < 0 for t in tokens):
            raise ValueError('Invalid usage')
        actual = price(*tokens, config)
        # Charge excess and block the month if a provider/configuration violates
        # the conservative bound. Do not conceal actual reported usage.
        status = 'overrun' if actual > reserved else 'completed'
        with closing(banco()) as conn, conn:
            execute(conn, '''UPDATE keiper_ai_usage SET input_tokens=%s,output_tokens=%s,
                committed_brl=%s,status=%s WHERE id=%s''', (*tokens, actual, status, usage_id))
        text = '\n'.join(part['text'] for output in data.get('output', [])
                         if output.get('type') == 'message'
                         for part in output.get('content', []) if part.get('type') == 'output_text')
        if data.get('status') != 'completed' or not text.strip():
            return None, 'resposta incompleta; uso registrado'
        return text[:4000], 'interpretada; custo estimado registrado'
    except Exception:
        # No exception bodies: provider errors can contain credentials/payloads.
        with closing(banco()) as conn, conn:
            execute(conn, "UPDATE keiper_ai_usage SET status='uncertain' WHERE id=%s AND status='reserved'", (usage_id,))
        return None, 'falha na API; reserva mantida, sem repetição automática'
