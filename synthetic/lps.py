"""Synthetic LP / investor CRM — 60 contacts."""

from __future__ import annotations

import random
from datetime import date, timedelta

FIRST_NAMES = ["Priya", "Marcus", "Sarah", "Daniel", "Aisha", "Jon", "Elena", "Hiroshi",
               "Fiona", "Rashid", "Margaux", "Theo", "Olivia", "Kenji", "Ines", "Tomas",
               "Amara", "Levi", "Noor", "Ida", "Caleb", "Yuki", "Lior", "Petra", "Sebastian"]
LAST_NAMES = ["Chen", "Patel", "Rodriguez", "Sanchez", "Müller", "Okafor", "Bergström",
              "Khan", "Kovač", "Hassan", "Nakamura", "Levine", "Ferreira", "Dubois",
              "Kwon", "Alvarez", "Weinstein", "Reinhardt", "Park"]
FIRMS = ["Cascade Family Office", "Vanguard Partners", "Polaris Capital",
         "Evergreen RE Fund", "Titan Bridge Capital", "Fairhaven Real Estate",
         "Orion Global Partners", "Thornfield Wealth", "Sable Peak Ventures",
         "Horizon Crossing", "Meridian Holdings", "Grayson Family Trust",
         "Redbud Capital", "Castle Pines Advisors", "Haverford Group",
         "Silvercloud Endowment", "Cornerstone Foundation", "Longleaf Capital"]
STAGES = ["cold", "qualified", "meeting", "committed", "closed", "passed"]
FOCI = ["multifamily", "industrial", "mixed", "office", "retail"]
GEOS = ["Sun Belt", "Texas Triangle", "Rockies", "Southeast", "National", "Mountain West"]


def generate(count: int = 60, seed: int = 42) -> list[dict]:
    rng = random.Random(seed + 11)
    rows: list[dict] = []
    for i in range(count):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        firm = rng.choice(FIRMS)
        stage = rng.choices(STAGES, weights=[8, 5, 4, 3, 2, 3])[0]
        check = rng.choice([250_000, 500_000, 1_000_000, 2_500_000, 5_000_000, 10_000_000])
        focus = rng.choice(FOCI)
        geo = rng.choice(GEOS)
        last_touch = (date.today() - timedelta(days=rng.randint(3, 180))).isoformat()
        notes_pool = [
            f"Prefers deals sub-$50M, {focus} focus, {geo}. Values monthly distributions.",
            f"Looking for value-add {focus}. Introduced by {rng.choice(['ULI', 'warm intro', 'Selects'])}.",
            "Tax-advantaged investor, 1031 exchange capacity this Q.",
            f"Closed last deal with us at {rng.randint(14, 22)}% IRR; repeat LP.",
            "Requests detailed sensitivity analysis before commitment.",
            f"Allocates quarterly; next review {rng.choice(['June','August','November'])}.",
        ]
        rows.append({
            "name": f"{first} {last}",
            "firm": firm,
            "email": f"{first.lower()}.{last.lower().replace(' ', '')}@{firm.split()[0].lower()}.com",
            "check_size": check,
            "stage": stage,
            "focus": focus,
            "geography": geo,
            "last_touch": last_touch,
            "notes": rng.choice(notes_pool),
        })
    return rows
