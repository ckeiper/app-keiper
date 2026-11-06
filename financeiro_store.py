"""Financeiro Keiper: independent client registry and monthly receivables.

No marketplace credentials or payment automation are required.
Amounts are stored as integer cents to avoid rounding errors.
"""
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def cents(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("Valor monetário inválido")
    if not amount.is_finite() or amount < 0:
        raise ValueError("Valor monetário deve ser positivo ou zero")
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def init_finance_schema(conn, execute):
    execute(conn, """CREATE TABLE IF NOT EXISTS financeiro_clientes (
        id SERIAL PRIMARY KEY,
        nome TEXT NOT NULL,
        telefone TEXT,
        email TEXT,
        ativo BOOLEAN NOT NULL DEFAULT TRUE,
        criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""")
    execute(conn, """CREATE TABLE IF NOT EXISTS financeiro_vinculos (
        conexao_id INTEGER PRIMARY KEY REFERENCES conexoes(id) ON DELETE CASCADE,
        cliente_id INTEGER NOT NULL REFERENCES financeiro_clientes(id) ON DELETE CASCADE
    )""")
    execute(conn, """CREATE TABLE IF NOT EXISTS financeiro_contratos (
        id SERIAL PRIMARY KEY,
        cliente_id INTEGER NOT NULL REFERENCES financeiro_clientes(id),
        valor_centavos BIGINT NOT NULL CHECK (valor_centavos >= 0),
        dia_vencimento INTEGER NOT NULL CHECK (dia_vencimento BETWEEN 1 AND 31),
        inicio DATE NOT NULL,
        fim DATE,
        ativo BOOLEAN NOT NULL DEFAULT TRUE,
        CHECK (fim IS NULL OR fim >= inicio)
    )""")
    execute(conn, """CREATE TABLE IF NOT EXISTS financeiro_mensalidades (
        id SERIAL PRIMARY KEY,
        contrato_id INTEGER NOT NULL REFERENCES financeiro_contratos(id),
        competencia DATE NOT NULL,
        vencimento DATE NOT NULL,
        valor_centavos BIGINT NOT NULL CHECK (valor_centavos >= 0),
        criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (contrato_id, competencia)
    )""")
    execute(conn, """CREATE TABLE IF NOT EXISTS financeiro_pagamentos (
        id SERIAL PRIMARY KEY,
        mensalidade_id INTEGER NOT NULL REFERENCES financeiro_mensalidades(id),
        valor_centavos BIGINT NOT NULL CHECK (valor_centavos > 0),
        data_pagamento DATE NOT NULL,
        meio TEXT NOT NULL CHECK (meio IN ('pix', 'transferencia')),
        observacao TEXT,
        criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""")
    execute(conn, """CREATE INDEX IF NOT EXISTS idx_financeiro_mensalidades_vencimento
        ON financeiro_mensalidades(vencimento)""")
    execute(conn, """CREATE INDEX IF NOT EXISTS idx_financeiro_pagamentos_mensalidade
        ON financeiro_pagamentos(mensalidade_id)""")


def due_date(year, month, day):
    """Use the last day of shorter months for 29/30/31 due dates."""
    from calendar import monthrange
    return date(year, month, min(day, monthrange(year, month)[1]))


def balance_status(amount_cents, paid_cents, due, today=None):
    today = today or date.today()
    remaining = max(0, amount_cents - paid_cents)
    if remaining == 0:
        return "pago"
    if due < today:
        return "atrasado" if paid_cents == 0 else "parcial_atrasado"
    return "aberto" if paid_cents == 0 else "parcial"
