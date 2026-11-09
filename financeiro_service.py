"""Transactional operations for Keiper's admin-only receivables module."""
from datetime import date
from financeiro_store import cents, due_date
from calendar import monthrange
from datetime import datetime
from zoneinfo import ZoneInfo


def today_br():
    return datetime.now(ZoneInfo('America/Sao_Paulo')).date()


def sync_finance(conn):
    imported = import_integrated_clients(conn)
    today = today_br()
    with conn.cursor() as cur:
        cur.execute('''INSERT INTO financeiro_mensalidades (contrato_id,competencia,vencimento,valor_centavos)
            SELECT c.id,mes::date,mes::date+4,c.valor_centavos FROM financeiro_contratos c
            CROSS JOIN LATERAL generate_series(date_trunc('month',c.inicio::timestamp),
                date_trunc('month',LEAST(COALESCE(c.fim,%s),%s)::timestamp), interval '1 month') AS meses(mes)
            WHERE c.ativo=TRUE ON CONFLICT (contrato_id,competencia) DO NOTHING''', (today, today))
    return imported


def consolidate_account(conn, client_id, account_id):
    """Explicit consolidation only for an imported client with no contracts."""
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(58410501)")
        cur.execute("SELECT cliente_id FROM financeiro_vinculos WHERE conexao_id=%s FOR UPDATE", (account_id,))
        row = cur.fetchone()
        if not row or row[0] == client_id:
            return link_account(conn, client_id, account_id)
        source = row[0]
        cur.execute("SELECT id FROM financeiro_clientes WHERE id IN (%s,%s) ORDER BY id FOR UPDATE", (source, client_id))
        if len(cur.fetchall()) != 2:
            raise ValueError('Cliente não encontrado')
        cur.execute("SELECT 1 FROM financeiro_contratos WHERE cliente_id=%s", (source,))
        if cur.fetchone():
            raise ValueError('Cliente de origem possui contratos. O histórico e o vínculo foram preservados.')
        cur.execute("UPDATE financeiro_vinculos SET cliente_id=%s WHERE conexao_id=%s", (client_id, account_id))
        cur.execute("DELETE FROM financeiro_clientes c WHERE c.id=%s AND c.importado AND NOT EXISTS (SELECT 1 FROM financeiro_vinculos v WHERE v.cliente_id=c.id)", (source,))


def import_integrated_clients(conn):
    """Import accounts without duplicates; repeatable and safe for multiple stores."""
    with conn.cursor() as cur:
        # Serialize discovery and creation in the same transaction. A losing
        # importer must never leave an unlinked financial client behind.
        cur.execute("SELECT pg_advisory_xact_lock(58410501)")
        cur.execute("""
            SELECT c.id, c.cliente
            FROM conexoes c
            LEFT JOIN financeiro_vinculos v ON v.conexao_id = c.id
            WHERE v.conexao_id IS NULL
            ORDER BY c.id
        """)
        accounts = cur.fetchall()
        for account_id, name in accounts:
            # One financial client per previously unlinked store. Explicit linking
            # handles clients with multiple stores; names alone are not safe identifiers.
            cur.execute(
                "INSERT INTO financeiro_clientes (nome,importado) VALUES (%s,TRUE) RETURNING id",
                (name or ('Loja #' + str(account_id)),)
            )
            client_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO financeiro_vinculos (conexao_id, cliente_id) "
                "VALUES (%s, %s) ON CONFLICT (conexao_id) DO NOTHING",
                (account_id, client_id)
            )
    return len(accounts)


def create_manual_client(conn, name, phone=None, email=None):
    name = (name or "").strip()
    if not name:
        raise ValueError("Nome do cliente é obrigatório")
    if len(name) > 300 or len(phone or '') > 50 or len(email or '') > 300:
        raise ValueError('Confira o tamanho dos dados do cliente')
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO financeiro_clientes (nome, telefone, email) "
            "VALUES (%s, %s, %s) RETURNING id",
            (name, phone, email)
        )
        return cur.fetchone()[0]


def link_account(conn, client_id, account_id):
    """Explicitly attach a store to an existing financial client."""
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(58410501)")
        cur.execute("SELECT cliente_id FROM financeiro_vinculos WHERE conexao_id=%s", (account_id,))
        existing = cur.fetchone()
        if existing and existing[0] != client_id:
            raise ValueError("Loja já vinculada a outro cliente. O vínculo existente foi preservado.")
        cur.execute(
            "INSERT INTO financeiro_vinculos (conexao_id, cliente_id) "
            "VALUES (%s, %s) ON CONFLICT (conexao_id) "
            "DO NOTHING",
            (account_id, client_id)
        )


def create_contract(conn, client_id, amount, start):
    value = cents(amount)
    start = date.fromisoformat(str(start))
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(58410501)")
        cur.execute(
            "INSERT INTO financeiro_contratos "
            "(cliente_id, valor_centavos, dia_vencimento, inicio) "
            "VALUES (%s, %s, 5, %s) RETURNING id",
            (client_id, value, start)
        )
        return cur.fetchone()[0]


def issue_month(conn, year, month):
    """Create at most one invoice per active contract per month."""
    due = due_date(year, month)
    competence = date(year, month, 1)
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO financeiro_mensalidades
                (contrato_id, competencia, vencimento, valor_centavos)
            SELECT id, %s, %s, valor_centavos
              FROM financeiro_contratos
             WHERE ativo = TRUE AND inicio <= %s
               AND (fim IS NULL OR fim >= %s)
            ON CONFLICT (contrato_id, competencia) DO NOTHING
        """, (competence, due, date(year, month, monthrange(year, month)[1]), competence))
        return cur.rowcount


def record_payment(conn, invoice_id, amount, payment_date, method="pix", note=None, key=None, actor=None):
    value = cents(amount)
    payment_date = date.fromisoformat(str(payment_date))
    if value <= 0:
        raise ValueError("Pagamento deve ser maior que zero")
    if method not in ("pix", "transferencia"):
        raise ValueError("Meio de pagamento inválido")
    if len(note or '') > 1000:
        raise ValueError('Observação muito longa')
    with conn.cursor() as cur:
        cur.execute(
            "SELECT valor_centavos FROM financeiro_mensalidades "
            "WHERE id = %s FOR UPDATE", (invoice_id,)
        )
        row = cur.fetchone()
        if not row:
            raise ValueError("Mensalidade não encontrada")
        if key:
            cur.execute('SELECT id,mensalidade_id,valor_centavos,data_pagamento,meio FROM financeiro_pagamentos WHERE chave=%s', (key,))
            previous = cur.fetchone()
            if previous:
                if previous[1:] != (invoice_id, value, payment_date, method):
                    raise ValueError('Chave de pagamento já utilizada')
                return previous[0]
        cur.execute(
            "SELECT COALESCE(SUM(valor_centavos), 0) "
            "FROM financeiro_pagamentos WHERE mensalidade_id = %s",
            (invoice_id,)
        )
        paid = cur.fetchone()[0]
        if value > row[0] - paid:
            raise ValueError("Pagamento supera o saldo da mensalidade")
        cur.execute(
            "INSERT INTO financeiro_pagamentos "
            "(mensalidade_id, valor_centavos, data_pagamento, meio, observacao, chave, registrado_por) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (invoice_id, value, payment_date, method, note, key, actor)
        )
        return cur.fetchone()[0]
