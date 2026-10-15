"""Sales indicators without Flask, database access or import-time side effects."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

# Brazilian marketplace reporting day; never use the server's timezone.
SAO_PAULO = timezone(timedelta(hours=-3))
PRESETS = (7, 15, 30, 60, 90)


def reporting_today():
    return datetime.now(SAO_PAULO).date()


def period(args, today=None):
    today = today or reporting_today()
    choice = args.get("periodo", "30")
    if choice == "personalizado":
        try:
            start = date.fromisoformat(args.get("inicio", ""))
            end = date.fromisoformat(args.get("fim", ""))
        except (TypeError, ValueError):
            raise ValueError("Informe as datas inicial e final válidas.")
        if end < start or end > today:
            raise ValueError("O início deve preceder o fim; o fim não pode estar no futuro.")
        if (end - start).days >= 366:
            raise ValueError("Selecione no máximo 366 dias.")
    else:
        if choice not in tuple(map(str, PRESETS)):
            raise ValueError("Selecione 7, 15, 30, 60 ou 90 dias, ou um período personalizado.")
        end = today
        start = end - timedelta(days=int(choice) - 1)
    days = (end - start).days + 1
    return start, end, start - timedelta(days=days), start - timedelta(days=1)


def created_day(value):
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return None
        return stamp.astimezone(SAO_PAULO).date()
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None


def invalid_date_days(row):
    """Possible days for a broken timestamp, for integrity checks only.

    A collection day comes from the API's explicit date_created filter. A
    readable calendar prefix without a valid timezone has a one-day margin.
    Neither is a replacement creation date for counting a sale.
    """
    try:
        return {date.fromisoformat(row.get("vendas_dia_coleta"))}
    except (TypeError, ValueError):
        pass
    raw = row.get("criado_em")
    try:
        day = date.fromisoformat(raw[:10])
    except (TypeError, ValueError):
        return set()
    return {day + timedelta(days=offset) for offset in (-1, 0, 1)
            if date.min.toordinal() <= day.toordinal() + offset <= date.max.toordinal()}


def amount(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result >= 0 else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def order_fields(order):
    """Keep only fields needed for reporting; no buyer or payment credentials."""
    payments = order.get("payments")
    payments = ([{"id": p.get("id"), "status": p.get("status")}
                 for p in payments]
                if isinstance(payments, list) and all(isinstance(p, dict) for p in payments) else None)
    items = order.get("order_items")
    units = None
    if isinstance(items, list) and items:
        quantities = [i.get("quantity") for i in items if isinstance(i, dict)]
        if (len(quantities) == len(items) and
                all(type(q) is int and q > 0 for q in quantities)):
            units = sum(quantities)
    return order.get("date_created"), payments, units


def summarize(rows, start, end, covered):
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    daily = {d: Decimal(0) for d in days}
    revenue, orders, units, cancellations = Decimal(0), 0, 0, 0
    unknown_units = 0
    invalid = 0
    invalid_dates = 0
    unallocated_dates = 0
    bad_days = set()
    seen = set()
    for row in rows:
        key = (row.get("conexao_id"), row.get("pedido_id"))
        if key in seen:
            continue
        seen.add(key)
        day = created_day(row.get("criado_em"))
        if day is None:
            possible = invalid_date_days(row)
            affected = {d for d in possible if start <= d <= end}
            if affected:
                invalid += 1
                invalid_dates += 1
                bad_days.update(affected)
            elif not possible:
                # Cannot locate this record in either interval. Keep it visible
                # as a separate integrity issue, not an error in every period.
                unallocated_dates += 1
            continue
        if not start <= day <= end:
            continue
        if row.get("status") == "cancelled":
            cancellations += 1
            continue
        if row.get("status") != "paid":
            continue
        payments = row.get("pagamentos_json")
        if (not isinstance(payments, list) or
                any(not isinstance(p, dict) or not p.get("status") for p in payments) or
                (row.get("status") == "paid" and not payments)):
            invalid += 1
            bad_days.add(day)
            continue
        approved = any(p.get("status") == "approved" for p in payments)
        if not approved:
            continue
        value = amount(row.get("total"))
        if row.get("moeda") != "BRL" or value is None:
            invalid += 1
            bad_days.add(day)
            continue
        revenue += value
        daily[day] += value
        orders += 1
        qty = row.get("unidades")
        if type(qty) is int and qty > 0:
            units += qty
        else:
            unknown_units += 1
    complete = all(d.isoformat() in covered for d in days)
    reliable = complete and invalid == 0
    return {
        "revenue": revenue if reliable else None,
        "orders": orders if reliable else None,
        "units": units if reliable and not unknown_units else None,
        "ticket": revenue / orders if reliable and orders else None,
        "unit_price": revenue / units if reliable and units and not unknown_units else None,
        "cancellations": cancellations if complete and not invalid_dates else None,
        "returns": None, "refunds": None,
        "daily": [float(daily[d]) if d.isoformat() in covered and d not in bad_days else None for d in days],
        "days": [d.isoformat() for d in days],
        "complete": complete, "invalid": invalid, "unknown_units": unknown_units,
        "invalid_dates": invalid_dates, "unallocated_dates": unallocated_dates,
    }


def change(current, previous):
    if current is None or previous is None:
        return None
    if previous == 0:
        return Decimal(0) if current == 0 else None
    return (current - previous) * 100 / previous
