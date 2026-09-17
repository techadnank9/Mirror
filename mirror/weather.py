"""Score normalized signals into weather, month by month.

Temperature = traffic momentum. Pressure = hiring momentum. Precipitation =
funding recency. Wind = leadership and stack change. Visibility = search and
social footprint. All in [-1, 1] or [0, 1]; the condition is a rule over them.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

from .dates import add_months, month_range, months_between, parse_date

MONTHS = 12
GO_TO_MARKET = {"sales", "marketing", "customer"}
BUILDING = {"engineering", "product"}


def clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def pct_change(new: float, old: float) -> float | None:
    if old <= 0:
        return None
    return (new - old) / old


def _month_end(mk: str) -> date:
    y, m = int(mk[:4]), int(mk[5:7])
    return add_months(date(y, m, 1), 1) - timedelta(days=1)


def _in_window(d: str | None, end: date, days: int) -> bool:
    p = parse_date(d)
    return bool(p and end - timedelta(days=days) < p <= end)


def temperature(traffic: list[dict], mk: str) -> tuple[float | None, str]:
    series = {t["month"]: t["visits"] for t in traffic if t.get("month") != "latest"}
    if len(series) < 2:
        return None, "no traffic history"
    recent = [series[m] for m in month_range(_month_end(mk), 3) if m in series]
    prior = [series[m] for m in month_range(add_months(_month_end(mk), -3), 3) if m in series]
    if not recent or not prior:
        return None, "traffic history too short"
    change = pct_change(sum(recent) / len(recent), sum(prior) / len(prior))
    if change is None:
        return None, "traffic baseline zero"
    return clamp(change / 0.5), f"traffic {change:+.0%} quarter over quarter"


def pressure(jobs: list[dict], news: list[dict], mk: str) -> tuple[float | None, str]:
    end = _month_end(mk)
    known = [j for j in jobs if parse_date(j.get("date")) and parse_date(j["date"]) <= end]  # type: ignore[arg-type]
    recent = sum(1 for j in known if _in_window(j.get("date"), end, 90))
    prior = sum(1 for j in known if _in_window(j.get("date"), end - timedelta(days=90), 90))
    layoffs = [n for n in news if n.get("kind") == "layoff" and _in_window(n.get("date"), end, 120)]
    if layoffs:
        return -0.8, f"layoffs reported: {layoffs[-1]['title'][:60]}"
    if recent == 0 and prior == 0:
        return (None, "no job postings on record") if not known else (-0.4, "hiring has gone quiet")
    if prior == 0:
        return clamp(recent / 5.0, 0, 1), f"{recent} roles opened in 90 days from a standing start"
    change = (recent - prior) / prior
    return clamp(change / 0.75), f"open roles {change:+.0%} vs prior quarter ({recent} recent)"


def precipitation(funding: list[dict], mk: str) -> tuple[float, str]:
    end = _month_end(mk)
    past = [f for f in funding if parse_date(f.get("date")) and parse_date(f["date"]) <= end]
    if not past:
        return 0.2, "no funding on record"
    last = past[-1]
    gap = months_between(parse_date(last["date"]), end)  # type: ignore[arg-type]
    if gap <= 6:
        return 1.0, f"{last['round']} {gap} months ago"
    if gap <= 18:
        return clamp(1.0 - (gap - 6) / 12.0, 0, 1), f"last round {gap} months ago"
    return 0.0, f"drought: {gap} months since {last['round']}"


def wind(people: list[dict], tech: list[dict], news: list[dict], mk: str) -> tuple[float, str, list[str]]:
    end = _month_end(mk)
    events: list[str] = []
    funcs: list[str] = []
    for p in people:
        if _in_window(p.get("start_date"), end, 90):
            events.append(f"{p['title']} joined ({p['name']})")
            funcs.append(p.get("function", "other"))
        if _in_window(p.get("end_date"), end, 90):
            events.append(f"{p['title']} left ({p['name']})")
            funcs.append("departure")
    for t in tech:
        if _in_window(t.get("first_seen"), end, 90):
            events.append(f"added {t['name']} to the stack")
    for n in news:
        if n.get("kind") in ("exec", "acquisition", "launch") and _in_window(n.get("date"), end, 90):
            events.append(f"news: {n['title'][:70]}")
    strength = clamp(len(events) / 3.0, 0, 1)
    if "departure" in funcs and funcs.count("departure") >= len(funcs) / 2:
        direction = "leadership leaving"
    elif any(f in GO_TO_MARKET for f in funcs):
        direction = "toward market"
    elif any(f in BUILDING for f in funcs):
        direction = "toward building"
    elif events:
        direction = "shifting"
    else:
        direction = "calm"
    return strength, direction, events


def visibility_raw(seo: dict) -> float | None:
    dr = seo.get("domain_rating")
    kw = seo.get("keywords")
    if dr is None and kw is None:
        return None
    score = 0.0
    if dr is not None:
        score += clamp(float(dr) / 100.0, 0, 1) * 0.6
    if kw is not None:
        score += clamp(math.log10(max(float(kw), 1.0)) / 5.0, 0, 1) * 0.4
    return clamp(score, 0, 1)


def condition(t: float | None, p: float | None, precip: float, w: float, vis: float | None, has_footprint: bool) -> str:
    if not has_footprint and (vis is None or vis < 0.15):
        return "fog"
    tv = 0.0 if t is None else t
    pv = 0.0 if p is None else p
    if w >= 0.6 and abs(tv) < 0.35:
        return "front"
    if tv <= -0.3 and pv <= -0.2 and precip < 0.5:
        return "storm"
    if tv >= 0.2 and pv >= 0.0 and precip >= 0.5:
        return "sunny"
    if tv <= -0.5 or (tv <= -0.2 and pv <= -0.3):
        return "storm"
    return "cloudy"


def momentum(t: float | None, p: float | None, precip: float, w: float, direction: str) -> float:
    tv = 0.0 if t is None else t
    pv = 0.0 if p is None else p
    wv = w * (0.5 if direction in ("toward market", "toward building") else -0.5 if direction == "leadership leaving" else 0.0)
    return clamp(0.4 * tv + 0.3 * pv + 0.2 * (2 * precip - 1) + 0.1 * wv)


def score_company(sig: dict, asof: date, vis: float | None) -> dict:
    traffic = sig.get("traffic", [])
    jobs = sig.get("jobs", [])
    funding = sig.get("funding", [])
    people = sig.get("people", [])
    tech = sig.get("tech", [])
    news = sig.get("news", [])
    has_footprint = bool(traffic or jobs or funding or news)
    snapshots = []
    for mk in month_range(asof, MONTHS):
        t, t_why = temperature(traffic, mk)
        p, p_why = pressure(jobs, news, mk)
        pr, pr_why = precipitation(funding, mk)
        w, w_dir, w_events = wind(people, tech, news, mk)
        cond = condition(t, p, pr, w, vis, has_footprint)
        snapshots.append({
            "month": mk,
            "temperature": t, "temperature_why": t_why,
            "pressure": p, "pressure_why": p_why,
            "precipitation": pr, "precipitation_why": pr_why,
            "wind": w, "wind_direction": w_dir, "wind_events": w_events,
            "visibility": vis,
            "momentum": momentum(t, p, pr, w, w_dir),
            "condition": cond,
        })
    return {"snapshots": snapshots, "current": snapshots[-1]}


def score_pool(signals: list[dict], asof: date) -> list[dict]:
    """Score every company; visibility is ranked within the pool."""
    raws = [visibility_raw(s.get("seo", {})) for s in signals]
    known = sorted(v for v in raws if v is not None)
    out = []
    for sig, raw in zip(signals, raws):
        vis = None
        if raw is not None and known:
            rank = sum(1 for k in known if k <= raw) / len(known)
            vis = round(0.5 * raw + 0.5 * rank, 3)
        out.append(score_company(sig, asof, vis))
    return out


def forecast_line(current: dict, name: str) -> str:
    c = current["condition"]
    d = current["wind_direction"]
    if c == "sunny":
        return f"{name} stays warm through the quarter. Funded and hiring; expect them to buy tools, not cut them."
    if c == "storm":
        return f"Storm over {name} for the next 90 days. Cooling traffic and thinning hiring; a churn risk if they are a customer, a poaching window if they are not."
    if c == "front":
        return f"A front is moving through {name}, {d}. Something just changed while the rest lags. This is the moment to reach out."
    if c == "fog":
        return f"{name} is in fog. Almost no public footprint; verify they are still operating before spending time."
    return f"{name} holds steady. Flat on every signal; nothing pushes them to buy or to cut right now."
