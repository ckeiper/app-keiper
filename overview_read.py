"""Bound the complete overview read before the web worker's timeout."""
import time
import logging

READ_SECONDS = 12
TIMEOUT_MESSAGE = ('A consulta excedeu o tempo disponível. Tente novamente ou selecione '
                   'um período menor. Nenhum total parcial foi apresentado.')


def bounded_query(conn, query):
    deadline = time.monotonic() + READ_SECONDS

    def read(connection, sql, params):
        remaining = int((deadline - time.monotonic()) * 1000)
        if remaining <= 0:
            raise ValueError(TIMEOUT_MESSAGE)
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT set_config('jit', 'off', true), "
                               "set_config('statement_timeout', %s, true)",
                               (str(remaining),))
            return query(connection, sql, params)
        except Exception as exc:
            if getattr(exc, 'pgcode', None) == '57014':
                stage = ('daily' if 'WITH candidates AS MATERIALIZED' in sql else
                         'unusual' if 'vendas_dia_coleta FROM pedidos' in sql else
                         'coverage' if 'FROM vendas_cobertura' in sql else 'errors')
                logging.getLogger(__name__).warning('overview_read_timeout stage=%s', stage)
                raise ValueError(TIMEOUT_MESSAGE) from exc
            raise
    return read
