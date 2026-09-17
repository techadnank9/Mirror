"""Thin wrapper over the Glasser CLI with a disk cache.

Every paid run is cached under data/raw/<provider>/<endpoint>/<key>.json and
keyed by a stable idempotency key, so re-running the pipeline never spends
credits twice and an ambiguous failure can be retried safely.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

RAW_DIR = Path("data/raw")
CATALOG_DIR = Path("data/catalog")
_NAMESPACE = uuid.UUID("3f1a6c2e-7b4d-4e0a-9c1f-2d8e5a7b9c01")


class GlasserError(RuntimeError):
    pass


def cli_path() -> str:
    exe = shutil.which("glasser")
    if not exe:
        raise GlasserError(
            "glasser CLI not found. Install: npm install -g @glasser-ai/cli && glasser login"
        )
    return exe


def _call(args: list[str], timeout: int = 900) -> Any:
    proc = subprocess.run(
        [cli_path(), *args, "-j"], capture_output=True, text=True, timeout=timeout
    )
    if proc.returncode != 0:
        err: Any = proc.stderr.strip()
        try:
            err = json.loads(err)
        except (ValueError, TypeError):
            pass
        raise GlasserError(f"glasser {' '.join(args[:4])} failed (exit {proc.returncode}): {err}")
    out = proc.stdout.strip()
    return json.loads(out) if out else {}


def balance() -> Any:
    return _call(["balance"])


def search(query: str, limit: int = 10, cursor: str | None = None) -> Any:
    args = ["search", "-q", query, "--limit", str(limit)]
    if cursor:
        args += ["--cursor", cursor]
    return _call(args)


def inspect(provider: str, endpoint: str) -> Any:
    return _call(["inspect", "-p", provider, "-e", endpoint])


def cache_key(provider: str, endpoint: str, inp: dict) -> str:
    canonical = json.dumps([provider, endpoint, inp], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:20]


def cache_path(provider: str, endpoint: str, inp: dict) -> Path:
    return RAW_DIR / provider / endpoint / f"{cache_key(provider, endpoint, inp)}.json"


def run(provider: str, endpoint: str, inp: dict, *, force: bool = False, wait: bool = True) -> dict:
    """Run an endpoint, or return the cached record if this exact call already ran."""
    path = cache_path(provider, endpoint, inp)
    if path.exists() and not force:
        return json.loads(path.read_text())
    key = cache_key(provider, endpoint, inp)
    idem = str(uuid.uuid5(_NAMESPACE, key))
    args = ["run", "-p", provider, "-e", endpoint, "-i", json.dumps(inp), "--idempotency-key", idem]
    if wait:
        args.append("--wait")
    response = _call(args)
    record = {
        "provider": provider,
        "endpoint": endpoint,
        "input": inp,
        "idempotency_key": idem,
        "response": response,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=1))
    return record


# ---- tolerant readers over CLI JSON shapes -------------------------------

def _find_key(obj: Any, names: tuple[str, ...], depth: int = 0) -> Any:
    if depth > 6:
        return None
    if isinstance(obj, dict):
        for n in names:
            if n in obj and obj[n] not in (None, ""):
                return obj[n]
        for v in obj.values():
            found = _find_key(v, names, depth + 1)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj[:20]:
            found = _find_key(v, names, depth + 1)
            if found is not None:
                return found
    return None


def output_of(record: dict) -> Any:
    resp = record.get("response", record)
    if isinstance(resp, dict):
        for k in ("output", "result", "data", "body"):
            if k in resp:
                return resp[k]
    return resp


def charge_of(record: dict) -> Decimal:
    val = _find_key(record.get("response", record), ("charge", "charged", "amount_charged"))
    if isinstance(val, dict):
        val = _find_key(val, ("amount", "value", "usd"))
    try:
        return Decimal(str(val)) if val is not None else Decimal("0")
    except Exception:
        return Decimal("0")


def run_url_of(record: dict) -> str | None:
    val = _find_key(record.get("response", record), ("run_url", "runUrl", "url"))
    return str(val) if isinstance(val, str) and val.startswith("http") else None


def status_of(record: dict) -> str:
    val = _find_key(record.get("response", record), ("status",))
    return str(val) if val else "UNKNOWN"


def price_of(inspect_result: Any) -> Decimal:
    val = _find_key(inspect_result, ("price", "unit_price", "price_usd"))
    if isinstance(val, dict):
        val = _find_key(val, ("amount", "value", "usd"))
    try:
        return Decimal(str(val)) if val is not None else Decimal("0")
    except Exception:
        return Decimal("0")


def search_rows(search_result: Any) -> list[dict]:
    if isinstance(search_result, list):
        return [r for r in search_result if isinstance(r, dict)]
    if isinstance(search_result, dict):
        for k in ("items", "endpoints", "results", "data", "rows"):
            if isinstance(search_result.get(k), list):
                return [r for r in search_result[k] if isinstance(r, dict)]
    return []


def row_identity(row: dict) -> tuple[str, str, str]:
    prov = row.get("provider") or row.get("provider_slug") or ""
    if isinstance(prov, dict):
        prov = prov.get("slug") or prov.get("id") or prov.get("name") or ""
    ep = row.get("endpoint") or row.get("slug") or row.get("id") or row.get("name") or ""
    if isinstance(ep, dict):
        ep = ep.get("slug") or ep.get("id") or ep.get("name") or ""
    price = row.get("price")
    if isinstance(price, dict):
        price = price.get("amount") or price.get("value") or price.get("usd")
    return str(prov), str(ep), str(price if price is not None else "?")
