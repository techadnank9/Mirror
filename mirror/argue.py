"""Prosecution and defense for each company, every claim tied to a source.

Template mode works offline from the scored signals. When ANTHROPIC_API_KEY is
set and the `anthropic` package is installed, Claude polishes the same claims
into sharper prose without inventing new facts.
"""
from __future__ import annotations

import json
import os
from typing import Any


def _claim(text: str, signal: str, sources: list[dict]) -> dict:
    src = next((s for s in sources if s.get("signal") == signal), None)
    return {"text": text, "signal": signal, "source": src}


def template_arguments(company: dict) -> tuple[list[dict], list[dict]]:
    cur = company["current"]
    sig = company["signals"]
    sources = company.get("sources", [])
    pros: list[dict] = []
    defs: list[dict] = []
    t, p, pr, w = cur["temperature"], cur["pressure"], cur["precipitation"], cur["wind"]

    if t is not None:
        (defs if t > 0.1 else pros if t < -0.1 else defs).append(
            _claim(f"Traffic: {cur['temperature_why']}.", "traffic", sources))
    else:
        pros.append(_claim("No measurable traffic history. Either tiny or invisible.", "traffic", sources))

    if p is not None:
        (defs if p > 0.1 else pros if p < -0.1 else defs).append(
            _claim(f"Hiring: {cur['pressure_why']}.", "jobs", sources))
    else:
        pros.append(_claim("No job postings on record in the last two quarters.", "jobs", sources))

    if pr >= 0.5:
        defs.append(_claim(f"Funding: {cur['precipitation_why']}. Cash is fresh.", "funding", sources))
    elif pr == 0.0 and sig.get("funding"):
        pros.append(_claim(f"Funding: {cur['precipitation_why']}. Runway is the open question.", "funding", sources))
    else:
        pros.append(_claim(f"Funding: {cur['precipitation_why']}.", "funding", sources))

    for ev in cur["wind_events"][:3]:
        target = pros if ("left" in ev or "layoff" in ev.lower()) else defs
        target.append(_claim(f"Change: {ev}.", "people" if ("joined" in ev or "left" in ev) else "news", sources))

    layoffs = [n for n in sig.get("news", []) if n.get("kind") == "layoff"]
    for n in layoffs[-1:]:
        pros.append(_claim(f"News: {n['title']} ({n.get('date') or 'undated'}).", "news", sources))
    launches = [n for n in sig.get("news", []) if n.get("kind") == "launch"]
    for n in launches[-1:]:
        defs.append(_claim(f"News: {n['title']} ({n.get('date') or 'undated'}).", "news", sources))

    seo = sig.get("seo", {})
    if seo.get("domain_rating") is not None:
        dr = seo["domain_rating"]
        (defs if dr >= 40 else pros).append(_claim(f"Search authority: domain rating {dr:.0f}.", "seo", sources))

    if not pros:
        pros.append(_claim("Nothing in the public record cuts against them yet. That is a claim to test on the call, not a verdict.", "meta", sources))
    if not defs:
        defs.append(_claim("Absence of bad news is the only defense on record. Thin, but real.", "meta", sources))
    return pros, defs


_SCHEMA = {
    "type": "object",
    "properties": {
        "prosecution": {"type": "array", "items": {"type": "string"}},
        "defense": {"type": "array", "items": {"type": "string"}},
        "verdict": {"type": "string"},
    },
    "required": ["prosecution", "defense", "verdict"],
    "additionalProperties": False,
}


def polish_with_claude(company: dict, pros: list[dict], defs: list[dict]) -> dict | None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        return None
    client = anthropic.Anthropic()
    facts = {
        "company": company["name"],
        "condition": company["current"]["condition"],
        "forecast": company["forecast"],
        "prosecution_claims": [c["text"] for c in pros],
        "defense_claims": [c["text"] for c in defs],
    }
    prompt = (
        "You are writing both sides of a courtroom argument about a company's business momentum. "
        "Rewrite the prosecution claims (the case that this company is in trouble) and the defense "
        "claims (the case that it is fine) as sharp one-sentence arguments, one string per claim, "
        "keeping the same order and never adding facts that are not in the claims. Then give a "
        "one-sentence verdict.\n\n" + json.dumps(facts, indent=1)
    )
    try:
        resp = client.messages.create(
            model="claude-opus-5",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
        )
        if resp.stop_reason == "refusal":
            return None
        text = next(b.text for b in resp.content if b.type == "text")
        data = json.loads(text)
        if len(data["prosecution"]) == len(pros) and len(data["defense"]) == len(defs):
            return data
    except Exception as exc:  # network, auth, schema drift: fall back to templates
        print(f"  claude polish skipped for {company['name']}: {exc}")
    return None


def argue(company: dict, use_llm: bool = True) -> dict:
    pros, defs = template_arguments(company)
    polished = polish_with_claude(company, pros, defs) if use_llm else None
    if polished:
        for c, t in zip(pros, polished["prosecution"]):
            c["text"] = t
        for c, t in zip(defs, polished["defense"]):
            c["text"] = t
        verdict = polished["verdict"]
    else:
        m = company["current"]["momentum"]
        verdict = ("Momentum is positive; the defense has the better of it." if m > 0.15
                   else "Momentum is negative; the prosecution has the better of it." if m < -0.15
                   else "Evenly balanced; watch the wind.")
    return {"prosecution": pros, "defense": defs, "verdict": verdict}
