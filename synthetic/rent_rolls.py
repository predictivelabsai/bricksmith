"""Per-property rent rolls — realistic unit mixes, vacancies, lease dates."""

from __future__ import annotations

import random
from datetime import date, timedelta

MF_UNIT_MIX = [
    ("studio", (450, 620), (1100, 1750)),
    ("1BR/1BA", (620, 820), (1350, 2250)),
    ("2BR/2BA", (880, 1150), (1850, 3100)),
    ("3BR/2BA", (1150, 1450), (2450, 3950)),
]

INDUSTRIAL_TYPES = [
    ("bulk warehouse", (80000, 250000)),
    ("flex/light industrial", (10000, 35000)),
    ("cold storage bay", (20000, 60000)),
    ("last-mile", (25000, 80000)),
]

OFFICE_TYPES = [
    ("full floor", (18000, 35000)),
    ("multi-tenant suite", (2200, 12000)),
    ("ground-floor retail", (1800, 6000)),
]

RETAIL_TYPES = [
    ("anchor grocery", (35000, 55000)),
    ("junior anchor", (12000, 28000)),
    ("inline", (1200, 4500)),
    ("pad site", (2500, 7000)),
]

TENANT_FIRSTS = ["Acme", "Pacific", "Lone Star", "Southern", "Evergreen", "Vanguard", "Summit",
                 "Prime", "Sable", "Northstar", "Delta", "Apex", "Kinetic", "Granite", "Harbor"]
TENANT_LASTS = ["Logistics", "Health", "Capital", "Foods", "Systems", "Media", "Studios",
                "Partners", "Fitness", "Outfitters", "Dynamics", "Technologies", "Insurance",
                "Brewing", "Retail"]


def _tenant(rng: random.Random) -> str:
    return f"{rng.choice(TENANT_FIRSTS)} {rng.choice(TENANT_LASTS)}"


def _pick(rng: random.Random, options):
    weights = [max(1, 10 - i * 2) for i in range(len(options))]
    return rng.choices(options, weights=weights, k=1)[0]


def generate_for_property(prop: dict, as_of: date, rng: random.Random) -> list[dict]:
    units: list[dict] = []
    asset = prop["asset_type"]
    occ_pct = (prop["occupancy_pct"] or 92) / 100

    if asset == "multifamily":
        total = prop["units"] or 100
        # distribute across mix with weights biased to 1BR/2BR
        weights = [1, 5, 5, 2]
        mix_counts = [0] * len(MF_UNIT_MIX)
        for _ in range(total):
            idx = rng.choices(range(len(MF_UNIT_MIX)), weights=weights)[0]
            mix_counts[idx] += 1
        occupied_target = int(total * occ_pct)
        occ_flags = [True] * occupied_target + [False] * (total - occupied_target)
        rng.shuffle(occ_flags)

        n = 0
        for (type_name, sqft_rng, rent_rng), count in zip(MF_UNIT_MIX, mix_counts):
            for i in range(count):
                n += 1
                occupied = occ_flags[n - 1]
                sqft = rng.randint(*sqft_rng)
                rent = rng.randint(*rent_rng)
                if occupied:
                    lease_start = as_of - timedelta(days=rng.randint(45, 720))
                    lease_end = lease_start + timedelta(days=rng.choice([365, 365 + 90, 730]))
                    tenant = f"Resident {prop['slug'][:6]}-{n:03d}"
                    status = "active"
                else:
                    lease_start = lease_end = None
                    tenant = None
                    status = "vacant"
                units.append({
                    "unit": f"{(n // 100) + 1}{n % 100:02d}",
                    "type": type_name,
                    "sqft": sqft,
                    "tenant": tenant,
                    "rent": rent,
                    "lease_start": lease_start.isoformat() if lease_start else None,
                    "lease_end":   lease_end.isoformat()   if lease_end   else None,
                    "status": status,
                })
        return units

    # Commercial rent rolls — fewer, larger tenants
    total_sqft = prop["sqft"] or 100_000
    leased_sqft_target = int(total_sqft * occ_pct)
    if asset == "industrial":
        types = INDUSTRIAL_TYPES
    elif asset == "office":
        types = OFFICE_TYPES
    else:
        types = RETAIL_TYPES

    leased = 0
    suite = 100
    while leased < leased_sqft_target:
        type_name, sqft_rng = _pick(rng, types)
        sqft = rng.randint(*sqft_rng)
        sqft = min(sqft, leased_sqft_target - leased)
        if sqft < 800:
            break
        rent_psf = {
            "industrial": rng.uniform(7.5, 14.0),
            "office":     rng.uniform(24.0, 65.0),
            "retail":     rng.uniform(18.0, 58.0),
        }[asset]
        rent = int(sqft * rent_psf)
        start = date(as_of.year - rng.randint(0, 4), rng.randint(1, 12), 1)
        term_years = rng.choice([3, 5, 5, 7, 10])
        end = date(start.year + term_years, start.month, 1)
        units.append({
            "unit": f"Suite {suite}",
            "type": type_name,
            "sqft": sqft,
            "tenant": _tenant(rng),
            "rent": rent,
            "rent_psf": round(rent_psf, 2),
            "lease_start": start.isoformat(),
            "lease_end":   end.isoformat(),
            "status": "active",
        })
        suite += 10
        leased += sqft

    # add vacant suites to hit total
    vacant = total_sqft - leased
    if vacant > 2000:
        units.append({
            "unit": f"Suite {suite}",
            "type": "vacant",
            "sqft": vacant,
            "tenant": None,
            "rent": 0,
            "lease_start": None,
            "lease_end":   None,
            "status": "vacant",
        })
    return units
