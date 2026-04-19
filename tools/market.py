"""Market / comp tools."""

from __future__ import annotations

import json
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from db import fetch_all, fetch_one


class CompArgs(BaseModel):
    slug_or_id: Optional[str] = Field(default=None, description="Anchor property (optional).")
    metro: Optional[str] = Field(default=None)
    asset_type: Optional[str] = Field(default=None)
    min_sqft: Optional[int] = Field(default=None)
    max_sqft: Optional[int] = Field(default=None)
    limit: int = Field(default=8, ge=1, le=25)


def _resolve_pid(slug_or_id: Optional[str]) -> Optional[int]:
    if not slug_or_id:
        return None
    try:
        return int(slug_or_id)
    except (TypeError, ValueError):
        row = fetch_one("SELECT id FROM bricksmith.properties WHERE slug = %s", (slug_or_id,))
        return row["id"] if row else None


def _find_sales_comps(**kw) -> str:
    args = CompArgs(**kw)
    sql = ["SELECT comp_name, city, state, asset_type, sqft, units, sale_date, "
           "sale_price, cap_rate, price_per_unit, price_per_sqft, source "
           "FROM bricksmith.comps_sales WHERE TRUE"]
    params: list = []
    if args.slug_or_id:
        pid = _resolve_pid(args.slug_or_id)
        if pid:
            sql.append("AND property_id = %s"); params.append(pid)
    if args.metro:
        sql.append("AND city ILIKE %s"); params.append(args.metro)
    if args.asset_type:
        sql.append("AND asset_type = %s"); params.append(args.asset_type.lower())
    if args.min_sqft:
        sql.append("AND sqft >= %s"); params.append(args.min_sqft)
    if args.max_sqft:
        sql.append("AND sqft <= %s"); params.append(args.max_sqft)
    sql.append("ORDER BY sale_date DESC LIMIT %s"); params.append(args.limit)
    rows = fetch_all(" ".join(sql), tuple(params))
    if not rows:
        return "No sales comps found."
    rows2 = [
        {
            "comp_name": r["comp_name"], "city": r["city"], "asset_type": r["asset_type"],
            "sqft": r["sqft"], "units": r["units"],
            "sale_date": str(r["sale_date"]), "sale_price": float(r["sale_price"]),
            "cap_rate": float(r["cap_rate"]) if r["cap_rate"] else None,
            "price_per_sqft": float(r["price_per_sqft"]) if r["price_per_sqft"] else None,
            "source": r["source"],
        } for r in rows
    ]
    avg_cap = round(sum(r["cap_rate"] for r in rows2 if r["cap_rate"]) /
                    max(1, sum(1 for r in rows2 if r["cap_rate"])), 2)
    avg_ppsf = round(sum(r["price_per_sqft"] for r in rows2 if r["price_per_sqft"]) /
                     max(1, sum(1 for r in rows2 if r["price_per_sqft"])), 2)
    return "__ARTIFACT__" + json.dumps({
        "kind": "table",
        "title": "Sales comps",
        "subtitle": f"{len(rows2)} comps · avg cap {avg_cap}% · avg ppsf ${avg_ppsf}",
        "columns": ["comp_name", "city", "asset_type", "sqft", "sale_date", "sale_price",
                    "cap_rate", "price_per_sqft", "source"],
        "rows": rows2,
        "summary": {"avg_cap_rate": avg_cap, "avg_price_per_sqft": avg_ppsf},
    })


find_sales_comps = StructuredTool.from_function(
    func=_find_sales_comps,
    name="find_sales_comps",
    description="Return sales comps for a property (or freely by metro/asset_type). Outputs a comp table with average cap rate + ppsf.",
    args_schema=CompArgs,
)


class RentCompArgs(BaseModel):
    slug_or_id: Optional[str] = None
    unit_type: Optional[str] = None
    limit: int = Field(default=10, ge=1, le=25)


def _find_rent_comps(**kw) -> str:
    args = RentCompArgs(**kw)
    sql = ["SELECT comp_name, unit_type, sqft, rent, rent_per_sqft, effective_date, source "
           "FROM bricksmith.comps_rents WHERE TRUE"]
    params: list = []
    pid = _resolve_pid(args.slug_or_id)
    if pid:
        sql.append("AND property_id = %s"); params.append(pid)
    if args.unit_type:
        sql.append("AND unit_type ILIKE %s"); params.append(f"%{args.unit_type}%")
    sql.append("ORDER BY effective_date DESC LIMIT %s"); params.append(args.limit)
    rows = fetch_all(" ".join(sql), tuple(params))
    if not rows:
        return "No rent comps found."
    rows2 = [
        {"comp_name": r["comp_name"], "unit_type": r["unit_type"], "sqft": r["sqft"],
         "monthly_rent": r["rent"], "rent_psf_annual": float(r["rent_per_sqft"]) if r["rent_per_sqft"] else None,
         "effective_date": str(r["effective_date"]), "source": r["source"]}
        for r in rows
    ]
    return "__ARTIFACT__" + json.dumps({
        "kind": "table",
        "title": "Rent comps",
        "columns": ["comp_name", "unit_type", "sqft", "monthly_rent", "rent_psf_annual",
                    "effective_date", "source"],
        "rows": rows2,
    })


find_rent_comps = StructuredTool.from_function(
    func=_find_rent_comps,
    name="find_rent_comps",
    description="Return rent comps for a property (or freely by unit type).",
    args_schema=RentCompArgs,
)


class MarketSignalsArgs(BaseModel):
    metro: str
    asset_type: Optional[str] = None
    metric: Optional[str] = Field(default=None, description="cap_rate | rent_growth | vacancy | absorption | employment")


def _fetch_market_signals(**kw) -> str:
    args = MarketSignalsArgs(**kw)
    sql = ["SELECT metro, asset_type, metric, value, as_of_date "
           "FROM bricksmith.market_signals WHERE metro ILIKE %s"]
    params: list = [args.metro]
    if args.asset_type:
        sql.append("AND asset_type = %s"); params.append(args.asset_type.lower())
    if args.metric:
        sql.append("AND metric = %s"); params.append(args.metric)
    sql.append("ORDER BY as_of_date DESC LIMIT 50")
    rows = fetch_all(" ".join(sql), tuple(params))
    if not rows:
        return "No market signals for that filter."
    rows2 = [{"metric": r["metric"], "asset_type": r["asset_type"],
              "value": float(r["value"]) if r["value"] is not None else None,
              "as_of_date": str(r["as_of_date"])} for r in rows]
    return "__ARTIFACT__" + json.dumps({
        "kind": "table",
        "title": f"{args.metro} market signals",
        "subtitle": args.metric or "all metrics",
        "columns": ["metric", "asset_type", "value", "as_of_date"],
        "rows": rows2,
    })


fetch_market_signals = StructuredTool.from_function(
    func=_fetch_market_signals,
    name="fetch_market_signals",
    description="Fetch historical market signals (cap rate, rent growth, vacancy, absorption, employment) for a metro + asset type.",
    args_schema=MarketSignalsArgs,
)
