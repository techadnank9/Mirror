"""Synthetic pool so the map runs before a single credit is spent.

Deterministic, clearly labelled, and shaped to show every condition.
"""
from __future__ import annotations

import json
import random
from datetime import date, timedelta

from .build import SIGNALS_DIR
from .dates import add_months, month_key, month_range

SECTORS = {
    "Fintech": ["Ledgerly", "Payhaven", "Quillpay", "Vaultic", "Numera", "Coinbridge", "Fundwise"],
    "Devtools": ["Buildpipe", "Stackmint", "Deployr", "Codeharbor", "Loomcode", "Gitgale", "Shipmate"],
    "Health": ["Clinicore", "Medlane", "Vitalgraph", "Careloop", "Pulsewell", "Nurseline"],
    "Climate": ["Gridleaf", "Solmetric", "Carbonclear", "Windward", "Aquifer"],
    "Retail": ["Shelfio", "Cartline", "Merchly", "Storefold", "Basketry", "Trolleyo"],
    "AI infra": ["Tensorbay", "Promptforge", "Vectorhaus", "Inferly", "Modelmill", "Datarift", "Embedly", "Agentic Labs"],
}
ARCHETYPES = ["sunny"] * 10 + ["cloudy"] * 10 + ["storm"] * 8 + ["front"] * 6 + ["fog"] * 5
CITIES = [("San Francisco", 37.77, -122.42), ("New York", 40.71, -74.01), ("Austin", 30.27, -97.74),
          ("London", 51.51, -0.13), ("Berlin", 52.52, 13.41), ("Toronto", 43.65, -79.38), ("Singapore", 1.35, 103.82)]
EXEC_TITLES = {
    "sales": ["VP Sales", "Chief Revenue Officer", "Head of Sales"],
    "marketing": ["VP Marketing", "Head of Growth", "CMO"],
    "engineering": ["VP Engineering", "CTO", "Head of Platform"],
    "product": ["Chief Product Officer", "VP Product"],
    "finance": ["CFO", "VP Finance"],
}
NEWS = {
    "layoff": "{n} lays off {pct}% of staff in restructuring",
    "funding": "{n} raises ${amt}M {rnd} led by {inv}",
    "exec": "{n} appoints {title}",
    "launch": "{n} launches {prod} for enterprise teams",
    "acquisition": "{n} acquires {other} to expand platform",
}
INVESTORS = ["Northwind Capital", "Sequoia", "a16z", "Index Ventures", "Lightspeed", "Accel", "Founders Fund"]
TECH = ["HubSpot", "Salesforce", "Segment", "Snowflake", "dbt", "Datadog", "Stripe", "Intercom", "Gong", "Outreach", "Amplitude", "Vercel"]


def _traffic(rng: random.Random, months: list[str], arche: str, base: float) -> list[dict]:
    out = []
    v = base
    for i, m in enumerate(months):
        drift = {"sunny": 0.06, "cloudy": 0.005, "storm": -0.07, "front": 0.01, "fog": 0.0}[arche]
        if arche == "storm" and i < 5:
            drift = 0.03  # was sunny before the storm
        v = max(200.0, v * (1 + drift + rng.uniform(-0.04, 0.04)))
        out.append({"month": m, "visits": round(v)})
    return out


def _jobs(rng: random.Random, asof: date, arche: str) -> list[dict]:
    """Postings spread over 14 months; the monthly rate follows the archetype's story."""
    funcs = ["sales", "marketing", "engineering", "product", "customer", "ops"]
    jobs = []
    for back in range(20, -1, -1):  # months ago, oldest first
        if arche == "sunny":
            rate = 1.5 + max(0, 14 - back) * 0.4
        elif arche == "cloudy":
            rate = 1.5
        elif arche == "storm":
            rate = 3.5 if back > 4 else max(0.0, 3.5 - (5 - back) * 1.2)
        elif arche == "front":
            rate = 1.2 if back > 1 else 4.0
        else:
            rate = 0.0
        n = max(0, round(rng.gauss(rate, 0.7))) if rate > 0 else 0
        for _ in range(n):
            f = rng.choice(funcs)
            d = asof - timedelta(days=back * 30 + rng.randint(0, 29))
            jobs.append({"title": f"{rng.choice(['Senior', 'Lead', 'Staff', ''])} {f.title()} {'Engineer' if f == 'engineering' else 'Manager'}".strip(), "date": d.isoformat(), "function": f})
    return jobs


