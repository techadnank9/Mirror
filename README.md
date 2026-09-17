# Mirror

**Every company is a weather system.** Mirror feeds verified business intelligence from
[Glasser](https://glasser.ai) into a scoring engine and renders each company on a radar
as sun, cloud, storm, front, or fog. Behind every glyph is a prosecution and a defense,
each claim tied to the Glasser run that produced it.

| Weather | Signal | Glasser capability |
|---|---|---|
| Temperature | web traffic momentum | website traffic analytics |
| Pressure | hiring momentum | job postings |
| Precipitation | funding recency | company enrichment, funding rounds |
| Wind | leadership and stack change | person search, tech stack, news |
| Visibility | search footprint | domain rating, organic keywords |

A **front** is a company where one signal just jumped while the rest lags. That is the
"ready to buy now" moment. A **storm** is a churn risk if they are your customer and a
poaching window if they are not.

## Run it in two minutes, no credits

```
python -m mirror demo      # 39 synthetic companies across 12 months
python -m mirror serve     # http://localhost:8765
```

## Run it on real data

See `docs/RUNBOOK.md`. Short version: `glasser login`, `mirror discover`, `mirror resolve
--auto`, `mirror pool`, `mirror collect`, `mirror build`, `mirror serve`. Every paid call
is cached and idempotent, so nothing is ever charged twice.

## Layout

- `mirror/` Python pipeline, standard library only. `glasser.py` wraps the CLI with a
  cache, `normalize.py` turns any provider payload into one schema, `weather.py` scores,
  `argue.py` writes both sides, `build.py` assembles `web/data.json`.
- `web/` a single page: radar, timeline, side panel, live add, briefing export.
- `.claude/skills/` Glasser's own skills so Claude Code drives the data plane correctly.
- `docs/GLASSER.md` how the sponsor's platform works and the budget plan.
