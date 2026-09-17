from __future__ import annotations

import argparse
import json
from datetime import date


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="mirror", description="Company weather forecast on Glasser data.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("balance", help="check Glasser auth and credits")
    d = sub.add_parser("discover", help="free catalog search for every signal")
    d.add_argument("--limit", type=int, default=8)
    r = sub.add_parser("resolve", help="pin provider/endpoint per signal")
    r.add_argument("picks", nargs="*", help="signal=provider/endpoint")
    r.add_argument("--auto", action="store_true", help="cheapest of the top three hits per signal")
    i = sub.add_parser("inspect", help="print schema and price for a resolved signal")
    i.add_argument("signal")
    e = sub.add_parser("estimate", help="estimated spend for N companies")
    e.add_argument("-n", type=int, default=50)
    sub.add_parser("pool", help="run the ICP company search (paid)")
    c = sub.add_parser("collect", help="pull every signal per company (paid, cached)")
    c.add_argument("--limit", type=int)
    c.add_argument("--workers", type=int, default=4)
    c.add_argument("--signals", help="comma list to restrict, e.g. news,jobs")
    c.add_argument("--yes", action="store_true", help="skip the spend confirmation")
    a = sub.add_parser("add", help="add one company by domain and collect it (paid)")
    a.add_argument("domain")
    a.add_argument("--name")
    b = sub.add_parser("build", help="score signals and write web/data.json")
    b.add_argument("--asof", default=date.today().isoformat())
    b.add_argument("--no-llm", action="store_true", help="template arguments only")
    dm = sub.add_parser("demo", help="generate synthetic signals and build")
    dm.add_argument("--seed", type=int, default=7)
    dm.add_argument("--asof", default=date.today().isoformat())
    s = sub.add_parser("serve", help="serve web/ with the live add endpoint")
    s.add_argument("--port", type=int, default=8765)
    sub.add_parser("briefing", help="print the top storms and fronts as markdown")

    args = p.parse_args(argv)

    if args.cmd == "balance":
        from . import glasser
        print(json.dumps(glasser.balance(), indent=1))
    elif args.cmd == "discover":
        from .catalog import discover
        discover(args.limit)
    elif args.cmd == "resolve":
        from .catalog import resolve
        picks = dict(x.split("=", 1) for x in args.picks)
        resolve(picks, auto=args.auto)
    elif args.cmd == "inspect":
        from .catalog import inspect_signal
        inspect_signal(args.signal)
    elif args.cmd == "estimate":
        from .catalog import estimate
        estimate(args.n)
    elif args.cmd == "pool":
        from .collect import pool
        pool()
    elif args.cmd == "collect":
        from .catalog import estimate
        from .collect import POOL_PATH, collect_all
        n = len(json.loads(POOL_PATH.read_text()))
        n = min(n, args.limit) if args.limit else n
        if not args.yes:
            est = estimate(n)
            ans = input(f"Spend up to ~${est} across {n} companies (cached calls are free)? [y/N] ")
            if ans.strip().lower() != "y":
                raise SystemExit("aborted")
        collect_all(args.limit, args.workers, args.signals.split(",") if args.signals else None)
    elif args.cmd == "add":
        from .collect import add_to_pool, collect_one
        add_to_pool(args.domain, args.name)
        sig = collect_one({"domain": args.domain, "name": args.name})
        print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in sig.items() if k != "sources"}, indent=1, default=str))
    elif args.cmd == "build":
        from .build import build, load_signals, write_build
        sigs = load_signals()
        synthetic = all(s.get("sources") and s["sources"][0].get("provider") == "synthetic" for s in sigs) if sigs else True
        data = build(sigs, date.fromisoformat(args.asof), synthetic=synthetic, use_llm=not args.no_llm)
        path = write_build(data)
        print(f"built {data['meta']['companies']} companies -> {path} (charges ${data['meta']['total_charge_usd']})")
    elif args.cmd == "demo":
        from .build import build, load_signals, write_build
        from .demo import write_demo
        asof = date.fromisoformat(args.asof)
        n = write_demo(asof, args.seed)
        data = build(load_signals(), asof, synthetic=True, use_llm=False)
        path = write_build(data)
        counts: dict[str, int] = {}
        for c in data["companies"]:
            counts[c["current"]["condition"]] = counts.get(c["current"]["condition"], 0) + 1
        print(f"demo: {n} synthetic companies -> {path}  conditions: {counts}")
    elif args.cmd == "serve":
        from .serve import serve
        serve(args.port)
    elif args.cmd == "briefing":
        from .briefing import briefing
        print(briefing())
