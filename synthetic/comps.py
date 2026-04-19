"""Sales + rent comps per property."""

from __future__ import annotations

import random
from datetime import date, timedelta


def _comp_name(rng: random.Random, prop: dict, suffix: str) -> str:
    names = ["Heritage", "Riverside", "Oakwood", "Crestview", "Metropolitan",
             "Legacy", "Preserve", "Grand", "Ashton", "Trailside", "Foundry", "Greenfield"]
    return f"{rng.choice(names)} {suffix}"


def generate_sales_comps(prop: dict, rng: random.Random, count: int = 6) -> list[dict]:
    rows = []
    base_ppsf = {
        "multifamily": rng.uniform(190, 330) * 1000 / rng.uniform(800, 1000),
        "office":      rng.uniform(220, 520),
        "industrial":  rng.uniform(95, 240),
        "retail":      rng.uniform(180, 420),
    }[prop["asset_type"]]

    for i in range(count):
        delta_days = rng.randint(30, 720)
        sale_date = date.today() - timedelta(days=delta_days)
        noise = rng.uniform(0.82, 1.16)
        ppsf = base_ppsf * noise
        sqft = int((prop["sqft"] or (prop["units"] or 100) * 950) * rng.uniform(0.7, 1.3))
        price = ppsf * sqft
        cap = rng.uniform(4.2, 7.8)
        rows.append({
            "comp_name": _comp_name(rng, prop, "Commons" if prop["asset_type"] != "multifamily" else "Apartments"),
            "city": prop["city"],
            "state": prop["state"],
            "asset_type": prop["asset_type"],
            "sqft": sqft,
            "units": prop["units"] and int(prop["units"] * rng.uniform(0.7, 1.3)) or None,
            "sale_date": sale_date.isoformat(),
            "sale_price": round(price, 2),
            "cap_rate": round(cap, 2),
            "price_per_unit": round(price / max(1, prop["units"] or 1), 2) if prop["units"] else None,
            "price_per_sqft": round(ppsf, 2),
            "source": rng.choice(["CoStar", "RCA", "Broker BOV", "Public records"]),
        })
    return rows


def generate_rent_comps(prop: dict, rng: random.Random, count: int = 6) -> list[dict]:
    rows = []
    if prop["asset_type"] == "multifamily":
        types = [("1BR", (720, 820), (1400, 2200)), ("2BR", (1050, 1200), (1950, 3000))]
    elif prop["asset_type"] == "office":
        types = [("full floor", (20000, 35000), None), ("suite", (3000, 9000), None)]
    elif prop["asset_type"] == "industrial":
        types = [("warehouse", (60000, 200000), None)]
    else:
        types = [("inline", (1500, 4500), None), ("anchor", (35000, 55000), None)]

    base_psf = {"office": 40.0, "industrial": 10.0, "retail": 32.0}.get(prop["asset_type"])

    for i in range(count):
        t = rng.choice(types)
        unit_type, sqft_rng, rent_rng = t
        sqft = rng.randint(*sqft_rng)
        if rent_rng:
            rent = rng.randint(*rent_rng)
            rent_psf = round(rent * 12 / sqft, 2)
        else:
            psf = base_psf * rng.uniform(0.8, 1.22)
            rent = int(sqft * psf / 12)
            rent_psf = round(psf, 2)
        rows.append({
            "comp_name": _comp_name(rng, prop, "Plaza"),
            "unit_type": unit_type,
            "sqft": sqft,
            "rent": rent,
            "rent_per_sqft": rent_psf,
            "effective_date": (date.today() - timedelta(days=rng.randint(15, 240))).isoformat(),
            "source": rng.choice(["Broker survey", "CoStar", "LoopNet", "CompStak"]),
        })
    return rows
