"""Financial modeling tools: T12 normalize, pro-forma, debt sizing, returns."""

from __future__ import annotations

import json
import math
from datetime import date
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from db import connect, fetch_all, fetch_one


class PropSlugArgs(BaseModel):
    slug_or_id: str = Field(description="Property slug or numeric id.")


def _resolve_pid(slug_or_id: str) -> Optional[int]:
    try:
        return int(slug_or_id)
    except (TypeError, ValueError):
        row = fetch_one("SELECT id FROM bricksmith.properties WHERE slug = %s", (slug_or_id,))
        return row["id"] if row else None


def _normalize_t12(slug_or_id: str) -> str:
    pid = _resolve_pid(slug_or_id)
    if not pid:
        return "Property not found."
    prop = fetch_one("SELECT name, asset_type FROM bricksmith.properties WHERE id = %s", (pid,))
    rows = fetch_all(
        "SELECT month, gross_rent, other_income, vacancy_loss, opex, noi "
        "FROM bricksmith.t12_statements WHERE property_id = %s ORDER BY month ASC",
        (pid,),
    )
    if not rows:
        return "No T12 rows."

    gross   = sum(float(r["gross_rent"] or 0) for r in rows)
    other   = sum(float(r["other_income"] or 0) for r in rows)
    vac     = sum(float(r["vacancy_loss"] or 0) for r in rows)
    opex_total = {
        k: sum(float((r["opex"] or {}).get(k, 0)) for r in rows)
        for k in set().union(*[set((r["opex"] or {}).keys()) for r in rows])
    }
    noi = sum(float(r["noi"] or 0) for r in rows)
    egi = gross + other - vac

    normalized = {
        "property": prop["name"],
        "period": f"{rows[0]['month']} to {rows[-1]['month']}",
        "months": len(rows),
        "gross_potential_rent": round(gross, 2),
        "other_income": round(other, 2),
        "vacancy_loss": round(vac, 2),
        "effective_gross_income": round(egi, 2),
        "opex_by_category": {k: round(v, 2) for k, v in opex_total.items()},
        "opex_total": round(sum(opex_total.values()), 2),
        "noi": round(noi, 2),
        "noi_margin": round(noi / max(1, egi), 3),
    }

    chart_rows = [
        {"month": str(r["month"])[:7],
         "gross_rent": float(r["gross_rent"] or 0),
         "vacancy_loss": float(r["vacancy_loss"] or 0),
         "noi": float(r["noi"] or 0)}
        for r in rows
    ]
    artifact = {
        "kind": "table",
        "title": f"T12 — {prop['name']}",
        "subtitle": normalized["period"],
        "columns": ["month", "gross_rent", "vacancy_loss", "noi"],
        "rows": chart_rows,
        "summary": normalized,
    }
    return "__ARTIFACT__" + json.dumps(artifact)


normalize_t12 = StructuredTool.from_function(
    func=_normalize_t12,
    name="normalize_t12",
    description="Normalize a property's trailing twelve months (T12) into a single-page rollup (GPR, vacancy, EGI, opex by category, NOI, margin). Emits a monthly table artifact.",
    args_schema=PropSlugArgs,
)


class ProFormaArgs(BaseModel):
    slug_or_id: str = Field(description="Property slug or id.")
    hold_years: int = Field(default=5, ge=1, le=15)
    rent_growth_pct: float = Field(default=3.0, description="Annual rent growth %")
    expense_growth_pct: float = Field(default=2.5, description="Annual opex growth %")
    vacancy_pct: float = Field(default=6.0, description="Underwritten vacancy %")
    exit_cap_pct: float = Field(default=6.0, description="Exit cap rate %")
    purchase_price: Optional[float] = Field(default=None, description="If not provided, uses asking_price.")
    capex_reserve_psf: float = Field(default=0.25)
    selling_costs_pct: float = Field(default=2.0)


