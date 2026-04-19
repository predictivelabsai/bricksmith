"""DD document bodies (zoning, environmental, property condition, title, market)
for RAG indexing.
"""

from __future__ import annotations

import random
from datetime import date


def zoning_memo(prop: dict, rng: random.Random) -> str:
    asset = prop["asset_type"]
    zoning_code = {
        "multifamily": rng.choice(["R-4", "MR-3", "RM-25", "RMF-30"]),
        "office":      rng.choice(["CBD-1", "MU-3", "DMU", "O-2"]),
        "industrial":  rng.choice(["I-1", "IL", "M-1", "LI"]),
        "retail":      rng.choice(["C-2", "CM", "NC-3", "CB"]),
    }[asset]
    far = round(rng.uniform(0.5, 5.0), 1)
    height_limit = rng.choice([45, 65, 85, 125, 250, 400])
    nonconforming = rng.random() < 0.3

    return f"""# Zoning Memorandum — {prop['name']}

**Subject Property:** {prop['address']}, {prop['city']}, {prop['state']}
**Prepared:** {date.today().isoformat()}

## Current Zoning
The Subject Property is zoned **{zoning_code}**, which permits {asset} use as of right. Accessory uses customary to {asset} properties are also permitted. Residential density cap: {rng.choice(['30 du/ac', '45 du/ac', '60 du/ac', 'n/a'])}. Floor Area Ratio (FAR) limit: {far}. Height limit: {height_limit}'.

## Conformance
{"The existing improvements do not fully conform to current zoning setbacks (side yard deficiency of approximately 3 feet). This condition is grandfathered as legal nonconforming; however, any reconstruction exceeding 50% of the assessed value would require a variance." if nonconforming else "The existing improvements are fully conforming to current zoning requirements, including setbacks, FAR, height, and parking."}

## Permitted Uses
Permitted uses under {zoning_code} include: {asset} as primary use; ancillary office; {rng.choice(['retail', 'personal service', 'professional office', 'day-care (<60 children)', 'restaurant (< 100 seats)'])} as accessory up to 15% of gross floor area.

## Parking Requirements
Current ordinance requires {rng.choice(['1 space per 1,000 sqft', '1 space per 300 sqft', '2 spaces per unit', '1.5 spaces per unit'])}. The Subject Property provides {rng.randint(50, 450)} parking stalls, which is {rng.choice(['compliant with', 'in excess of', 'deficient by approximately 8% from'])} the required count.

## Overlay Districts
{"The Subject falls within the {} overlay district, which imposes additional design review for any exterior modifications visible from the public right-of-way.".format(rng.choice(["Historic Preservation", "Corridor", "Transit-Oriented Development", "Design Review"])) if rng.random() < 0.4 else "The Subject Property is not within any overlay district."}

## Recommendations
- Obtain a zoning verification letter from the Department of Planning prior to closing.
- Confirm parking compliance with on-site survey.
- Review latest Code Enforcement violations: none open as of last search.
"""


def environmental_phase1(prop: dict, rng: random.Random) -> str:
    has_rec = rng.random() < 0.25
    adjacent_concern = rng.random() < 0.4
    return f"""# Phase I Environmental Site Assessment — {prop['name']}

**Property:** {prop['address']}, {prop['city']}, {prop['state']}
**Assessment Date:** {date.today().isoformat()}
**Consultant:** Granite Environmental Group

## Scope
This Phase I ESA was conducted in general accordance with ASTM E1527-21 to identify potential Recognized Environmental Conditions (RECs) at the Subject Property.

## Records Review
- EDR regulatory database review: {rng.choice(['no listings of concern', 'prior UST listing closed 2008', 'no listings of concern'])}.
- Historical aerial photographs (1950-2024): {"site was previously agricultural through 1978; developed for current use {}.".format(rng.choice(['1985', '1992', '1998', '2003', '2012']))}
- Sanborn fire insurance maps: no indication of historical industrial or commercial chemical use on-site.
- State Department of Environmental Quality database: clean.

## Site Reconnaissance
On-site reconnaissance observed {"stained pavement in the loading dock area, likely associated with ordinary parking lot staining" if rng.random() < 0.3 else "no visible staining, spills, or evidence of environmental concern"}. Above-ground storage tanks: {rng.choice(['none observed', 'one 275-gal fuel oil tank, empty and decommissioned'])}. Underground storage tanks: none observed.

## Adjacent Properties
{"A former dry cleaner operated two parcels east of the Subject from 1982-2004. State records indicate closure with no further action after soil vapor sampling confirmed no off-site migration. Nonetheless, given the proximity, a vapor intrusion screening evaluation is recommended as a de minimis follow-up." if adjacent_concern else "Adjacent properties consist of compatible uses with no indication of potential off-site impact."}

## Findings
{"**Recognized Environmental Conditions:** The historical presence of the former dry cleaner adjacent to the Subject constitutes a Controlled Recognized Environmental Condition (CREC) warranting further inquiry before final underwriting." if has_rec else "**No Recognized Environmental Conditions (RECs) were identified.** "}
{"Minor de minimis conditions noted in Section 3 are not considered RECs." if not has_rec else ""}

## Opinion & Recommendations
{"Recommend a Phase II ESA limited to sub-slab vapor sampling along the eastern property line to confirm no vapor intrusion pathway. Estimated cost: $18,000-$28,000." if has_rec or adjacent_concern else "No further environmental investigation is warranted based on the findings of this Phase I ESA."}
"""