def make_company(rng: random.Random, name: str, sector: str, arche: str, asof: date) -> dict:
    months = month_range(asof, 20)
    domain = name.lower().replace(" ", "") + ".example"
    city, lat, lng = rng.choice(CITIES)
    base = {"sunny": rng.uniform(20000, 120000), "cloudy": rng.uniform(5000, 60000), "storm": rng.uniform(15000, 90000), "front": rng.uniform(8000, 50000), "fog": rng.uniform(300, 900)}[arche]
    sig: dict = {
        "name": name, "domain": domain, "sector": sector, "city": city, "lat": lat + rng.uniform(-0.3, 0.3), "lng": lng + rng.uniform(-0.3, 0.3),
        "headcount": {"sunny": rng.randint(80, 400), "cloudy": rng.randint(30, 200), "storm": rng.randint(60, 300), "front": rng.randint(40, 150), "fog": rng.randint(3, 15)}[arche],
        "founded": rng.randint(2014, 2023),
        "description": f"{name} builds {sector.lower()} software for mid-market teams.",
        "traffic": [] if arche == "fog" else _traffic(rng, months, arche, base),
        "jobs": _jobs(rng, asof, arche),
        "funding": [], "people": [], "tech": [], "news": [],
        "seo": {"domain_rating": None, "keywords": None, "backlinks": None},
        "sources": [],
    }
    # funding
    if arche in ("sunny", "front"):
        d = asof - timedelta(days=rng.randint(30, 330))
        amt = rng.choice([8, 12, 20, 35, 60])
        sig["funding"] = [{"date": (d - timedelta(days=rng.randint(400, 700))).isoformat(), "round": "Seed", "amount_usd": 3e6, "investors": [rng.choice(INVESTORS)]},
                          {"date": d.isoformat(), "round": "Series A" if amt < 30 else "Series B", "amount_usd": amt * 1e6, "investors": [rng.choice(INVESTORS)]}]
        sig["news"].append({"date": d.isoformat(), "title": NEWS["funding"].format(n=name, amt=amt, rnd=sig["funding"][-1]["round"], inv=sig["funding"][-1]["investors"][0]), "kind": "funding", "url": None})
    elif arche == "cloudy":
        d = asof - timedelta(days=rng.randint(300, 500))
        sig["funding"] = [{"date": d.isoformat(), "round": "Seed", "amount_usd": rng.choice([2e6, 4e6, 6e6]), "investors": [rng.choice(INVESTORS)]}]
    elif arche == "storm":
        d = asof - timedelta(days=rng.randint(700, 1100))
        sig["funding"] = [{"date": d.isoformat(), "round": "Series A", "amount_usd": rng.choice([10e6, 15e6, 25e6]), "investors": [rng.choice(INVESTORS)]}]
        ld = asof - timedelta(days=rng.randint(10, 80))
        sig["news"].append({"date": ld.isoformat(), "title": NEWS["layoff"].format(n=name, pct=rng.choice([12, 18, 25, 30])), "kind": "layoff", "url": None})
        sig["people"].append({"name": rng.choice(["Dana Whitfield", "Marcus Lee", "Priya Raman"]), "title": rng.choice(EXEC_TITLES["sales"]), "function": "sales", "start_date": (asof - timedelta(days=900)).isoformat(), "end_date": (ld - timedelta(days=rng.randint(5, 40))).isoformat()})
    # execs and tech
    if arche == "front":
        f = rng.choice(["sales", "marketing"])
        title = rng.choice(EXEC_TITLES[f])
        d = asof - timedelta(days=rng.randint(7, 60))
        sig["people"].append({"name": rng.choice(["Elena Voss", "Tomas Brandt", "Aisha Okafor", "Jun Park"]), "title": title, "function": f, "start_date": d.isoformat(), "end_date": None})
        sig["news"].append({"date": d.isoformat(), "title": NEWS["exec"].format(n=name, title=title), "kind": "exec", "url": None})
        sig["tech"].append({"name": rng.choice(["HubSpot", "Salesforce", "Gong", "Outreach"]), "first_seen": (d + timedelta(days=rng.randint(1, 20))).isoformat()})
    if arche == "sunny":
        f = rng.choice(["engineering", "product", "sales"])
        sig["people"].append({"name": rng.choice(["Sam Idris", "Leah Cohen", "Ravi Menon"]), "title": rng.choice(EXEC_TITLES[f]), "function": f, "start_date": (asof - timedelta(days=rng.randint(100, 400))).isoformat(), "end_date": None})
        sig["news"].append({"date": (asof - timedelta(days=rng.randint(20, 120))).isoformat(), "title": NEWS["launch"].format(n=name, prod=rng.choice(["Workflows", "Insights", "Copilot", "Connect"])), "kind": "launch", "url": None})
    sig["people"].append({"name": rng.choice(["Ana Ruiz", "Ben Carter", "Yuki Tanaka", "Omar Haddad"]), "title": "CEO", "function": "other", "start_date": f"{sig['founded']}-01-01", "end_date": None})
    sig["tech"] += [{"name": t, "first_seen": None} for t in rng.sample(TECH, rng.randint(3, 6))]
    # seo
    if arche != "fog":
        sig["seo"] = {"domain_rating": round({"sunny": rng.uniform(45, 75), "cloudy": rng.uniform(20, 50), "storm": rng.uniform(30, 60), "front": rng.uniform(25, 55)}[arche]), "keywords": rng.randint(300, 20000), "backlinks": rng.randint(500, 50000)}
    else:
        sig["seo"] = {"domain_rating": rng.uniform(2, 9), "keywords": rng.randint(3, 40), "backlinks": rng.randint(5, 60)}
    for s in ("company", "traffic", "jobs", "funding", "people", "news", "seo"):
        sig["sources"].append({"signal": s, "provider": "synthetic", "endpoint": "demo", "run_url": None, "charge": "0", "status": "SYNTHETIC"})
    return sig


def generate(asof: date, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    arches = list(ARCHETYPES)
    rng.shuffle(arches)
    out = []
    i = 0
    for sector, names in SECTORS.items():
        for name in names:
            out.append(make_company(rng, name, sector, arches[i % len(arches)], asof))
            i += 1
    return out


def write_demo(asof: date, seed: int = 7) -> int:
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    for p in SIGNALS_DIR.glob("*.json"):
        p.unlink()
    sigs = generate(asof, seed)
    for s in sigs:
        (SIGNALS_DIR / f"{s['domain']}.json").write_text(json.dumps(s, indent=1))
    return len(sigs)
