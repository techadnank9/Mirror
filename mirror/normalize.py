"""Turn raw provider payloads (any shape) into one common signal schema.

Providers disagree on field names, so extraction is heuristic: walk the payload,
look for lists of records carrying the keys a signal needs, and read dates with
the tolerant parser. Anything the heuristics miss stays in data/raw for a
human to map by hand in config/endpoints.json `paths`.
"""
from __future__ import annotations

import math
import re
from typing import Any, Iterable

from .dates import parse_date

NEWS_KINDS = {
    "layoff": ("layoff", "lays off", "lay off", "laid off", "layoffs", "cuts jobs", "job cuts", "restructur", "downsiz"),
    "funding": ("raises", "raised", "funding", "series a", "series b", "series c", "seed round", "investment", "valuation"),
    "exec": ("appoints", "names new", "hires", "joins as", "chief", "cto", "cfo", "ceo", "vp of", "head of", "steps down", "resigns", "departs"),
    "acquisition": ("acquire", "acquisition", "merger", "merges", "buys"),
    "launch": ("launch", "unveils", "introduces", "releases", "announces new", "rolls out", "partnership", "partners with"),
    "legal": ("lawsuit", "sued", "settlement", "regulator", "fine", "investigation", "breach"),
}


def classify_news(title: str) -> str:
    t = (title or "").lower()
    for kind, needles in NEWS_KINDS.items():
        if any(n in t for n in needles):
            return kind
    return "other"


def walk(obj: Any, depth: int = 0) -> Iterable[Any]:
    if depth > 8:
        return
    yield obj
    if isinstance(obj, dict):
        for v in obj.values():
            yield from walk(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj[:500]:
            yield from walk(v, depth + 1)


def _lists_of_dicts(obj: Any) -> Iterable[list]:
    for node in walk(obj):
        if isinstance(node, list) and node and all(isinstance(x, dict) for x in node[:5]):
            yield node


def _first(d: dict, *cands: str) -> Any:
    low = {k.lower(): k for k in d}
    for c in cands:
        if c in low:
            return d[low[c]]
    for c in cands:
        for lk, k in low.items():
            if c in lk:
                return d[k]
    return None


def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v)):
        return float(v)
    if isinstance(v, str):
        s = v.replace(",", "").replace("$", "").strip().lower()
        mult = 1.0
        for suf, m in (("k", 1e3), ("m", 1e6), ("b", 1e9)):
            if s.endswith(suf):
                s, mult = s[:-1], m
        try:
            return float(s) * mult
        except ValueError:
            return None
    return None


def _get_path(obj: Any, path: str | None) -> Any:
    if not path:
        return obj
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit():
            cur = cur[int(part)] if int(part) < len(cur) else None
        else:
            return None
    return cur


# ---- per-signal extractors ------------------------------------------------

def extract_traffic(raw: Any, path: str | None = None) -> list[dict]:
    """[{month: 'YYYY-MM', visits: float}] sorted by month."""
    raw = _get_path(raw, path)
    out: dict[str, float] = {}
    for lst in _lists_of_dicts(raw):
        for rec in lst:
            d = parse_date(_first(rec, "month", "date", "period", "timestamp", "time"))
            v = _num(_first(rec, "visits", "visitors", "traffic", "sessions", "value", "count"))
            if d and v is not None:
                out[f"{d.year:04d}-{d.month:02d}"] = v
        if out:
            break
    if not out:
        for node in walk(raw):
            if isinstance(node, dict):
                monthish = {k: _num(v) for k, v in node.items() if parse_date(k) and _num(v) is not None}
                if len(monthish) >= 3:
                    for k, v in monthish.items():
                        d = parse_date(k)
                        out[f"{d.year:04d}-{d.month:02d}"] = v  # type: ignore[union-attr]
                    break
    if not out and isinstance(raw, (dict, list)):
        for node in walk(raw):
            if isinstance(node, dict):
                v = _num(_first(node, "monthly_visits", "visits", "monthlyvisits", "estimated_monthly_visits"))
                if v is not None:
                    out["latest"] = v
                    break
    return [{"month": k, "visits": v} for k, v in sorted(out.items())]


def extract_jobs(raw: Any, path: str | None = None) -> list[dict]:
    """[{title, date, function}] job postings."""
    raw = _get_path(raw, path)
    jobs: list[dict] = []
    for lst in _lists_of_dicts(raw):
        for rec in lst:
            title = _first(rec, "title", "job_title", "position", "name")
            if not isinstance(title, str):
                continue
            d = parse_date(_first(rec, "posted", "date_posted", "published", "created", "date", "first_seen"))
            jobs.append({"title": title, "date": d.isoformat() if d else None, "function": job_function(title)})
        if jobs:
            break
    return jobs


def job_function(title: str) -> str:
    t = (title or "").lower()
    table = (
        ("sales", ("sales", "account executive", "sdr", "bdr", "revenue", "business development")),
        ("marketing", ("marketing", "growth", "content", "brand", "demand gen")),
        ("engineering", ("engineer", "developer", "software", "devops", "sre", "data scientist", "ml ", "backend", "frontend")),
        ("product", ("product manager", "product designer", "designer", "ux", "product")),
        ("customer", ("customer success", "support", "account manager", "onboarding")),
        ("finance", ("finance", "controller", "accountant", "cfo", "fp&a")),
        ("people", ("recruit", "talent", "people ops", "hr ")),
        ("ops", ("operations", "ops", "supply", "logistics")),
    )
    for fn, needles in table:
        if any(n in t for n in needles):
            return fn
    return "other"