def _build_pro_forma(**kw) -> str:
    args = ProFormaArgs(**kw)
    pid = _resolve_pid(args.slug_or_id)
    if not pid:
        return "Property not found."
    prop = fetch_one("SELECT * FROM bricksmith.properties WHERE id = %s", (pid,))
    price = args.purchase_price or float(prop["asking_price"] or 0)
    if price <= 0:
        return "No purchase price available — pass `purchase_price`."

    # Year-0 NOI from T12
    t12 = fetch_all("SELECT noi FROM bricksmith.t12_statements WHERE property_id = %s", (pid,))
    noi0 = sum(float(r["noi"] or 0) for r in t12)
    if noi0 <= 0:
        # fallback from rent roll
        rr = fetch_one("SELECT units FROM bricksmith.rent_rolls WHERE property_id = %s ORDER BY as_of_date DESC LIMIT 1", (pid,))
        rent_monthly = sum((u.get("rent") or 0) for u in (rr["units"] if rr else []))
        noi0 = rent_monthly * 12 * 0.6  # rough

    sqft = int(prop["sqft"] or 0)
    projections = []
    cum = 0.0
    for y in range(1, args.hold_years + 1):
        revenue = noi0 * ((1 + args.rent_growth_pct / 100) ** y) / 0.95  # reverse out vacancy
        vacancy = revenue * (args.vacancy_pct / 100)
        opex = (noi0 / 0.58) * ((1 + args.expense_growth_pct / 100) ** y) - noi0  # rough opex starting at ~42%
        opex = max(opex, revenue * 0.35)
        noi = revenue - vacancy - opex
        capex = sqft * args.capex_reserve_psf if sqft else 0
        cf = noi - capex
        cum += cf
        projections.append({
            "year": y,
            "revenue": round(revenue, 2),
            "vacancy_loss": round(vacancy, 2),
            "opex": round(opex, 2),
            "noi": round(noi, 2),
            "capex": round(capex, 2),
            "cash_flow": round(cf, 2),
        })

    exit_noi = projections[-1]["noi"] * (1 + args.rent_growth_pct / 100)
    sale_price = exit_noi / (args.exit_cap_pct / 100)
    selling_costs = sale_price * (args.selling_costs_pct / 100)
    net_sale = sale_price - selling_costs

    # Returns: unlevered IRR on cash flows + net sale
    cash_flows = [-price] + [p["cash_flow"] for p in projections]
    cash_flows[-1] += net_sale
    irr = _irr(cash_flows)
    moic = (sum(cash_flows[1:])) / price
    avg_coc = sum(p["cash_flow"] for p in projections) / (args.hold_years * price)

    assumptions = {
        "hold_years": args.hold_years,
        "purchase_price": price,
        "rent_growth_pct": args.rent_growth_pct,
        "expense_growth_pct": args.expense_growth_pct,
        "vacancy_pct": args.vacancy_pct,
        "exit_cap_pct": args.exit_cap_pct,
        "capex_reserve_psf": args.capex_reserve_psf,
    }
    returns = {
        "unlevered_irr_pct": round(irr * 100, 2) if irr is not None else None,
        "avg_coc_pct": round(avg_coc * 100, 2),
        "moic": round(moic, 2),
        "exit_value": round(net_sale, 2),
        "exit_noi": round(exit_noi, 2),
    }

    # Persist
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO bricksmith.pro_formas (property_id, name, assumptions, projections, returns) "
            "VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb) RETURNING id",
            (pid, f"{prop['name']} — base case", json.dumps(assumptions),
             json.dumps(projections), json.dumps(returns)),
        )
        conn.commit()

    artifact = {
        "kind": "table",
        "title": f"Pro forma — {prop['name']}",
        "subtitle": f"{args.hold_years}-year base case · unlevered IRR {returns['unlevered_irr_pct']}%",
        "columns": ["year", "revenue", "vacancy_loss", "opex", "noi", "capex", "cash_flow"],
        "rows": projections,
        "summary": {"assumptions": assumptions, "returns": returns,
                    "purchase_price": price, "exit_value": returns["exit_value"]},
    }
    return "__ARTIFACT__" + json.dumps(artifact)


def _irr(cash_flows: list[float]) -> Optional[float]:
    # Newton-Raphson with bisection fallback
    def npv(r):
        return sum(cf / ((1 + r) ** i) for i, cf in enumerate(cash_flows))
    low, high = -0.95, 10.0
    if npv(low) * npv(high) > 0:
        return None
    for _ in range(80):
        mid = (low + high) / 2
        v = npv(mid)
        if abs(v) < 1:
            return mid
        if npv(low) * v < 0:
            high = mid
        else:
            low = mid
    return mid


build_pro_forma = StructuredTool.from_function(
    func=_build_pro_forma,
    name="build_pro_forma",
    description="Build a multi-year pro forma for a property with rent growth, vacancy, opex inflation, exit cap. Persists to bricksmith.pro_formas and returns the schedule + returns.",
    args_schema=ProFormaArgs,
)


