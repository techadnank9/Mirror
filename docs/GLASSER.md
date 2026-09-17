# Using Glasser in this project

Glasser is one API key over 1,000+ paid data endpoints (People Data Labs, Ahrefs,
DataForSEO, Serper, Apollo and others). You search a catalog, inspect an endpoint's
price, run it, and pay per call. Empty results and failed calls cost $0.

## Setup on your laptop (2 minutes)

1. Open this repo in Claude Code. `.mcp.json` registers the Glasser MCP server, so the
   tools `search`, `inspect`, `run`, `balance` appear automatically.
2. Run `/mcp`, pick `glasser`, click Authenticate. Sign in, choose the workspace
   holding the event credits, click Allow.
3. Ask Claude to call `balance`. If it returns your credits, you are live.

Optional CLI for scripting and large outputs:

```
npm install -g @glasser-ai/cli
glasser login
glasser balance
```

## The three verbs

| Verb | What it does | Cost |
|---|---|---|
| `search -q "<capability>"` | Finds endpoints across providers, shows price beside each | Free |
| `inspect -p <provider> -e <endpoint>` | Input schema, price, charge clauses, sync or async | Free |
| `run -p <provider> -e <endpoint> -i '<json>'` | Executes. Prints Charge and a Run URL | Paid |

Rules that keep the balance safe: always inspect before run, start with small `limit`
values, and never loop over runs without knowing the per-call price first.

## Signal to weather mapping

Each weather variable is fed by one capability. The middle column is a catalog search
query, not a provider name. Run `scripts/glasser_discover.sh` to see real providers
and prices for every row.

| Weather | Business signal | Catalog search | Cost dial |
|---|---|---|---|
| Temperature | Web traffic and trend | `website traffic analytics` | Most expensive row. Price first. |
| Pressure | Open roles, hiring velocity | `job postings company` | Per posting or per query |
| Precipitation | Funding rounds, time since last | `company enrichment funding` | Usually per lookup, empty is free |
| Wind | Exec arrivals, tech stack changes | `person search company`, `company tech stack` | Per person. Enrich 2 to 3 execs max |
| Visibility | SEO keywords, social presence | `organic keywords domain`, `social profile lookup` | `limit` is the cost dial |
| Front incoming | Dated news events | `news search company` | Cheap. Refresh this live on stage |

Composite conditions:

- Sunny: warm traffic, rising pressure, recent rain.
- Cloudy: flat everywhere.
- Storm: cooling traffic, falling pressure, long dry spell.
- Front incoming: one signal jumps while the others lag. The "ready to buy now" moment.
- Fog: almost no footprint. Ghost company.

## Budget plan for $100

| Step | Calls | Rough cost |
|---|---|---|
| Company pool, 5 searches | 5 | $3 |
| Company enrichment, 50 companies | 50 | $8 |
| Exec enrichment, 2 per company | 100 | $30 |
| News, 50 companies | 50 | $3 |
| Keywords, 10 per company | 500 | $10 |
| Reserve for live demo and re-runs | | $45 |

Go narrow and deep. Fifty companies with every signal makes a full map. Five hundred
companies with one signal makes a boring table.

## Cache everything

Every run result goes to `data/raw/<provider>/<endpoint>/<key>.json`. Re-running the
demo must never re-spend credits. Retry an ambiguous failure with the same
idempotency key. It replays the original run and is never charged twice.

## Recipes installed

`.claude/skills/` carries Glasser's own recipes. Claude Code loads them automatically.

- `glasser`: the mechanism. How to search, inspect, run, and stay safe.
- `competitor-research`: one profile per rival with traffic, hiring, funding, SEO.
- `investor-diligence`: memo with red flags. The backbone of the Anti-Portfolio drilldown.
- `prospect-list`: ICP to company table to contacts. Builds the map's candidate pool.

Sources: github.com/glasser-ai/plugins and github.com/glasser-ai/skills, MIT licensed.
