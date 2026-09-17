"""Assemble web/data.json from normalized signals."""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from .argue import argue
from .weather import forecast_line, score_pool

SIGNALS_DIR = Path("data/signals")
BUILD_PATH = Path("web/data.json")


def load_signals() -> list[dict]:
    if not SIGNALS_DIR.exists():
        return []
    return [json.loads(p.read_text()) for p in sorted(SIGNALS_DIR.glob("*.json"))]


def at_a_glance(sig: dict, asof: date) -> dict:
    from datetime import timedelta

    from .dates import parse_date

    traffic = [t for t in sig.get("traffic", []) if t.get("month") != "latest"]
    cutoff = asof - timedelta(days=90)
    funding = sig.get("funding", [])
    total = sum((f.get("amount_usd") or 0) for f in funding)
    return {
        "headcount": sig.get("headcount"),
        "founded": sig.get("founded"),
        "monthly_visits": traffic[-1]["visits"] if traffic else None,
        "open_roles_90d": len([j for j in sig.get("jobs", []) if parse_date(j.get("date")) and cutoff < parse_date(j["date"]) <= asof]),  # type: ignore[operator]
        "total_raised": total or None,
        "last_round": f"{funding[-1]['round']} {funding[-1]['date'][:7]}" if funding else None,
        "domain_rating": sig.get("seo", {}).get("domain_rating"),
    }


def build(signals: list[dict], asof: date, synthetic: bool = False, use_llm: bool = True) -> dict:
    scored = score_pool(signals, asof)
    companies = []
    total_charge = Decimal("0")
    for sig, sc in zip(signals, scored):
        for s in sig.get("sources", []):
            try:
                total_charge += Decimal(str(s.get("charge") or "0"))
            except Exception:
                pass
        company = {
            "id": sig["domain"],
            "name": sig.get("name") or sig["domain"],
            "domain": sig["domain"],
            "sector": sig.get("sector") or "Other",
            "city": sig.get("city"),
            "lat": sig.get("lat"),
            "lng": sig.get("lng"),
            "description": sig.get("description"),
            "glance": at_a_glance(sig, asof),
            "snapshots": sc["snapshots"],
            "current": sc["current"],
            "sources": sig.get("sources", []),
            "signals": {k: sig.get(k, []) for k in ("traffic", "jobs", "funding", "people", "tech", "news")} | {"seo": sig.get("seo", {})},
        }
        company["forecast"] = forecast_line(company["current"], company["name"])
        company["argument"] = argue(company, use_llm=use_llm)
        companies.append(company)
    companies.sort(key=lambda c: c["current"]["momentum"])
    return {
        "meta": {
            "generated": date.today().isoformat(),
            "asof": asof.isoformat(),
            "synthetic": synthetic,
            "companies": len(companies),
            "total_charge_usd": str(total_charge),
            "runs": sum(len(c["sources"]) for c in companies),
            "months": [s["month"] for s in companies[0]["snapshots"]] if companies else [],
        },
        "companies": companies,
    }


def write_build(data: dict) -> Path:
    BUILD_PATH.parent.mkdir(parents=True, exist_ok=True)
    BUILD_PATH.write_text(json.dumps(data, indent=1, default=str))
    return BUILD_PATH