def property_condition_report(prop: dict, rng: random.Random) -> str:
    age = date.today().year - prop["year_built"]
    roof_age = rng.randint(1, 22)
    hvac_age = rng.randint(3, 18)
    return f"""# Property Condition Report — {prop['name']}

**Property:** {prop['address']}, {prop['city']}, {prop['state']}
**Inspection Date:** {date.today().isoformat()}
**Reviewer:** Cornerstone Building Diagnostics

## Executive Summary
The Subject Property was constructed in {prop['year_built']} ({age} years of age) and is in {rng.choice(['average', 'above average', 'average to above average', 'good'])} condition overall. Observed deferred maintenance is estimated at approximately ${rng.randint(120, 1800)}k, concentrated in roof and HVAC systems.

## Roof
The built-up modified bitumen roof is approximately {roof_age} years into an estimated 25-year service life. {"Multiple patches and ponding were observed, suggesting approaching end-of-life. Full tear-off and replacement recommended within 3 years." if roof_age > 18 else "General condition is serviceable, with routine sealant maintenance recommended."}

## HVAC
Roof-top package units (n={rng.randint(4, 18)}) are approximately {hvac_age} years into a 15-20 year service life. {"Recommend replacement budget of ${amt}k over the next 24 months.".format(amt=rng.randint(120, 420)) if hvac_age > 12 else "Units are in serviceable condition; budget for routine maintenance and selective replacement of worst-performing units."}

## Structural
No evidence of foundation distress, differential settlement, or structural deficiencies was observed. Expansion joints function as intended. Concrete slab is sound with typical surface cracks consistent with age.

## Site & Parking
Parking lot pavement is in {rng.choice(['fair', 'fair to good', 'good'])} condition. Recommend full seal coat and restriping within 12 months. Drainage is adequate; no evidence of standing water beyond minor ponding near the eastern curb line.

## Life Safety
Fire suppression system last tested {date.today().year - rng.randint(0, 2)}; passing. Emergency lighting functional. ADA accessibility substantially compliant; minor path-of-travel improvements recommended at the main entrance.

## Immediate Repair Budget (Yr 1): ${rng.randint(80, 380)}k
## Short-Term Budget (Yrs 2-3): ${rng.randint(280, 720)}k
## Long-Term Capital Reserve: ${rng.randint(0, 22)}/sqft over 10-year hold
"""


