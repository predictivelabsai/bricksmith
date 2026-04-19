"""Rent-roll tools: parse/summarize/WALT/expiry waterfall."""

from __future__ import annotations

import json
from datetime import date
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from db import fetch_one


class PropSlugArgs(BaseModel):
    slug_or_id: str = Field(description="Property slug or numeric id.")


def _load_rent_roll(slug_or_id: str):
    try:
        pid = int(slug_or_id)
        row = fetch_one("SELECT p.id, p.name, p.asset_type, rr.as_of_date, rr.units "
                        "FROM bricksmith.properties p "
                        "JOIN bricksmith.rent_rolls rr ON rr.property_id = p.id "
                        "WHERE p.id = %s ORDER BY rr.as_of_date DESC LIMIT 1", (pid,))
    except (TypeError, ValueError):
        row = fetch_one("SELECT p.id, p.name, p.asset_type, rr.as_of_date, rr.units "
                        "FROM bricksmith.properties p "
                        "JOIN bricksmith.rent_rolls rr ON rr.property_id = p.id "
                        "WHERE p.slug = %s ORDER BY rr.as_of_date DESC LIMIT 1", (slug_or_id,))
    return row


def _summarize_rent_roll(slug_or_id: str) -> str:
    row = _load_rent_roll(slug_or_id)
    if not row:
        return "No rent roll for that property."
    units = row["units"]
    active = [u for u in units if u.get("status") == "active"]
    vacant = [u for u in units if u.get("status") == "vacant"]
    total_units = len(units)
    total_sqft = sum(u.get("sqft") or 0 for u in units)
    leased_sqft = sum(u.get("sqft") or 0 for u in active)
    monthly_rent = sum(u.get("rent") or 0 for u in active)

    summary = {
        "property": row["name"],
        "asset_type": row["asset_type"],
        "as_of": str(row["as_of_date"]),
        "total_line_items": total_units,
        "active_units": len(active),
        "vacant_units": len(vacant),
        "occupancy_units_pct": round(100 * len(active) / max(1, total_units), 1),
        "occupancy_sqft_pct": round(100 * leased_sqft / max(1, total_sqft), 1),
        "monthly_rent_in_place": monthly_rent,
        "annualized_rent_in_place": monthly_rent * 12,
        "avg_rent_per_unit": round(monthly_rent / max(1, len(active))),
        "avg_rent_psf_annual": round((monthly_rent * 12) / max(1, leased_sqft), 2) if leased_sqft else None,
    }

    sample_rows = [
        {
            "unit": u.get("unit"),
            "type": u.get("type"),
            "tenant": u.get("tenant") or "—",
            "sqft": u.get("sqft"),
            "monthly_rent": u.get("rent"),
            "lease_end": u.get("lease_end") or "—",
            "status": u.get("status"),
        }
        for u in units[:25]
    ]
    artifact = {
        "kind": "table",
        "title": f"Rent roll — {row['name']}",
        "subtitle": f"As of {row['as_of_date']} · {summary['active_units']}/{total_units} active",
        "columns": ["unit", "type", "tenant", "sqft", "monthly_rent", "lease_end", "status"],
        "rows": sample_rows,
    }
    return "__ARTIFACT__" + json.dumps({"summary": summary, **artifact})


summarize_rent_roll = StructuredTool.from_function(
    func=_summarize_rent_roll,
    name="summarize_rent_roll",
    description="Load the most recent rent roll for a property and return occupancy, WALT-style economics, "
                "and a sample of line items. Also emits a right-pane artifact with the rent roll table.",
    args_schema=PropSlugArgs,
)


def _lease_expiry_waterfall(slug_or_id: str) -> str:
    row = _load_rent_roll(slug_or_id)
    if not row:
        return "No rent roll for that property."
    units = row["units"]
    buckets: dict[int, dict] = {}
    for u in units:
        end = u.get("lease_end")
        if not end:
            continue
        try:
            y = int(str(end)[:4])
        except Exception:
            continue
        b = buckets.setdefault(y, {"year": y, "units": 0, "sqft": 0, "rent": 0})
        b["units"] += 1
        b["sqft"] += u.get("sqft") or 0
        b["rent"] += u.get("rent") or 0
    ordered = sorted(buckets.values(), key=lambda b: b["year"])
    total_rent = sum(b["rent"] for b in ordered) or 1
    for b in ordered:
        b["pct_of_rent"] = round(100 * b["rent"] / total_rent, 1)

    return "__ARTIFACT__" + json.dumps({
        "kind": "table",
        "title": f"Lease expiry waterfall — {row['name']}",
        "subtitle": f"{len(ordered)} expiry years",
        "columns": ["year", "units", "sqft", "rent", "pct_of_rent"],
        "rows": ordered,
    })


lease_expiry_waterfall = StructuredTool.from_function(
    func=_lease_expiry_waterfall,
    name="lease_expiry_waterfall",
    description="Year-by-year lease expiry rollup (units, sqft, rent) for a property.",
    args_schema=PropSlugArgs,
)


def _walt(slug_or_id: str) -> str:
    """Weighted-average lease term by rent."""
    row = _load_rent_roll(slug_or_id)
    if not row:
        return "No rent roll for that property."
    units = row["units"]
    today = date.today()
    total_rent = 0.0
    weighted = 0.0
    for u in units:
        if u.get("status") != "active":
            continue
        rent = u.get("rent") or 0
        end = u.get("lease_end")
        if not end:
            continue
        try:
            d = date.fromisoformat(str(end)[:10])
        except Exception:
            continue
        years_remaining = max(0.0, (d - today).days / 365.25)
        total_rent += rent
        weighted += rent * years_remaining
    walt = round(weighted / total_rent, 2) if total_rent else 0
    return json.dumps({
        "property": row["name"],
        "walt_years": walt,
        "rent_basis_monthly": round(total_rent, 2),
    })


walt_years = StructuredTool.from_function(
    func=_walt,
    name="walt_years",
    description="Weighted-average lease term (by rent) for a property, in years.",
    args_schema=PropSlugArgs,
)