class DebtArgs(BaseModel):
    slug_or_id: str
    purchase_price: Optional[float] = Field(default=None)
    ltv_pct: float = Field(default=65.0)
    rate_pct: float = Field(default=6.75)
    amort_years: int = Field(default=30)
    term_years: int = Field(default=10)
    io_years: int = Field(default=2)
    target_dscr: float = Field(default=1.30)


def _size_debt(**kw) -> str:
    args = DebtArgs(**kw)
    pid = _resolve_pid(args.slug_or_id)
    if not pid:
        return "Property not found."
    prop = fetch_one("SELECT name, asking_price FROM bricksmith.properties WHERE id = %s", (pid,))
    price = args.purchase_price or float(prop["asking_price"] or 0)
    if price <= 0:
        return "No price available."

    t12_noi = sum(float(r["noi"] or 0) for r in fetch_all(
        "SELECT noi FROM bricksmith.t12_statements WHERE property_id = %s", (pid,)))

    max_ltv_loan = price * args.ltv_pct / 100
    # DSCR-constrained sizing — cap-rate-implied debt service
    monthly_rate = (args.rate_pct / 100) / 12
    n = args.amort_years * 12
    # payment on $1 to compute max loan
    payment_per_dollar = monthly_rate / (1 - (1 + monthly_rate) ** -n) if monthly_rate else 1 / n
    dscr_constrained_loan = (t12_noi / args.target_dscr) / (payment_per_dollar * 12)
    loan = min(max_ltv_loan, dscr_constrained_loan)

    annual_ds = loan * payment_per_dollar * 12
    dscr = t12_noi / annual_ds if annual_ds else None
    ltv = loan / price

    tranches = [{
        "name": "Senior Agency",
        "lender": "Fannie/Freddie small-balance",
        "amount": round(loan, 2),
        "rate_pct": args.rate_pct,
        "amort_years": args.amort_years,
        "term_years": args.term_years,
        "io_years": args.io_years,
        "type": "mortgage",
    }]

    result = {
        "property": prop["name"],
        "purchase_price": price,
        "loan_amount": round(loan, 2),
        "ltv_pct": round(ltv * 100, 2),
        "annual_debt_service": round(annual_ds, 2),
        "dscr": round(dscr, 2) if dscr else None,
        "constraint_binding": "LTV" if max_ltv_loan < dscr_constrained_loan else "DSCR",
        "tranches": tranches,
    }

    # Persist
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO bricksmith.debt_stacks (property_id, name, tranches, ltv, dscr) "
            "VALUES (%s, %s, %s::jsonb, %s, %s)",
            (pid, "Senior-only", json.dumps(tranches), ltv * 100, dscr),
        )
        conn.commit()
    return "__ARTIFACT__" + json.dumps({
        "kind": "table",
        "title": f"Debt stack — {prop['name']}",
        "subtitle": f"{result['ltv_pct']}% LTV · {result['dscr']}x DSCR · binding: {result['constraint_binding']}",
        "columns": ["name", "lender", "amount", "rate_pct", "amort_years", "term_years", "io_years"],
        "rows": tranches,
        "summary": result,
    })


size_debt = StructuredTool.from_function(
    func=_size_debt,
    name="size_debt",
    description="Size a senior mortgage against a property's T12 NOI, given an LTV target and a DSCR target. Returns whichever is binding.",
    args_schema=DebtArgs,
)


class ReturnsArgs(BaseModel):
    slug_or_id: str
    pro_forma_id: Optional[int] = Field(default=None, description="Specific pro forma id; if None uses most recent.")


def _compute_returns(**kw) -> str:
    args = ReturnsArgs(**kw)
    pid = _resolve_pid(args.slug_or_id)
    if not pid:
        return "Property not found."
    if args.pro_forma_id:
        pf = fetch_one("SELECT * FROM bricksmith.pro_formas WHERE id = %s AND property_id = %s",
                       (args.pro_forma_id, pid))
    else:
        pf = fetch_one("SELECT * FROM bricksmith.pro_formas WHERE property_id = %s "
                       "ORDER BY id DESC LIMIT 1", (pid,))
    if not pf:
        return "No pro forma for this property — call build_pro_forma first."
    return json.dumps(pf["returns"])


compute_returns = StructuredTool.from_function(
    func=_compute_returns,
    name="compute_returns",
    description="Return IRR/CoC/MOIC for the most recent pro forma of a property (or a specific pro_forma_id).",
    args_schema=ReturnsArgs,
)
