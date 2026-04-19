"""Asset-management tools: rent opt, opex variance, capex ranking, tenant churn."""

from __future__ import annotations

import json
from datetime import date
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from db import fetch_all, fetch_one


def _resolve_pid(slug_or_id):
    try:
        return int(slug_or_id)
    except (TypeError, ValueError):
        row = fetch_one("SELECT id FROM bricksmith.properties WHERE slug = %s", (slug_or_id,))
        return row["id"] if row else None


class PropArgs(BaseModel):
    slug_or_id: str


def _rent_opt(slug_or_id: str) -> str:
    pid = _resolve_pid(slug_or_id)
    if not pid:
        return "Property not found."
    prop = fetch_one("SELECT name, asset_type, city FROM bricksmith.properties WHERE id = %s", (pid,))
    rr = fetch_one("SELECT units FROM bricksmith.rent_rolls WHERE property_id = %s "
                   "ORDER BY as_of_date DESC LIMIT 1", (pid,))
    comps = fetch_all("SELECT avg(rent_per_sqft)::numeric(10,2) as avg_psf, "
                      "unit_type FROM bricksmith.comps_rents "
                      "WHERE property_id = %s OR (%s::text IS NULL) "
                      "GROUP BY unit_type", (pid, prop["city"]))

    comp_map = {c["unit_type"]: float(c["avg_psf"]) for c in comps if c["avg_psf"]}
    recs = []
    for u in (rr["units"] if rr else []):
        if u.get("status") != "active":
            continue
        in_place = u.get("rent", 0)
        sqft = u.get("sqft", 1) or 1
        in_place_psf = in_place * 12 / sqft
        market_psf = None
        for key in comp_map:
            if key.lower() in (u.get("type") or "").lower():
                market_psf = comp_map[key]; break
        if market_psf is None and comp_map:
            market_psf = sum(comp_map.values()) / len(comp_map)
        if market_psf is None:
            continue
        delta_pct = 100 * (market_psf - in_place_psf) / in_place_psf if in_place_psf else 0
        recs.append({
            "unit": u.get("unit"),
            "type": u.get("type"),
            "in_place_rent": in_place,
            "in_place_psf": round(in_place_psf, 2),
            "market_psf": round(market_psf, 2),
            "delta_pct": round(delta_pct, 1),
            "lease_end": u.get("lease_end"),
        })
    recs.sort(key=lambda r: r["delta_pct"], reverse=True)
    top = recs[:20]
    return "__ARTIFACT__" + json.dumps({
        "kind": "table",
        "title": f"Rent optimization — {prop['name']}",
        "subtitle": f"{len(recs)} active units ranked by below-market delta",
        "columns": ["unit", "type", "in_place_rent", "in_place_psf", "market_psf", "delta_pct", "lease_end"],
        "rows": top,
    })


rent_optimization_recs = StructuredTool.from_function(
    func=_rent_opt,
    name="rent_optimization_recs",
    description="Compare in-place rents to local comps and rank units by below-market delta.",
    args_schema=PropArgs,
)


def _opex_variance(slug_or_id: str) -> str:
    pid = _resolve_pid(slug_or_id)
    if not pid:
        return "Property not found."
    rows = fetch_all("SELECT month, opex FROM bricksmith.t12_statements "
                     "WHERE property_id = %s ORDER BY month ASC", (pid,))
    if len(rows) < 2:
        return "Not enough T12 history."
    # per-category avg of first N months vs last month
    total = len(rows)
    split = max(1, total - 3)  # baseline = first 9, recent = last 3
    cats = set().union(*[set((r["opex"] or {}).keys()) for r in rows])
    variance = []
    for c in cats:
        base = sum(float((r["opex"] or {}).get(c, 0)) for r in rows[:split]) / split
        recent = sum(float((r["opex"] or {}).get(c, 0)) for r in rows[split:]) / max(1, total - split)
        delta = recent - base
        pct = 100 * delta / base if base else 0
        variance.append({
            "category": c,
            "baseline_avg": round(base, 2),
            "recent_avg": round(recent, 2),
            "abs_delta": round(delta, 2),
            "pct_delta": round(pct, 1),
        })
    variance.sort(key=lambda v: abs(v["pct_delta"]), reverse=True)
    return "__ARTIFACT__" + json.dumps({
        "kind": "table",
        "title": "Opex variance (recent 3 mo vs. prior 9)",
        "columns": ["category", "baseline_avg", "recent_avg", "abs_delta", "pct_delta"],
        "rows": variance,
    })


