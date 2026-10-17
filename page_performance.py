"""Small, dependency-free helpers for safe dashboard query windows."""
from datetime import timedelta
from sales_metrics import reporting_today


def ranking_query_bounds(days, today=None):
    """Include timezone boundary days around both adjacent ranking windows.

    A stored Mercado Livre ISO timestamp may use UTC or -03:00, so its
    calendar prefix can differ from the reporting day by one day.
    """
    if days not in (7, 30):
        raise ValueError("Período não suportado")
    end = today or reporting_today()
    first_day = end - timedelta(days=2 * days - 1)
    return ((first_day - timedelta(days=1)).isoformat(),
            (end + timedelta(days=1)).isoformat(),
            first_day.isoformat(), end.isoformat())
