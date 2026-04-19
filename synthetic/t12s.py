"""Twelve-month operating statements per property — deterministic seasonality."""

from __future__ import annotations

import math
import random
from datetime import date
from dateutil.relativedelta import relativedelta

# Opex ratios (of EGI) by asset type — reasonable industry proxies
OPEX_BASE = {
    "multifamily": 0.42,
    "office":      0.52,
    "industrial":  0.18,
    "retail":      0.32,
}

# Category breakdown (share of total opex)
OPEX_SPLIT = {
    "multifamily": {"taxes": 0.25, "insurance": 0.08, "utilities": 0.12,
                    "maintenance": 0.18, "payroll": 0.22, "mgmt": 0.08, "other": 0.07},
    "office":      {"taxes": 0.22, "insurance": 0.06, "utilities": 0.18,
                    "maintenance": 0.20, "payroll": 0.16, "mgmt": 0.06, "other": 0.12},
    "industrial":  {"taxes": 0.38, "insurance": 0.12, "utilities": 0.06,
                    "maintenance": 0.15, "payroll": 0.08, "mgmt": 0.08, "other": 0.13},
    "retail":      {"taxes": 0.30, "insurance": 0.08, "utilities": 0.08,
                    "maintenance": 0.18, "payroll": 0.14, "mgmt": 0.10, "other": 0.12},
}


def _seasonal_factor(month: int, asset: str) -> float:
    """Multiplicative seasonality on revenue."""
    if asset == "multifamily":
        return 1.0 + 0.02 * math.sin((month - 3) / 12 * 2 * math.pi)
    if asset == "retail":
        return 1.0 + 0.06 * math.sin((month - 10) / 12 * 2 * math.pi)
    return 1.0


def generate_for_property(prop: dict, end_month: date, rng: random.Random) -> list[dict]:
    """Return 12 rows of {month, gross_rent, other_income, vacancy_loss, opex, noi}
    ending with end_month (most recent first-of-month)."""
    asset = prop["asset_type"]
    occ = (prop["occupancy_pct"] or 90) / 100

    # Base monthly gross
    if asset == "multifamily":
        avg_unit_rent = 1800 if prop["metro"] in {"Austin", "Denver", "Nashville"} else 1550
        base_gross = (prop["units"] or 120) * avg_unit_rent
    else:
        psf_annual = {"office": 38, "industrial": 9.5, "retail": 28}[asset]
        base_gross = (prop["sqft"] or 80_000) * psf_annual / 12

    base_opex_ratio = OPEX_BASE[asset]
    split = OPEX_SPLIT[asset]

    rows: list[dict] = []
    for i in range(11, -1, -1):
        m = end_month - relativedelta(months=i)
        season = _seasonal_factor(m.month, asset)
        noise = rng.uniform(0.94, 1.06)
        gross = base_gross * season * noise
        vacancy = gross * (1 - occ) * rng.uniform(0.9, 1.1)
        other = gross * rng.uniform(0.02, 0.08)
        egi = gross - vacancy + other

        opex_total = egi * base_opex_ratio * rng.uniform(0.92, 1.10)
        opex = {k: round(opex_total * v, 2) for k, v in split.items()}
        noi = egi - sum(opex.values())

        rows.append({
            "month": m.replace(day=1).isoformat(),
            "gross_rent": round(gross, 2),
            "other_income": round(other, 2),
            "vacancy_loss": round(vacancy, 2),
            "opex": opex,
            "noi": round(noi, 2),
        })
    return rows
