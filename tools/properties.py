"""Property-lookup tools shared by many agents."""

from __future__ import annotations

import json
from typing import Annotated, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from db import fetch_all, fetch_one


class SearchPropertiesArgs(BaseModel):
    query: Optional[str] = Field(default=None, description="Free-text partial match on name, address, or description.")
    city: Optional[str] = Field(default=None)
    state: Optional[str] = Field(default=None)
    metro: Optional[str] = Field(default=None)
    asset_type: Optional[str] = Field(default=None, description="multifamily | office | industrial | retail")
    limit: int = Field(default=10, ge=1, le=50)


def _search_properties(**kw) -> str:
    args = SearchPropertiesArgs(**kw)
    sql = ["SELECT id, slug, name, address, city, state, asset_type, units, sqft, "
           "occupancy_pct, listing_status, seller_intent FROM bricksmith.properties WHERE TRUE"]
    params: list = []
    if args.query:
        sql.append("AND (name ILIKE %s OR address ILIKE %s OR description ILIKE %s)")
        q = f"%{args.query}%"
        params.extend([q, q, q])
    if args.city:
        sql.append("AND city ILIKE %s"); params.append(args.city)
    if args.state:
        sql.append("AND state = %s"); params.append(args.state.upper())
    if args.metro:
        sql.append("AND metro ILIKE %s"); params.append(args.metro)
    if args.asset_type:
        sql.append("AND asset_type = %s"); params.append(args.asset_type.lower())
    sql.append("ORDER BY id LIMIT %s"); params.append(args.limit)
    rows = fetch_all(" ".join(sql), tuple(params))

    if not rows:
        return "No matching properties."

    return json.dumps({
        "count": len(rows),
        "properties": [
            {
                "id": r["id"],
                "slug": r["slug"],
                "name": r["name"],
                "address": f"{r['address']}, {r['city']}, {r['state']}",
                "asset_type": r["asset_type"],
                "units": r["units"],
                "sqft": r["sqft"],
                "occupancy_pct": float(r["occupancy_pct"]) if r["occupancy_pct"] is not None else None,
                "listing_status": r["listing_status"],
                "seller_intent": r["seller_intent"],
            } for r in rows
        ],
    }, default=str)


search_properties = StructuredTool.from_function(
    func=_search_properties,
    name="search_properties",
    description="Search the Bricksmith property catalog. Filter by city, state, metro, asset_type, or a free-text query.",
    args_schema=SearchPropertiesArgs,
)


class GetPropertyArgs(BaseModel):
    slug_or_id: str = Field(description="Property slug (preferred) or numeric id.")


def _get_property(slug_or_id: str) -> str:
    try:
        pid = int(slug_or_id)
        row = fetch_one("SELECT * FROM bricksmith.properties WHERE id = %s", (pid,))
    except (TypeError, ValueError):
        row = fetch_one("SELECT * FROM bricksmith.properties WHERE slug = %s", (slug_or_id,))
    if not row:
        return "Not found."
    return json.dumps(row, default=str)


get_property = StructuredTool.from_function(
    func=_get_property,
    name="get_property",
    description="Fetch full details for one property by slug or numeric id.",
    args_schema=GetPropertyArgs,
)
