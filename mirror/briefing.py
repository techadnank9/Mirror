"""Markdown briefing of the map: storms, fronts, and the strongest sunny accounts."""
from __future__ import annotations

import json

from .build import BUILD_PATH


def briefing() -> str:
    data = json.loads(BUILD_PATH.read_text())
    cs = data["companies"]
    by = lambda cond: [c for c in cs if c["current"]["condition"] == cond]
    lines = [f"# Weather briefing — {data['meta']['asof']}", ""]
    if data["meta"].get("synthetic"):
        lines.append("_Synthetic demo data._\n")
    lines.append(f"{len(cs)} companies. Storms {len(by('storm'))}, fronts {len(by('front'))}, sunny {len(by('sunny'))}, cloudy {len(by('cloudy'))}, fog {len(by('fog'))}. Glasser spend ${data['meta']['total_charge_usd']}.\n")
    for title, cond, n in (("Fronts incoming (reach out now)", "front", 10), ("Storms (churn risk / poaching window)", "storm", 10), ("Sunny (buying, not cutting)", "sunny", 5)):
        rows = by(cond)
        rows.sort(key=lambda c: -abs(c["current"]["momentum"]))
        if not rows:
            continue
        lines.append(f"## {title}")
        for c in rows[:n]:
            cur = c["current"]
            lines.append(f"- **{c['name']}** ({c['sector']}) — {c['forecast']}")
            lines.append(f"  - {cur['temperature_why']}; {cur['pressure_why']}; {cur['precipitation_why']}; wind {cur['wind_direction']}.")
            for s in c["sources"]:
                if s.get("run_url"):
                    lines.append(f"  - source: {s['signal']} via {s['provider']} {s['run_url']}")
        lines.append("")
    return "\n".join(lines)
