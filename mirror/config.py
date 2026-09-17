from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ENDPOINTS_PATH = Path("config/endpoints.json")
ICP_PATH = Path("config/icp.json")
_PLACEHOLDER = re.compile(r"^\{([a-zA-Z0-9_.]+)\}$")


def load_endpoints() -> dict:
    return {k: v for k, v in json.loads(ENDPOINTS_PATH.read_text()).items() if not k.startswith("_")}


def save_endpoints(cfg: dict) -> None:
    full = json.loads(ENDPOINTS_PATH.read_text())
    full.update(cfg)
    ENDPOINTS_PATH.write_text(json.dumps(full, indent=2))


def load_icp() -> dict:
    return json.loads(ICP_PATH.read_text())


def _lookup(path: str, ctx: dict) -> Any:
    cur: Any = ctx
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit():
            cur = cur[int(part)] if int(part) < len(cur) else None
        else:
            return None
    return cur


def render(template: Any, ctx: dict) -> Any:
    """Substitute {placeholders} anywhere in a nested input template."""
    if isinstance(template, dict):
        return {k: render(v, ctx) for k, v in template.items()}
    if isinstance(template, list):
        return [render(v, ctx) for v in template]
    if isinstance(template, str):
        m = _PLACEHOLDER.match(template)
        if m:
            val = _lookup(m.group(1), ctx)
            return val if val is not None else template
        return re.sub(r"\{([a-zA-Z0-9_.]+)\}", lambda mm: str(_lookup(mm.group(1), ctx) or mm.group(0)), template)
    return template


def unresolved(cfg: dict) -> list[str]:
    return [k for k, v in cfg.items() if not (v.get("provider") and v.get("endpoint"))]
