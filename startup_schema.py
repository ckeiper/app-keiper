"""Avoid no-op exclusive locks and retry complete schema transactions only."""
import re
import time
import psycopg2

ADD_COLUMN = re.compile(r'^\s*ALTER\s+TABLE\s+([a-z_][a-z_0-9]*)\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+([a-z_][a-z_0-9]*)\b',re.I)
TRANSIENT = {'40P01','55P03','40001'}


def schema_executor(execute):
    """Existing columns need no ALTER/AccessExclusiveLock, even with IF NOT EXISTS.

    The catalog check follows the same search_path as the original ALTER.
    Missing columns still use PostgreSQL's original idempotent DDL.
    """
    def run(conn, sql, params=None):
        match = ADD_COLUMN.match(sql)
        if match:
            table,column = match.groups()
            cursor = execute(conn, '''SELECT 1 FROM pg_attribute
                WHERE attrelid=to_regclass(%s) AND attname=%s
                  AND attnum>0 AND NOT attisdropped''', (table.lower(),column.lower()))
            if cursor.fetchone():
                return cursor
        return execute(conn,sql,params)
    return run


def initialize_with_retry(initialize, logger, sleep=time.sleep, attempts=4):
    """Caller must open a fresh transaction each attempt; never skip required DDL."""
    for attempt in range(attempts):
        try:
            return initialize()
        except psycopg2.Error as exc:
            if exc.pgcode not in TRANSIENT or attempt+1 >= attempts:
                raise
            # SQL/error messages can contain data: log only SQLSTATE/attempt.
            logger.warning('schema_startup_retry sqlstate=%s attempt=%s',exc.pgcode,attempt+1)
            sleep(min(2**attempt,4))
