"""Capital / LP tools: memo, teaser, LP update, CRM."""

from __future__ import annotations

import json
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from db import fetch_all, fetch_one


class PropArgs(BaseModel):
    slug_or_id: str = Field(description="Property slug or id.")


def _resolve_pid(slug_or_id):
    try:
        return int(slug_or_id)
    except (TypeError, ValueError):
        row = fetch_one("SELECT id FROM bricksmith.properties WHERE slug = %s", (slug_or_id,))
        return row["id"] if row else None


def _deal_brief(slug_or_id: str) -> str:
    """Compact structured dump of everything the memo/teaser writers need."""
    pid = _resolve_pid(slug_or_id)
    if not pid:
        return "Property not found."
    prop = fetch_one("SELECT * FROM bricksmith.properties WHERE id = %s", (pid,))
    t12_rows = fetch_all("SELECT noi, gross_rent, vacancy_loss FROM bricksmith.t12_statements "
                         "WHERE property_id = %s", (pid,))
    noi = sum(float(r["noi"] or 0) for r in t12_rows)
    pf = fetch_one("SELECT assumptions, returns FROM bricksmith.pro_formas "
                   "WHERE property_id = %s ORDER BY id DESC LIMIT 1", (pid,))
    debt = fetch_one("SELECT ltv, dscr, tranches FROM bricksmith.debt_stacks "
                     "WHERE property_id = %s ORDER BY id DESC LIMIT 1", (pid,))
    sales = fetch_all("SELECT avg(cap_rate) as avg_cap, avg(price_per_sqft) as avg_ppsf "
                      "FROM bricksmith.comps_sales WHERE property_id = %s", (pid,))
    brief = {
        "property": {
            "name": prop["name"], "address": prop["address"],
            "city": prop["city"], "state": prop["state"],
            "asset_type": prop["asset_type"], "units": prop["units"],
            "sqft": prop["sqft"], "year_built": prop["year_built"],
            "occupancy_pct": float(prop["occupancy_pct"]) if prop["occupancy_pct"] else None,
            "asking_price": float(prop["asking_price"]) if prop["asking_price"] else None,
            "description": prop["description"],
        },
        "t12_noi": round(noi, 2),
        "pro_forma": {
            "assumptions": pf["assumptions"] if pf else None,
            "returns": pf["returns"] if pf else None,
        },
        "debt_stack": {
            "ltv_pct": float(debt["ltv"]) if debt and debt["ltv"] else None,
            "dscr": float(debt["dscr"]) if debt and debt["dscr"] else None,
            "tranches": debt["tranches"] if debt else None,
        },
        "comps": {
            "avg_cap_rate": float(sales[0]["avg_cap"]) if sales and sales[0]["avg_cap"] else None,
            "avg_price_per_sqft": float(sales[0]["avg_ppsf"]) if sales and sales[0]["avg_ppsf"] else None,
        },
    }
    return json.dumps(brief)


deal_brief = StructuredTool.from_function(
    func=_deal_brief,
    name="deal_brief",
    description="Pull a compact structured dossier about a property — attributes, T12 NOI, latest pro forma, debt stack, comps — for memo/teaser writers to summarize.",
    args_schema=PropArgs,
)


class CRMArgs(BaseModel):
    stage: Optional[str] = Field(default=None, description="cold | qualified | meeting | committed | closed | passed")
    focus: Optional[str] = Field(default=None, description="multifamily | office | industrial | retail | mixed")
    min_check: Optional[float] = Field(default=None)
    days_since_touch: Optional[int] = Field(default=None, description="Filter to LPs not touched in N days.")
    limit: int = Field(default=15, ge=1, le=50)


def _crm_lookup(**kw) -> str:
    args = CRMArgs(**kw)
    sql = ["SELECT name, firm, email, check_size, stage, focus, geography, last_touch, notes "
           "FROM bricksmith.investor_crm WHERE TRUE"]
    params: list = []
    if args.stage:
        sql.append("AND stage = %s"); params.append(args.stage)
    if args.focus:
        sql.append("AND focus = %s"); params.append(args.focus)
    if args.min_check:
        sql.append("AND check_size >= %s"); params.append(args.min_check)
    if args.days_since_touch:
        sql.append("AND last_touch < now() - (%s || ' days')::interval"); params.append(args.days_since_touch)
    sql.append("ORDER BY check_size DESC, last_touch DESC LIMIT %s"); params.append(args.limit)
    rows = fetch_all(" ".join(sql), tuple(params))
    if not rows:
        return "No LPs match."
    rows2 = [{**r, "check_size": float(r["check_size"]) if r["check_size"] else None,
              "last_touch": str(r["last_touch"]) if r["last_touch"] else None} for r in rows]
    return "__ARTIFACT__" + json.dumps({
        "kind": "table",
        "title": "LP shortlist",
        "columns": ["name", "firm", "stage", "focus", "check_size", "last_touch"],
        "rows": rows2,
        "summary": {"count": len(rows2)},
    })


crm_lookup = StructuredTool.from_function(
    func=_crm_lookup,
    name="crm_lookup",
    description="Filter the investor CRM by stage, focus, min check size, and days-since-last-touch.",
    args_schema=CRMArgs,
)


def _portfolio_snapshot() -> str:
    """For LP updates: deals under management, weighted NOI, upcoming events."""
    rows = fetch_all(
        "SELECT asset_type, count(*) as n, "
        "sum(units)::bigint as total_units, sum(sqft)::bigint as total_sqft, "
        "avg(occupancy_pct) as avg_occ "
        "FROM bricksmith.properties "
        "WHERE listing_status IN ('off_market','closed') "
        "GROUP BY asset_type ORDER BY asset_type"
    )
    rows2 = [{"asset_type": r["asset_type"], "properties": r["n"],
              "total_units": r["total_units"], "total_sqft": r["total_sqft"],
              "avg_occupancy_pct": round(float(r["avg_occ"]), 1) if r["avg_occ"] else None}
             for r in rows]
    return "__ARTIFACT__" + json.dumps({
        "kind": "table",
        "title": "Portfolio snapshot",
        "columns": ["asset_type", "properties", "total_units", "total_sqft", "avg_occupancy_pct"],
        "rows": rows2,
    })


portfolio_snapshot = StructuredTool.from_function(
    func=_portfolio_snapshot,
    name="portfolio_snapshot",
    description="Return a portfolio-wide snapshot broken down by asset type — property count, units, sqft, average occupancy.",
    args_schema=BaseModel,
)
