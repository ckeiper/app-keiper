"""Conservative matching core for a *validated* reconciliation report layout.

The caller must map a real Mercado Livre workbook to these normalized fields.
No automatic inference from unknown report columns is allowed. This module
does not make API requests or write to the database.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation


class ReconciliationError(ValueError):
    pass


def _amount(value):
    """Normalized numeric input (not localized spreadsheet text)."""
    if isinstance(value, bool) or value is None:
        raise ReconciliationError("Valor financeiro ausente ou inválido.")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ReconciliationError("Valor financeiro inválido.") from exc
    if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
        raise ReconciliationError("Valor deve ser positivo, com até duas casas decimais.")
    return amount.quantize(Decimal("0.01"))


def compare_normalized_freight(ledger_entries, dashboard_entries):
    """Compare explicitly classified freight debits/refunds by order.

    ledger_entries: [{transaction_id, order_id, kind: debit|refund, amount}]
    dashboard_entries: [{order_id, shipment_id, amount}]

    Output statuses: matched, difference, missing_dashboard, missing_ledger,
    ambiguous_dashboard. Differences are observations, not improper charges.
    """
    transactions = set()
    ledger = defaultdict(lambda: Decimal("0.00"))
    for row in ledger_entries:
        oid = str(row.get("order_id") or "").strip()
        tid = str(row.get("transaction_id") or "").strip()
        kind = row.get("kind")
        if not oid or not tid or kind not in ("debit", "refund"):
            raise ReconciliationError("Lançamento sem venda, transação ou tipo válido.")
        if tid in transactions:
            raise ReconciliationError("Transação duplicada na planilha: " + tid)
        transactions.add(tid)
        value = _amount(row.get("amount"))
        ledger[oid] += value if kind == "debit" else -value

    dashboard = defaultdict(list)
    for row in dashboard_entries:
        oid = str(row.get("order_id") or "").strip()
        sid = str(row.get("shipment_id") or "").strip()
        if not oid or not sid:
            raise ReconciliationError("Envio sem identificação da venda ou do envio.")
        dashboard[oid].append((sid, _amount(row.get("amount"))))

    results = []
    for oid in sorted(set(ledger) | set(dashboard)):
        charges = dashboard.get(oid, [])
        net = ledger.get(oid)
        if not charges:
            status, expected, difference = "missing_dashboard", None, None
        elif len(charges) != 1:
            # More than one shipment needs an explicit allocation rule from
            # real data; summing automatically may hide repeated charges.
            status, expected, difference = "ambiguous_dashboard", None, None
        elif net is None:
            status, expected, difference = "missing_ledger", charges[0][1], None
        else:
            expected = charges[0][1]
            difference = net - expected
            status = "matched" if difference == 0 else "difference"
        results.append({"order_id": oid, "status": status,
                        "ledger_net": net, "dashboard_cost": expected,
                        "difference": difference,
                        "shipments": [sid for sid, _ in charges]})
    return results
