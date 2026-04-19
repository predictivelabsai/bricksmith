"""24 months of market signals per metro + asset type."""

from __future__ import annotations

import math
import random
from datetime import date
from dateutil.relativedelta import relativedelta

METRICS = ["cap_rate", "rent_growth", "vacancy", "absorption", "employment"]

# Baseline values keyed by (metro, asset_type)
def _baseline(metro: str, asset: str) -> dict[str, float]:
    boom = metro in {"Austin", "Nashville", "Raleigh"}
    return {
        "cap_rate":    {"multifamily": 4.6, "office": 6.8, "industrial": 5.4, "retail": 6.4}[asset] + (-0.2 if boom else 0),
        "rent_growth": {"multifamily": 3.2, "office": 1.1, "industrial": 4.8, "retail": 2.4}[asset] + (1.0 if boom else 0),
        "vacancy":     {"multifamily": 6.8, "office": 17.5, "industrial": 5.2, "retail": 4.4}[asset] + (-1.0 if boom else 0),
        "absorption":  {"multifamily": 1.2, "office": 0.2, "industrial": 2.6, "retail": 0.4}[asset],
        "employment":  2.1 + (1.2 if boom else 0),
    }


def generate(properties: list[dict], months: int = 24, seed: int = 42) -> list[dict]:
    rng = random.Random(seed + 7)
    rows: list[dict] = []
    seen: set[tuple] = set()

    pairs = {(p["metro"], p["asset_type"]) for p in properties}
    today = date.today().replace(day=1)

    for metro, asset in pairs:
        base = _baseline(metro, asset)
        for metric in METRICS:
            for i in range(months, 0, -1):
                m = today - relativedelta(months=i)
                t = i / months
                seasonal = 0.1 * math.sin(i / 6 * math.pi)
                # Cap rate rose in '23-24 and softened in '25-26; others smoother
                trend = {
                    "cap_rate":    0.4 * math.sin((t - 0.4) * math.pi),
                    "rent_growth": -0.8 * t,
                    "vacancy":     0.5 * math.sin((t - 0.6) * math.pi),
                    "absorption":  -0.6 * t,
                    "employment":  -0.3 * t,
                }[metric]
                value = base[metric] + trend + seasonal + rng.uniform(-0.15, 0.15)
                key = (metro, asset, metric, m)
                if key in seen:
                    continue
                seen.add(key)
                rows.append({
                    "metro": metro,
                    "asset_type": asset,
                    "metric": metric,
                    "value": round(value, 3),
                    "as_of_date": m.isoformat(),
                    "source": rng.choice(["CoStar", "RCA", "CBRE Research", "JLL Research", "BLS"]),
                })
    return rows