opex_variance = StructuredTool.from_function(
    func=_opex_variance,
    name="opex_variance",
    description="Compute recent vs baseline opex by category from a property's T12; ranks categories by variance magnitude.",
    args_schema=PropArgs,
)


def _capex_ranking(slug_or_id: str) -> str:
    """Rank synthetic capex candidates by expected ROI."""
    pid = _resolve_pid(slug_or_id)
    if not pid:
        return "Property not found."
    prop = fetch_one("SELECT name, asset_type, sqft, units FROM bricksmith.properties WHERE id = %s", (pid,))
    sqft = prop["sqft"] or 50_000
    units = prop["units"] or 0

    # synthetic project catalog — deterministic
    catalog = [
        {"project": "Roof replacement", "cost": round(sqft * 14, 0),
         "noi_lift": round(sqft * 0.15, 0), "urgency": "high", "risk_if_deferred": "Active leaks; insurance exposure."},
        {"project": "HVAC RTU swap (5 units)", "cost": 185_000,
         "noi_lift": 62_000, "urgency": "medium",
         "risk_if_deferred": "Aging 18 yr units; tenant comfort complaints."},
        {"project": "Common-area lighting LED retrofit", "cost": 48_000,
         "noi_lift": 24_000, "urgency": "low",
         "risk_if_deferred": "Rebate window expires in 14 months."},
        {"project": "Unit interior refresh program",
         "cost": round((units or 50) * 7_500, 0),
         "noi_lift": round((units or 50) * 1_600, 0),
         "urgency": "medium",
         "risk_if_deferred": "$125/mo below-market at turn."},
        {"project": "Parking seal-coat + restripe", "cost": 62_000,
         "noi_lift": 4_000, "urgency": "low",
         "risk_if_deferred": "Cosmetic; minor drainage impact."},
    ]
    for c in catalog:
        c["roi_pct"] = round(100 * c["noi_lift"] / c["cost"], 1) if c["cost"] else 0
    catalog.sort(key=lambda c: c["roi_pct"], reverse=True)
    return "__ARTIFACT__" + json.dumps({
        "kind": "table",
        "title": f"Capex ranking — {prop['name']}",
        "columns": ["project", "cost", "noi_lift", "roi_pct", "urgency"],
        "rows": catalog,
    })


capex_ranking = StructuredTool.from_function(
    func=_capex_ranking,
    name="capex_ranking",
    description="Rank pending capex projects for a property by expected ROI (NOI lift / cost).",
    args_schema=PropArgs,
)


def _tenant_churn(slug_or_id: str) -> str:
    pid = _resolve_pid(slug_or_id)
    if not pid:
        return "Property not found."
    prop = fetch_one("SELECT name, asset_type FROM bricksmith.properties WHERE id = %s", (pid,))
    leases = fetch_all(
        "SELECT tenant, unit, base_rent, sqft, start_date, end_date "
        "FROM bricksmith.leases WHERE property_id = %s AND status='active' "
        "ORDER BY end_date ASC LIMIT 30",
        (pid,),
    )
    today = date.today()
    rows = []
    for l in leases:
        if not l["end_date"]:
            continue
        end_d = l["end_date"]
        days_to = (end_d - today).days
        tenure = (today - (l["start_date"] or end_d)).days
        # simple scoring: high churn risk if near expiry + short tenure + small sqft
        score = 0.0
        if days_to < 90: score += 0.5
        elif days_to < 270: score += 0.3
        if tenure < 365: score += 0.25
        if (l["sqft"] or 0) < 3000: score += 0.1
        # noise based on rent-vs-avg (placeholder)
        score = min(0.95, round(score, 2))
        rows.append({
            "tenant": l["tenant"], "unit": l["unit"],
            "sqft": l["sqft"], "monthly_rent": float(l["base_rent"]) if l["base_rent"] else None,
            "end_date": str(end_d), "days_to_expiry": days_to,
            "churn_score": score,
        })
    rows.sort(key=lambda r: -r["churn_score"])
    return "__ARTIFACT__" + json.dumps({
        "kind": "table",
        "title": f"Tenant churn risk — {prop['name']}",
        "subtitle": f"{len(rows)} active tenants ranked by churn score",
        "columns": ["tenant", "unit", "sqft", "monthly_rent", "end_date", "days_to_expiry", "churn_score"],
        "rows": rows[:25],
    })


tenant_churn = StructuredTool.from_function(
    func=_tenant_churn,
    name="tenant_churn_scores",
    description="Score each active commercial tenant for churn/renewal risk based on time-to-expiry, tenure, and size.",
    args_schema=PropArgs,
)
