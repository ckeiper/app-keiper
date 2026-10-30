"""Read-only Mercado Livre visits probe. Run inside the existing Render environment.

Requires ML_ACCESS_TOKEN and ML_ITEM_ID environment variables.
Never prints credentials, response bodies, or identifying customer data.
Does not write to the database or alter application state.
"""
import json
import os
import urllib.error
import urllib.request

def main():
    token = os.environ.get("ML_ACCESS_TOKEN")
    item_id = os.environ.get("ML_ITEM_ID")
    if not token or not item_id or not item_id.startswith("MLB") or not item_id[3:].isdigit():
        raise SystemExit("Missing valid ML_ACCESS_TOKEN or ML_ITEM_ID")
    url = f"https://api.mercadolibre.com/items/{item_id}/visits/time_window?last=30&unit=day"
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + token, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
            print(json.dumps({"http_status": response.status, "response_type": type(payload).__name__, "top_level_keys": list(payload) if isinstance(payload, dict) else None, "entries": len(payload) if isinstance(payload, list) else None}))
    except urllib.error.HTTPError as exc:
        print(json.dumps({"http_status": exc.code, "error": "Mercado Livre rejected the request; response suppressed"}))
        raise SystemExit(1)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(json.dumps({"error_type": type(exc).__name__}))
        raise SystemExit(1)

if __name__ == "__main__":
    main()
