"""Transactional operations for Keiper's admin-only receivables module."""
from datetime import date
from financeiro_store import cents, due_date


def import_integrated_clients(conn):
    """Import accounts without duplicates; repeatable and safe for multiple stores."""
    with conn.cursor() as cur:
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
                "INSERT INTO financeiro_clientes (nome) VALUES (%s) RETURNING id",
                (name,)
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
        cur.execute(
            "INSERT INTO financeiro_vinculos (conexao_id, cliente_id) "
            "VALUES (%s, %s) ON CONFLICT (conexao_id) "
            "DO UPDATE SET cliente_id = EXCLUDED.cliente_id",
            (account_id, client_id)
        )


def create_contract(conn, client_id, amount, start):
    value = cents(amount)
    with conn.cursor() as cur:
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
        """, (competence, due, due, competence))
        return cur.rowcount


def record_payment(conn, invoice_id, amount, payment_date, method="pix", note=None):
    value = cents(amount)
    if value <= 0:
        raise ValueError("Pagamento deve ser maior que zero")
    if method not in ("pix", "transferencia"):
        raise ValueError("Meio de pagamento inválido")
    with conn.cursor() as cur:
        cur.execute(
            "SELECT valor_centavos FROM financeiro_mensalidades "
            "WHERE id = %s FOR UPDATE", (invoice_id,)
        )
        row = cur.fetchone()
        if not row:
            raise ValueError("Mensalidade não encontrada")
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
            "(mensalidade_id, valor_centavos, data_pagamento, meio, observacao) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (invoice_id, value, payment_date, method, note)
        )
        return cur.fetchone()[0]
