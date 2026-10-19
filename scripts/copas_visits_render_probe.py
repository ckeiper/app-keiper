"""Read-only visits API diagnostic, restricted to Copas (connection ID 5).

Run inside Render with existing DATABASE_URL. No writes, no token output.
"""
import json
import os
import urllib.error
import urllib.request

import psycopg2

COPAS_ID = 5
API = "https://api.mercadolibre.com"
ITEM = "MLB5325240286"


def probe():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL not configured")
    with psycopg2.connect(database_url, connect_timeout=10) as conn:
        conn.set_session(readonly=True)
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT access_token, cliente, status FROM conexoes WHERE id=%s",
                (COPAS_ID,),
            )
            record = cursor.fetchone()
    if not record or record[1] != "Copas Ind" or record[2] != "ativa" or not record[0]:
        raise RuntimeError("Copas connection not available")
    token = record[0]
    url = f"{API}/items/{ITEM}/visits/time_window?last=30&unit=day"
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.load(response)
            return {
                "http_status": response.status,
                "response_type": type(data).__name__,
                "keys": sorted(data.keys()) if isinstance(data, dict) else None,
                "length": len(data) if isinstance(data, list) else None,
                "total_visits": data.get("total_visits") if isinstance(data, dict) else None,
                "date_from": data.get("date_from") if isinstance(data, dict) else None,
                "date_to": data.get("date_to") if isinstance(data, dict) else None,
                "daily_count": len(data.get("results", [])) if isinstance(data, dict) and isinstance(data.get("results"), list) else None,
                "daily_sample": data.get("results", [])[:3] if isinstance(data, dict) and isinstance(data.get("results"), list) else None,
            }
    except urllib.error.HTTPError as exc:
        return {"http_status": exc.code, "error": "API request failed; body suppressed"}
    except urllib.error.URLError:
        return {"error": "Network failure"}


if __name__ == "__main__":
    print(json.dumps(probe(), ensure_ascii=False))