def title_commitment(prop: dict, rng: random.Random) -> str:
    return f"""# Title Commitment (Schedule B-II) — {prop['name']}

**Property:** {prop['address']}, {prop['city']}, {prop['state']}
**Title Company:** First American Title Insurance Company
**Effective Date:** {date.today().isoformat()}

## Schedule B — Part II Exceptions

1. Real estate taxes and assessments, if any, for the year {date.today().year} and subsequent years, a lien not yet due and payable.

2. Easement and right-of-way granted to {rng.choice(['the electric utility', 'the municipal water authority', 'the county'])} recorded in Deed Book {rng.randint(1200, 8600)}, Page {rng.randint(1, 900)}.

3. Declaration of Covenants, Conditions and Restrictions recorded in Deed Book {rng.randint(2100, 9200)}, Page {rng.randint(1, 900)}, and any amendments thereto.

4. {"Encroachment of the Subject's eastern canopy approximately 0.6 feet over the adjacent property line as shown on survey dated {}. Resolution: executed encroachment easement to be recorded at closing.".format(date.today().isoformat()) if rng.random() < 0.3 else "No survey matters identified that affect insurability."}

5. Matters shown on plat recorded in Plat Book {rng.randint(10, 180)}, Page {rng.randint(1, 90)}, including setbacks, utility easements, and drainage easements.

6. Any rights of tenants in possession under unrecorded leases, as tenants only with no rights of purchase.

{"7. Existing deed of trust in favor of {} securing indebtedness in the original principal amount of ${}M, to be released at closing.".format(rng.choice(['Wells Fargo', 'JP Morgan Chase', 'Bank of America', 'a regional bank']), rng.randint(10, 85)) if rng.random() < 0.6 else ""}

## Requirements for Issuance of Owner's Policy
(a) Payment of all sums required to be paid.
(b) Execution and recording of the deed from Seller to Buyer.
(c) Release of any existing security instruments.
(d) Payoff of outstanding real estate taxes and assessments.
(e) Compliance with Company's underwriting requirements.
"""


def market_report(metro: str, asset: str, rng: random.Random) -> str:
    return f"""# Market Report — {metro} {asset.title()} — Q1 {date.today().year}

## Executive Summary
The {metro} {asset} market continued its {rng.choice(['gradual recovery', 'stabilization', 'modest expansion', 'rebalancing'])} in Q1. {"Fundamentals remain favorable despite near-term supply pressure." if asset != 'office' else "Office fundamentals remain challenged, with return-to-office momentum uneven across submarkets."}

## Key Metrics
- **Average Cap Rate:** {round(rng.uniform(4.4, 7.6), 2)}%
- **Vacancy:** {round(rng.uniform(3.5, 18.5), 1)}%
- **YoY Rent Growth:** {round(rng.uniform(-2, 6.5), 1)}%
- **Q1 Absorption:** {rng.randint(-250, 1400):,} units/sqft (positive = net leasing)
- **Under Construction:** {rng.randint(400, 6200):,} units/sqft

## Submarket Callouts
Top-performing submarket: **{rng.choice(['Downtown', 'Suburban North', 'Airport corridor', 'Tech corridor'])}**, with rent growth outpacing the metro by ~150 bps.

Weakest submarket: **{rng.choice(['Legacy CBD', 'Older suburban', 'Interior ring'])}**, where concessions have expanded to {rng.randint(4, 14)} weeks free on 12-month terms.

## Outlook
{rng.choice([
    "We expect a balanced market with modest rent growth over the next 12 months.",
    "Supply-constrained submarkets will continue to outperform; expect bifurcation.",
    "Cap rate stability now that rates have plateaued; limited scope for further compression without Treasury rally.",
    "Selective value-add opportunities remain in pre-2005 vintage stock, especially in {geo}.".format(geo=metro),
])}
"""


def generate_all_for_property(prop: dict, rng: random.Random) -> list[dict]:
    """Return a list of {title, doc_type, text} ready for RAG ingest."""
    return [
        {"title": f"Zoning Memo — {prop['name']}", "doc_type": "zoning", "text": zoning_memo(prop, rng)},
        {"title": f"Phase I ESA — {prop['name']}", "doc_type": "environmental", "text": environmental_phase1(prop, rng)},
        {"title": f"Property Condition Report — {prop['name']}", "doc_type": "pcr", "text": property_condition_report(prop, rng)},
        {"title": f"Title Commitment — {prop['name']}", "doc_type": "title", "text": title_commitment(prop, rng)},
    ]


def generate_market_reports(properties: list[dict], rng: random.Random) -> list[dict]:
    pairs = sorted({(p["metro"], p["asset_type"]) for p in properties})
    return [
        {
            "title": f"{metro} {asset.title()} Market Report — Q1 {date.today().year}",
            "doc_type": "market",
            "text": market_report(metro, asset, rng),
        }
        for metro, asset in pairs
    ]
