# Event runbook

Everything below runs on a laptop with Node 22 and Python 3.10+. No Python packages are
required. The `anthropic` package is optional and only sharpens the argument prose.

## 0. Before the event (10 minutes, free)

```
npm install -g @glasser-ai/cli
glasser login                       # browser approval, prints available balance
python -m mirror balance            # proves the CLI and key work
python -m mirror demo               # synthetic map, zero credits
python -m mirror serve              # http://localhost:8765
```

Open the URL. Click a storm, drag the timeline, export a briefing. If that works, the
only thing left is real data.

## 1. Discover endpoints (free)

```
python -m mirror discover
```

Prints, per signal, the providers Glasser's catalog offers with the price beside each.
Search results are relevance-ranked, so the first row is usually right. Traffic is the
expensive row: look at it first.

## 2. Pin endpoints

Either take the cheapest of the top three per signal:

```
python -m mirror resolve --auto
```

or pin by hand, one per signal:

```
python -m mirror resolve traffic=similarweb/traffic-overview jobs=theirstack/job-search
```

Then read each input schema (free) and adjust the `input` template in
`config/endpoints.json` to match the field names the endpoint actually wants:

```
python -m mirror inspect traffic
python -m mirror inspect jobs
```

Placeholders available in `input`: `{domain}`, `{name}`, `{icp.<field>}`.

## 3. Set the ICP

Edit `config/icp.json`. Narrow beats wide. Fifty companies with every signal makes a
full map. Five hundred with one signal makes a boring table.

## 4. Pull the pool, then collect

```
python -m mirror pool                # one paid search, prints charge and run URL
python -m mirror estimate -n 50      # cost before spending
python -m mirror collect --limit 10  # pilot ten companies, confirm the shapes look right
python -m mirror build && python -m mirror serve
```

If the pilot's gauges show "no data" for a signal, open `data/raw/<provider>/<endpoint>/`
and look at the payload. Set that signal's `path` in `config/endpoints.json` to the key
holding the list, rebuild, and it will pick up. Then run the rest:

```
python -m mirror collect --yes
python -m mirror build
```

Every call is cached under `data/raw`. Re-running collect or build never spends again.

## 5. On stage

- `python -m mirror serve`, full screen, dark room.
- Press play on the timeline. Say nothing for the first loop.
- Click the biggest storm. Read one prosecution claim and one defense claim.
- Type a company the audience names into the search box and press Enter. If it is not
  on the map, the server pulls it live through Glasser, scores it, and drops it on the
  radar with the charge shown in the toast.
- Export briefing. Show the markdown with run URLs on every claim.

## Sharper arguments (optional)

```
pip install anthropic
export ANTHROPIC_API_KEY=...
python -m mirror build
```

With the key set, the build asks Claude Opus 5 to rewrite the template claims into
sharper sentences without adding facts. Without it, the template prose is used.

## Where things live

| Path | What |
|---|---|
| `config/endpoints.json` | signal to provider/endpoint/input mapping |
| `config/icp.json` | the pool filter |
| `data/raw/` | every Glasser response, cached and idempotent |
| `data/signals/` | one normalized JSON per company |
| `web/data.json` | the scored map the page reads |
| `mirror/weather.py` | the scoring rules, in plain functions |
| `mirror/normalize.py` | payload to signal extraction, heuristic |
| `tests/` | `python -m unittest discover -s tests` |