def extract_funding(raw: Any, path: str | None = None) -> list[dict]:
    """[{date, round, amount_usd, investors}] sorted by date."""
    raw = _get_path(raw, path)
    rounds: list[dict] = []
    for lst in _lists_of_dicts(raw):
        for rec in lst:
            rnd = _first(rec, "round", "round_type", "type", "series", "stage", "name")
            amt = _num(_first(rec, "amount_usd", "amount", "raised", "money_raised", "value"))
            d = parse_date(_first(rec, "announced", "date", "announced_on", "funded_at", "closed"))
            if d and (amt is not None or rnd):
                inv = _first(rec, "investors", "lead_investors", "investor_names")
                if isinstance(inv, list):
                    inv = [i.get("name", i) if isinstance(i, dict) else i for i in inv]
                rounds.append({"date": d.isoformat(), "round": str(rnd or "Round"), "amount_usd": amt, "investors": inv or []})
        if rounds:
            break
    if not rounds:
        for node in walk(raw):
            if isinstance(node, dict):
                d = parse_date(_first(node, "last_funding_date", "latest_funding_date", "last_round_date", "funding_date"))
                if d:
                    amt = _num(_first(node, "last_funding_amount", "total_funding", "funding_total", "total_raised"))
                    rnd = _first(node, "last_funding_type", "last_round", "latest_funding_stage", "funding_stage")
                    rounds.append({"date": d.isoformat(), "round": str(rnd or "Round"), "amount_usd": amt, "investors": []})
                    break
    rounds.sort(key=lambda r: r["date"])
    return rounds


def extract_people(raw: Any, path: str | None = None) -> list[dict]:
    """[{name, title, start_date, end_date}] executives and notable hires."""
    raw = _get_path(raw, path)
    people: list[dict] = []
    for lst in _lists_of_dicts(raw):
        for rec in lst:
            name = _first(rec, "full_name", "name", "person_name")
            title = _first(rec, "title", "job_title", "role", "position", "headline")
            if not (isinstance(name, str) and isinstance(title, str)):
                continue
            start = parse_date(_first(rec, "start_date", "started", "joined", "since", "job_start_date"))
            end = parse_date(_first(rec, "end_date", "ended", "left", "job_end_date"))
            people.append({
                "name": name,
                "title": title,
                "function": job_function(title),
                "start_date": start.isoformat() if start else None,
                "end_date": end.isoformat() if end else None,
            })
        if people:
            break
    return people


def extract_tech(raw: Any, path: str | None = None) -> list[dict]:
    """[{name, first_seen}] technologies in the stack."""
    raw = _get_path(raw, path)
    tech: list[dict] = []
    for node in walk(raw):
        if isinstance(node, dict):
            val = _first(node, "technologies", "tech_stack", "techstack", "tech", "technology")
            if isinstance(val, list) and val:
                for t in val:
                    if isinstance(t, str):
                        tech.append({"name": t, "first_seen": None})
                    elif isinstance(t, dict):
                        n = _first(t, "name", "technology", "tech")
                        d = parse_date(_first(t, "first_seen", "first_detected", "since", "added"))
                        if isinstance(n, str):
                            tech.append({"name": n, "first_seen": d.isoformat() if d else None})
                break
    return tech


def extract_seo(raw: Any, path: str | None = None) -> dict:
    raw = _get_path(raw, path)
    out: dict[str, float | None] = {"domain_rating": None, "keywords": None, "backlinks": None}
    for node in walk(raw):
        if isinstance(node, dict):
            if out["domain_rating"] is None:
                out["domain_rating"] = _num(_first(node, "domain_rating", "domainrating", "dr", "authority", "domain_authority"))
            if out["keywords"] is None:
                kw = _first(node, "organic_keywords", "keywords_count", "keywords", "ranking_keywords")
                out["keywords"] = float(len(kw)) if isinstance(kw, list) else _num(kw)
            if out["backlinks"] is None:
                out["backlinks"] = _num(_first(node, "backlinks", "backlinks_count", "referring_domains"))
    return out


def extract_news(raw: Any, path: str | None = None) -> list[dict]:
    raw = _get_path(raw, path)
    items: list[dict] = []
    for lst in _lists_of_dicts(raw):
        for rec in lst:
            title = _first(rec, "title", "headline")
            if not isinstance(title, str):
                continue
            d = parse_date(_first(rec, "published", "date", "published_at", "datetime", "time"))
            url = _first(rec, "url", "link")
            items.append({"date": d.isoformat() if d else None, "title": title, "kind": classify_news(title), "url": url if isinstance(url, str) else None})
        if items:
            break
    items.sort(key=lambda r: r["date"] or "")
    return items


def extract_company(raw: Any, path: str | None = None) -> dict:
    raw = _get_path(raw, path)
    out: dict[str, Any] = {}
    for node in walk(raw):
        if isinstance(node, dict):
            for field, cands in (
                ("name", ("name", "company_name", "display_name")),
                ("domain", ("domain", "website", "url")),
                ("sector", ("industry", "sector", "category", "vertical")),
                ("headcount", ("employee_count", "employees", "headcount", "size")),
                ("founded", ("founded", "founded_year", "year_founded")),
                ("city", ("city", "location", "hq", "headquarters")),
                ("lat", ("lat", "latitude")),
                ("lng", ("lng", "lon", "longitude")),
                ("description", ("description", "summary", "tagline")),
            ):
                if field not in out:
                    v = _first(node, *cands)
                    if isinstance(v, dict):
                        v = _first(v, "name", "city", "value")
                    if isinstance(v, (str, int, float)) and str(v).strip():
                        out[field] = v
            if len(out) >= 5:
                break
    if isinstance(out.get("domain"), str):
        out["domain"] = re.sub(r"^https?://(www\.)?", "", out["domain"]).split("/")[0]
    return out
