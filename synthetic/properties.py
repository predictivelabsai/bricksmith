"""Synthetic CRE property catalog — 40 properties across 4 asset types + 8 metros.

Deterministic given the seed. Returns a list of dicts ready for bulk insert
into bricksmith.properties.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

METROS = [
    ("Austin", "TX", ["Downtown", "East Austin", "South Lamar", "North Austin", "Domain"]),
    ("Phoenix", "AZ", ["Central", "Scottsdale", "Tempe", "North Phoenix", "Chandler"]),
    ("Nashville", "TN", ["Downtown", "Midtown", "Germantown", "SoBro", "West End"]),
    ("Raleigh", "NC", ["Downtown", "North Hills", "RTP", "Cary", "Brier Creek"]),
    ("Atlanta", "GA", ["Midtown", "Buckhead", "Alpharetta", "West Midtown", "Sandy Springs"]),
    ("Denver", "CO", ["LoDo", "RiNo", "Cherry Creek", "DTC", "Boulder"]),
    ("Dallas", "TX", ["Uptown", "Frisco", "Plano", "Deep Ellum", "Las Colinas"]),
    ("Tampa", "FL", ["Downtown", "Westshore", "Channelside", "St. Pete", "Brandon"]),
]

ASSET_MIX = [
    # (asset_type, count_target, unit_range, sqft_range, unit_sqft_range)
    ("multifamily", 15, (60, 320),  None, (650, 1200)),
    ("office",      10, None,       (35000, 420000), None),
    ("industrial",  10, None,       (50000, 600000), None),
    ("retail",       5, None,       (12000, 180000), None),
]

SELLER_INTENT = ["cold", "cold", "warm", "warm", "hot"]
LISTING_STATUS = ["on_market", "on_market", "off_market", "off_market", "closed"]

MF_NAMES = ["Vista", "The", "Arden", "Parc", "Alto", "Ridge", "Aviator", "Haven", "Enclave at",
            "Residences at", "The Graham", "Maple", "Silver Spring", "Lumen", "Parkline"]
OFFICE_NAMES = ["Plaza", "Tower", "Commons", "Center", "Exchange", "Building", "Hub", "Works",
                "Corporate Center", "Summit"]
IND_NAMES = ["Logistics Park", "Distribution Center", "Commerce Center", "Industrial",
             "Freight Hub", "Last-Mile", "Fulfillment", "Crossdock", "Cold Storage", "Flex"]
RETAIL_NAMES = ["Shops at", "Market at", "Village", "Crossing", "Shoppes"]

STREETS = ["Main", "Oak", "Maple", "Cedar", "Lamar", "Congress", "Camelback", "Pine", "Commerce",
           "Industrial", "Trade", "Park", "River", "Mission", "Bluff", "Summit", "Galleria", "Gateway"]


@dataclass
class PropertySpec:
    slug: str
    name: str
    address: str
    city: str
    state: str
    zip: str
    metro: str
    asset_type: str
    submarket: str
    units: int | None
    year_built: int
    year_renovated: int | None
    sqft: int | None
    land_sqft: int | None
    occupancy_pct: float
    asking_price: float | None
    description: str
    listing_status: str
    seller_intent: str


def _name_for(asset_type: str, rng: random.Random, submarket: str) -> str:
    if asset_type == "multifamily":
        base = rng.choice(MF_NAMES)
        return f"{base} {submarket}" if base.endswith(("at", "The")) else f"{base} {submarket}"
    if asset_type == "office":
        n = rng.choice(OFFICE_NAMES)
        return f"{submarket} {n}"
    if asset_type == "industrial":
        n = rng.choice(IND_NAMES)
        return f"{submarket} {n}"
    # retail
    n = rng.choice(RETAIL_NAMES)
    return f"{n} {submarket}"


def generate(seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    specs: list[PropertySpec] = []

    slug_counter: dict[str, int] = {}

    def next_slug(base: str) -> str:
        slug_counter[base] = slug_counter.get(base, 0) + 1
        n = slug_counter[base]
        return base if n == 1 else f"{base}-{n}"

    for asset_type, count, unit_range, sqft_range, unit_sqft_range in ASSET_MIX:
        for _ in range(count):
            city, state, submarkets = rng.choice(METROS)
            submarket = rng.choice(submarkets)
            name = _name_for(asset_type, rng, submarket)
            street_num = rng.randrange(100, 9900)
            street = rng.choice(STREETS)
            suffix = rng.choice(["St", "Ave", "Blvd", "Rd", "Pkwy", "Dr"])
            address = f"{street_num} {street} {suffix}"

            year_built = rng.randint(1978, 2023)
            year_renov = rng.choice([None, None, year_built + rng.randint(8, 30)])
            if year_renov and year_renov > 2025:
                year_renov = None

            if unit_range:
                units = rng.randint(*unit_range)
                avg_unit_sqft = rng.randint(*(unit_sqft_range or (700, 1100)))
                sqft = units * avg_unit_sqft
            else:
                units = None
                sqft = rng.randint(*sqft_range) if sqft_range else None

            land_sqft = int((sqft or 50000) * rng.uniform(1.2, 3.5)) if asset_type != "office" else None
            occupancy = round(rng.uniform(0.78, 0.97) * 100, 1)

            status = rng.choice(LISTING_STATUS)
            intent = rng.choice(SELLER_INTENT)

            if asset_type == "multifamily":
                ppu = rng.randint(180_000, 320_000)
                price = ppu * units
                descr = (
                    f"{units}-unit garden-style community in {submarket}, {city}. "
                    f"Built {year_built}"
                    + (f", renovated {year_renov}. " if year_renov else ". ")
                    + f"Current occupancy {occupancy:.1f}%."
                )
            elif asset_type == "office":
                pppsf = rng.randint(220, 550)
                price = pppsf * sqft
                cls = rng.choice(["Class A", "Class B+", "Class B"])
                descr = (
                    f"{cls} office tower in {submarket}, {city}. "
                    f"{sqft:,} sqft across {rng.randint(4, 24)} floors. Built {year_built}. "
                    f"Major tenants include a mix of tech and professional services."
                )
            elif asset_type == "industrial":
                pppsf = rng.randint(95, 240)
                price = pppsf * sqft
                clear = rng.choice([24, 28, 32, 36, 40])
                descr = (
                    f"Modern distribution facility in {submarket}, {city}. "
                    f"{sqft:,} sqft with {clear}' clear height, "
                    f"{rng.randint(20, 120)} dock doors, cross-dock configuration. Built {year_built}."
                )
            else:  # retail
                pppsf = rng.randint(180, 420)
                price = pppsf * sqft
                descr = (
                    f"Grocery-anchored neighborhood center in {submarket}, {city}. "
                    f"{sqft:,} sqft GLA across multiple parcels. Built {year_built}."
                )

            if status == "closed":
                asking_price = None
            else:
                asking_price = float(price)

            slug_base = (name + " " + city).lower().replace(" ", "-").replace(",", "").replace("'", "")
            slug_base = "".join(c for c in slug_base if c.isalnum() or c == "-")
            slug = next_slug(slug_base[:50])

            specs.append(PropertySpec(
                slug=slug,
                name=name,
                address=address,
                city=city,
                state=state,
                zip=f"{rng.randint(10000, 99999)}",
                metro=city,
                asset_type=asset_type,
                submarket=submarket,
                units=units,
                year_built=year_built,
                year_renovated=year_renov,
                sqft=sqft,
                land_sqft=land_sqft,
                occupancy_pct=occupancy,
                asking_price=asking_price,
                description=descr,
                listing_status=status,
                seller_intent=intent,
            ))

    return [s.__dict__ for s in specs]
