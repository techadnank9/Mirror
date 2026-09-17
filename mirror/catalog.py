"""Discover and pin the Glasser endpoints behind each signal. Search and inspect are free."""
from __future__ import annotations

import json
from decimal import Decimal

from . import glasser
from .config import load_endpoints, save_endpoints


def discover(limit: int = 8) -> dict:
    cfg = load_endpoints()
    glasser.CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    found: dict[str, list] = {}
    for signal, spec in cfg.items():
        try:
            res = glasser.search(spec["search"], limit=limit)
        except glasser.GlasserError as exc:
            print(f"{signal:8s} search failed: {exc}")
            continue
        (glasser.CATALOG_DIR / f"{signal}.json").write_text(json.dumps(res, indent=1))
        rows = [glasser.row_identity(r) for r in glasser.search_rows(res)]
        found[signal] = rows
        print(f"{signal:8s} {spec['search']!r}")
        for prov, ep, price in rows:
            print(f"         {prov:22s} {ep:40s} ${price}")
    (glasser.CATALOG_DIR / "candidates.json").write_text(json.dumps(found, indent=1))
    return found


def resolve(picks: dict[str, str] | None = None, auto: bool = False) -> None:
    cfg = load_endpoints()
    picks = picks or {}
    if auto:
        cand_path = glasser.CATALOG_DIR / "candidates.json"
        if not cand_path.exists():
            raise SystemExit("run `mirror discover` first")
        cands = json.loads(cand_path.read_text())
        for signal, rows in cands.items():
            if signal in picks or cfg[signal].get("provider"):
                continue
            priced = []
            for prov, ep, price in rows:
                try:
                    priced.append((Decimal(price), prov, ep))
                except Exception:
                    continue
            if priced:
                top3 = priced[:3]  # relevance-ranked; pick the cheapest of the top three
                _, prov, ep = min(top3)
                picks[signal] = f"{prov}/{ep}"
    for signal, spec in picks.items():
        prov, _, ep = spec.partition("/")
        if signal not in cfg or not (prov and ep):
            raise SystemExit(f"bad pick {signal}={spec}; use signal=provider/endpoint")
        cfg[signal]["provider"], cfg[signal]["endpoint"] = prov, ep
        print(f"{signal:8s} -> {prov}/{ep}")
    save_endpoints(cfg)


def inspect_signal(signal: str) -> dict:
    cfg = load_endpoints()
    spec = cfg[signal]
    if not spec.get("provider"):
        raise SystemExit(f"{signal} is not resolved; run discover then resolve")
    res = glasser.inspect(spec["provider"], spec["endpoint"])
    (glasser.CATALOG_DIR / f"inspect.{signal}.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1)[:6000])
    print(f"\nprice: ${glasser.price_of(res)}")
    return res


def estimate(n_companies: int) -> Decimal:
    cfg = load_endpoints()
    total = Decimal("0")
    for signal, spec in cfg.items():
        if not spec.get("provider"):
            continue
        p = glasser.CATALOG_DIR / f"inspect.{signal}.json"
        price = glasser.price_of(json.loads(p.read_text())) if p.exists() else glasser.price_of(glasser.inspect(spec["provider"], spec["endpoint"]))
        mult = n_companies if spec.get("per_company", True) else 1
        print(f"{signal:8s} ${price} x {mult}")
        total += price * mult
    print(f"estimated total: ${total}")
    return total
