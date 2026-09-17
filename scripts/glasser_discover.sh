#!/usr/bin/env bash
# Discover which Glasser endpoints feed each weather signal, and what they cost.
# Runs ONLY catalog search (free). No paid runs. Output lands in data/catalog/.
# Prereq: npm i -g @glasser-ai/cli && glasser login
set -euo pipefail
mkdir -p data/catalog
declare -A Q=(
  [pool]="company search industry headcount geography"
  [identity]="company enrichment domain"
  [temperature_traffic]="website traffic analytics"
  [temperature_trend]="traffic estimate domain"
  [pressure_hiring]="job postings company"
  [precip_funding]="company enrichment funding"
  [precip_rounds]="funding rounds company"
  [wind_execs]="person search company"
  [wind_techstack]="company tech stack technologies"
  [visibility_seo]="organic keywords domain"
  [visibility_social]="social profile lookup"
  [front_news]="news search company"
)
for k in "${!Q[@]}"; do
  echo "== $k : ${Q[$k]}"
  glasser search -q "${Q[$k]}" --limit 10 -j > "data/catalog/$k.json" 2> "data/catalog/$k.err" || true
  python3 - "$k" <<'PY'
import json,sys
k=sys.argv[1]
try:
    d=json.load(open(f"data/catalog/{k}.json"))
except Exception as e:
    print("  (no result)", e); sys.exit()
rows=d if isinstance(d,list) else d.get("items") or d.get("endpoints") or d.get("results") or []
for r in rows[:10]:
    p=r.get("provider",{}); p=p.get("slug",p) if isinstance(p,dict) else p
    print(f"  {p} / {r.get('endpoint') or r.get('slug') or r.get('name')}  price={r.get('price')}")
PY
done
echo; echo "Next: glasser inspect -p <provider> -e <endpoint>  for each row you like. Read Price and charge clauses before running."
