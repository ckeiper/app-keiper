"""Indexed daily aggregation; unusual timestamps use the exact Python classifier."""

DAY_FUNCTION = r"""
CREATE OR REPLACE FUNCTION keiper_overview_day_v1(raw text) RETURNS date
LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE AS $$
DECLARE
    m text[];
    local_stamp timestamp;
    day date;
    seconds double precision;
    offset_minutes integer;
BEGIN
    -- Only the canonical ML shape is accelerated. Everything else is processed
    -- by sales_metrics.created_day/invalid_date_days, never silently discarded.
    m := regexp_match(raw, '^([0-9]{4})-([0-9]{2})-([0-9]{2})[T ]([0-9]{2}):([0-9]{2}):([0-9]{2})([.][0-9]{1,6})?(Z|[+-][0-9]{2}:[0-9]{2})$');
    IF m IS NULL OR m[1]::integer < 1 OR m[4]::integer > 23
       OR m[5]::integer > 59 OR m[6]::integer > 59 THEN
        RETURN NULL;
    END IF;
    seconds := m[6]::double precision + COALESCE(m[7]::double precision, 0);
    local_stamp := make_timestamp(m[1]::integer,m[2]::integer,m[3]::integer,
                                 m[4]::integer,m[5]::integer,seconds);
    offset_minutes := 0;
    IF m[8] <> 'Z' THEN
        IF substring(m[8],2,2)::integer > 23 OR substring(m[8],5,2)::integer > 59 THEN
            RETURN NULL;
        END IF;
        offset_minutes := substring(m[8],2,2)::integer * 60 + substring(m[8],5,2)::integer;
        IF left(m[8],1) = '-' THEN offset_minutes := -offset_minutes; END IF;
    END IF;
    day := (local_stamp - make_interval(mins => offset_minutes) - interval '3 hours')::date;
    IF day < date '0001-01-01' OR day > date '9999-12-31' THEN RETURN NULL; END IF;
    RETURN day;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$
"""


def init_overview_schema(conn, execute):
    execute(conn, DAY_FUNCTION)
    execute(conn, '''CREATE INDEX IF NOT EXISTS idx_overview_orders_day
        ON pedidos (conexao_id, keiper_overview_day_v1(criado_em))
        WHERE vendas_verificado_em IS NOT NULL AND keiper_overview_day_v1(criado_em) IS NOT NULL''')
    # The overview filters by the raw date prefix before Python's exact
    # timezone classifier. Index that exact expression, only verified rows.
    execute(conn, '''CREATE INDEX IF NOT EXISTS idx_overview_orders_prefix
        ON pedidos (conexao_id, LEFT(criado_em,10), pedido_id)
        WHERE vendas_verificado_em IS NOT NULL''')
    execute(conn, '''CREATE INDEX IF NOT EXISTS idx_overview_orders_unusual
        ON pedidos (conexao_id, pedido_id)
        WHERE vendas_verificado_em IS NOT NULL AND keiper_overview_day_v1(criado_em) IS NULL''')
    execute(conn, '''CREATE INDEX IF NOT EXISTS idx_overview_errors_latest
        ON erros (conexao_id, quando DESC NULLS FIRST)
        WHERE categoria IN ('pedidos','atualizacao','refresh','token')''')


# Cheap date-prefix candidate selection. Exact Brasília reporting days and
# payment verification remain in sales_metrics.summarize, not in this SQL.
PERIOD_ROWS_SQL = """SELECT conexao_id, pedido_id, status, total, moeda,
    criado_em, pagamentos_json, unidades, vendas_dia_coleta
    FROM pedidos
    WHERE conexao_id = ANY(%s) AND vendas_verificado_em IS NOT NULL
      AND LEFT(criado_em, 10) BETWEEN %s AND %s"""

DAILY_SQL = '''WITH candidates AS MATERIALIZED (
    SELECT ids.conexao_id, days.dia::date AS dia,
           status, total, moeda, unidades,
           CASE WHEN jsonb_typeof(pagamentos_json) = 'array'
                THEN pagamentos_json ELSE '[]'::jsonb END AS payments,
           jsonb_typeof(pagamentos_json) IS DISTINCT FROM 'array' AS bad_shape
    FROM unnest(%s::integer[]) AS ids(conexao_id)
    CROSS JOIN generate_series(%s::timestamp, %s::timestamp, interval '1 day') AS days(dia)
    CROSS JOIN LATERAL (
        SELECT status, total, moeda, unidades, pagamentos_json
        FROM pedidos WHERE conexao_id = ids.conexao_id
          AND vendas_verificado_em IS NOT NULL
          AND keiper_overview_day_v1(criado_em) IS NOT NULL
          AND keiper_overview_day_v1(criado_em) BETWEEN days.dia::date AND days.dia::date
        OFFSET 0
    ) AS matching
), payment_checks AS MATERIALIZED (
    SELECT *, bad_shape OR jsonb_array_length(payments) = 0 OR EXISTS (
        SELECT 1 FROM jsonb_array_elements(payments) AS p
        WHERE jsonb_typeof(p) <> 'object' OR NOT (p ? 'status')
           OR p->'status' IN ('null'::jsonb,'false'::jsonb,'0'::jsonb,
                             '""'::jsonb,'[]'::jsonb,'{}'::jsonb)
    ) AS bad_payments,
    EXISTS (SELECT 1 FROM jsonb_array_elements(payments) AS p
            WHERE p->'status' = '"approved"'::jsonb) AS approved,
    COALESCE(total >= 0 AND total < 'Infinity'::real, false) AS valid_total
    FROM candidates
), qualified AS MATERIALIZED (
    SELECT *, status = 'paid' AND NOT bad_payments AND approved
              AND moeda = 'BRL' AND valid_total AS good,
           status = 'paid' AND (bad_payments OR (approved AND
                (moeda IS DISTINCT FROM 'BRL' OR NOT valid_total))) AS bad
    FROM payment_checks
)
SELECT conexao_id, dia,
       COALESCE(sum(CASE WHEN good THEN total::text::numeric ELSE 0 END),0) AS revenue,
       count(*) FILTER (WHERE good) AS orders,
       COALESCE(sum(unidades) FILTER (WHERE good AND unidades > 0),0) AS units,
       count(*) FILTER (WHERE good AND (unidades IS NULL OR unidades <= 0)) AS unknown_units,
       count(*) FILTER (WHERE status = 'cancelled') AS cancellations,
       count(*) FILTER (WHERE bad) AS invalid
FROM qualified GROUP BY conexao_id, dia ORDER BY conexao_id, dia'''


UNUSUAL_SQL = '''SELECT conexao_id, pedido_id, status, total, moeda,
    criado_em, pagamentos_json, unidades, vendas_dia_coleta FROM pedidos
    WHERE conexao_id = ANY(%s) AND vendas_verificado_em IS NOT NULL
      AND keiper_overview_day_v1(criado_em) IS NULL'''


LATEST_ERRORS_SQL = '''SELECT ids.conexao_id, latest.quando
    FROM unnest(%s::integer[]) AS ids(conexao_id)
    CROSS JOIN LATERAL (
        SELECT quando FROM erros WHERE conexao_id = ids.conexao_id
          AND categoria IN ('pedidos','atualizacao','refresh','token')
        ORDER BY quando DESC NULLS FIRST LIMIT 1
    ) AS latest'''
