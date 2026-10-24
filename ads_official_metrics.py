"""Official Product Ads sales metrics; missing values are never estimated."""
import math


def value(metrics, key, integer=False):
    raw = metrics.get(key)
    if raw is None or isinstance(raw, bool):
        return None
    try:
        number = float(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number < 0 or (integer and not number.is_integer()):
        return None
    return int(number) if integer else number


def init_schema(conn, execute):
    execute(conn, """ALTER TABLE ads_campanha_dia
        ADD COLUMN IF NOT EXISTS impressoes BIGINT,
        ADD COLUMN IF NOT EXISTS vendas_atribuidas INTEGER,
        ADD COLUMN IF NOT EXISTS outras_vendas INTEGER,
        ADD COLUMN IF NOT EXISTS faturamento_sem_ads DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS metricas_vendas_coletadas_em BIGINT""")


def save_day(conn, execute, cid, campaign_id, day, spend, revenue, metrics, observed):
    execute(conn, """INSERT INTO ads_campanha_dia
        (conexao_id, campanha_id, data, gasto, faturamento, atualizado_em,
         vendas_atribuidas, outras_vendas, faturamento_sem_ads, metricas_vendas_coletadas_em, impressoes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (conexao_id, campanha_id, data) DO UPDATE SET
            gasto=EXCLUDED.gasto, faturamento=EXCLUDED.faturamento,
            atualizado_em=EXCLUDED.atualizado_em,
            vendas_atribuidas=EXCLUDED.vendas_atribuidas,
            outras_vendas=EXCLUDED.outras_vendas,
            faturamento_sem_ads=EXCLUDED.faturamento_sem_ads,
            metricas_vendas_coletadas_em=EXCLUDED.metricas_vendas_coletadas_em,
            impressoes=EXCLUDED.impressoes""",
        (cid, campaign_id, day, spend, revenue, observed,
         value(metrics, 'advertising_items_quantity', integer=True),
         value(metrics, 'organic_items_quantity', integer=True),
         value(metrics, 'organic_units_amount'), observed, value(metrics, 'prints', integer=True)))
