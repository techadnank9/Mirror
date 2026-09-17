"""Pull the candidate pool and every signal per company, through the cache."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import glasser, normalize
from .build import SIGNALS_DIR
from .config import load_endpoints, load_icp, render, unresolved

POOL_PATH = Path("data/pool.json")
EXTRACTORS = {
    "traffic": normalize.extract_traffic,
    "jobs": normalize.extract_jobs,
    "funding": normalize.extract_funding,
    "people": normalize.extract_people,
    "tech": normalize.extract_tech,
    "seo": normalize.extract_seo,
    "news": normalize.extract_news,
}


def pool() -> list[dict]:
    cfg = load_endpoints()
    icp = load_icp()
    spec = cfg["pool"]
    if not spec.get("provider"):
        raise SystemExit("pool endpoint not resolved")
    inp = render(spec["input"], {"icp": icp})
    rec = glasser.run(spec["provider"], spec["endpoint"], inp)
    out = glasser.output_of(rec)
    companies = []
    for lst in normalize._lists_of_dicts(out):
        for row in lst:
            c = normalize.extract_company(row)
            if c.get("domain") and c["domain"] not in icp.get("exclude_domains", []):
                c["_pool_source"] = {"provider": spec["provider"], "endpoint": spec["endpoint"], "run_url": glasser.run_url_of(rec), "charge": str(glasser.charge_of(rec))}
                companies.append(c)
        if companies:
            break
    POOL_PATH.parent.mkdir(parents=True, exist_ok=True)
    POOL_PATH.write_text(json.dumps(companies, indent=1))
    print(f"pool: {len(companies)} companies, charge ${glasser.charge_of(rec)}, run {glasser.run_url_of(rec)}")
    return companies


def add_to_pool(domain: str, name: str | None = None) -> dict:
    companies = json.loads(POOL_PATH.read_text()) if POOL_PATH.exists() else []
    if not any(c.get("domain") == domain for c in companies):
        companies.append({"domain": domain, "name": name or domain.split(".")[0].title()})
        POOL_PATH.write_text(json.dumps(companies, indent=1))
    return next(c for c in companies if c.get("domain") == domain)


def collect_one(company: dict, signals: list[str] | None = None) -> dict:
    cfg = load_endpoints()
    sig: dict = {
        "name": company.get("name") or company["domain"], "domain": company["domain"],
        "sector": company.get("sector"), "city": company.get("city"), "lat": company.get("lat"), "lng": company.get("lng"),
        "headcount": company.get("headcount"), "founded": company.get("founded"), "description": company.get("description"),
        "traffic": [], "jobs": [], "funding": [], "people": [], "tech": [], "news": [], "seo": {}, "sources": [],
    }
    ctx = {"domain": company["domain"], "name": sig["name"], "icp": load_icp()}
    for signal, spec in cfg.items():
        if not spec.get("per_company", True) or not spec.get("provider"):
            continue
        if signals and signal not in signals:
            continue
        inp = render(spec["input"], ctx)
        try:
            rec = glasser.run(spec["provider"], spec["endpoint"], inp)
        except glasser.GlasserError as exc:
            sig["sources"].append({"signal": signal, "provider": spec["provider"], "endpoint": spec["endpoint"], "status": "ERROR", "error": str(exc)[:300], "charge": "0", "run_url": None})
            continue
        out = glasser.output_of(rec)
        sig["sources"].append({"signal": signal, "provider": spec["provider"], "endpoint": spec["endpoint"], "status": glasser.status_of(rec), "charge": str(glasser.charge_of(rec)), "run_url": glasser.run_url_of(rec)})
        if signal == "company":
            meta = normalize.extract_company(out, spec.get("path"))
            for k in ("name", "sector", "headcount", "founded", "city", "lat", "lng", "description"):
                if meta.get(k) and not sig.get(k):
                    sig[k] = meta[k]
            fund = normalize.extract_funding(out)
            if fund and not sig["funding"]:
                sig["funding"] = fund
            tech = normalize.extract_tech(out)
            if tech and not sig["tech"]:
                sig["tech"] = tech
        elif signal in EXTRACTORS:
            sig[signal] = EXTRACTORS[signal](out, spec.get("path"))
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    (SIGNALS_DIR / f"{company['domain']}.json").write_text(json.dumps(sig, indent=1))
    return sig


def collect_all(limit: int | None = None, workers: int = 4, signals: list[str] | None = None) -> list[dict]:
    missing = [s for s in unresolved(load_endpoints()) if s != "pool"]
    if missing:
        print(f"note: unresolved signals will be skipped: {', '.join(missing)}")
    companies = json.loads(POOL_PATH.read_text())
    if limit:
        companies = companies[:limit]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(lambda c: collect_one(c, signals), companies))
    print(f"collected {len(results)} companies")
    return results
