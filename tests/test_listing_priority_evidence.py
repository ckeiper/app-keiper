from decimal import Decimal
from listing_priority_evidence import enrich_priorities


def test_unverified_signals_do_not_create_findings():
    queue = {"available": True, "items": [{"item_id": "MLB1", "loss": Decimal("20")}]}
    result = enrich_priorities(queue, {"MLB1": {"stock": 0, "margin_current_pct": 5}})
    assert result["items"][0]["additional_findings"] == []
    assert result["items"][0]["data_limitations"] == ["estoque", "margem"]


def test_verified_stockout_and_margin_decline():
    queue = {"available": True, "items": [{"item_id": "MLB1"}]}
    signals = {"MLB1": {"stock_verified": True, "stock": 0,
                        "margin_verified": True, "margin_current_pct": 10,
                        "margin_previous_pct": 20}}
    findings = enrich_priorities(queue, signals)["items"][0]["additional_findings"]
    assert [finding["code"] for finding in findings] == ["stockout", "margin_decline"]


def test_order_preserved_and_no_negative_stock():
    queue = {"available": True, "items": [{"item_id": "MLB2"}, {"item_id": "MLB1"}]}
    result = enrich_priorities(queue, {"MLB1": {"stock_verified": True, "stock": -1}})
    assert [item["item_id"] for item in result["items"]] == ["MLB2", "MLB1"]
    assert result["items"][1]["additional_findings"] == []


def test_unavailable_queue_is_unchanged():
    queue = {"available": False, "reason": "Sem cobertura", "items": []}
    assert enrich_priorities(queue) == queue


def test_queue_optional_enrichment_preserves_legacy_call(monkeypatch):
    import listing_priority_queue as queue_module
    monkeypatch.setattr(queue_module, "investigate", lambda ranking: {
        "available": True, "rows": [
            {"item_id": "MLB1", "loss": Decimal("30"),
             "percent": Decimal("-10"), "share": Decimal("1")}],
        "lost": Decimal("30")})
    legacy = queue_module.prioritize({}, limit=1)
    assert "additional_findings" not in legacy["items"][0]
    enriched = queue_module.prioritize({}, limit=1, verified_signals_by_item={
        "MLB1": {"stock_verified": True, "stock": 0}})
    assert enriched["items"][0]["additional_findings"][0]["code"] == "stockout"
