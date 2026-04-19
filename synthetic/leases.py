"""Generate full lease bodies (markdown) for RAG indexing.

Output format per lease: (document_metadata, body_text). Each body includes
realistic boilerplate (premises, term, rent, escalations, force majeure,
assignment, surrender) mixed with property-specific details.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

FORCE_MAJEURE = """
**Force Majeure.** Neither party shall be liable for any failure or delay in performance under this Lease (other than the payment of Rent) to the extent that such failure is caused by acts of God, war, acts of terrorism, riots, civil disturbance, strikes, lockouts, labor disputes, governmental action, pandemic, epidemic, quarantine, or other causes beyond the reasonable control of the party affected, provided that the affected party gives prompt written notice to the other party.
"""

ASSIGNMENT_RETAIL = """
**Assignment and Subletting.** Tenant shall not assign this Lease nor sublet the Premises in whole or in part without the prior written consent of Landlord, which consent shall not be unreasonably withheld, conditioned, or delayed. Any proposed assignee must demonstrate a tangible net worth at least equal to Tenant's net worth at the time this Lease was executed, and must operate under a permitted use substantially similar to Tenant's.
"""

CAM_RETAIL = """
**Common Area Maintenance.** Tenant shall pay its Pro Rata Share of Common Area Maintenance expenses, including but not limited to: landscaping, parking lot maintenance and resurfacing, exterior lighting, trash removal, snow removal where applicable, and property management fees not to exceed 4% of gross CAM charges. Landlord shall provide annual reconciliation within one hundred twenty (120) days of calendar year end.
"""

NNN_INDUSTRIAL = """
**Triple Net Expenses.** This is a triple-net Lease. Tenant shall be responsible for all Real Estate Taxes, Insurance, and Common Area Maintenance attributable to the Premises, payable monthly in equal installments based on Landlord's reasonable estimate, with annual reconciliation.
"""

OPTIONS = """
**Option to Renew.** Provided Tenant is not in default, Tenant shall have the option to extend the Term for {n} additional period(s) of {y} years each, exercisable by written notice delivered not less than nine (9) months prior to the then-current expiration. Rent during any renewal term shall be the greater of (i) fair market rent as determined by a qualified third-party appraiser, or (ii) 103% of the Rent payable in the final month of the preceding term.
"""

SURRENDER = """
**Surrender of Premises.** Upon expiration or earlier termination of this Lease, Tenant shall surrender the Premises to Landlord in broom-clean condition, free of all personal property of Tenant, reasonable wear and tear and casualty damage excepted. Any trade fixtures installed by Tenant shall be removed at Tenant's expense, and Tenant shall repair any damage caused by such removal.
"""

HAZARDOUS_CLAUSE = """
**Hazardous Materials.** Tenant shall not use, generate, store, release, or dispose of any Hazardous Materials on the Premises except for de minimis quantities of office or cleaning supplies customarily used in the ordinary course of Tenant's permitted use. Tenant's indemnity under this Section shall survive the expiration or earlier termination of the Lease.
"""


def _industrial_use(tenant: str) -> str:
    return f"distribution, warehousing, fulfillment, and light assembly operations for {tenant}, including ancillary office support"


def _office_use(tenant: str) -> str:
    return f"general office use for {tenant} and its affiliates, including meeting space, research and development, and customer demonstrations"


def _retail_use(tenant: str) -> str:
    return f"retail sale of goods and services by {tenant}, including ancillary storage and administrative functions"


def generate_lease_body(*, prop: dict, unit: dict, rng: random.Random) -> str:
    asset = prop["asset_type"]
    tenant = unit.get("tenant") or "Tenant Placeholder, LLC"
    commence = date.fromisoformat(unit["lease_start"]) if unit.get("lease_start") else date.today() - timedelta(days=rng.randint(60, 365))
    expire = date.fromisoformat(unit["lease_end"]) if unit.get("lease_end") else commence + timedelta(days=365 * 5)
    term_years = max(1, (expire.year - commence.year))

    base_rent = unit.get("rent", 0) or 0
    escalation_pct = rng.choice([2.5, 3.0, 3.0, 3.5])

    use_stmt = {
        "industrial": _industrial_use(tenant),
        "office":     _office_use(tenant),
        "retail":     _retail_use(tenant),
        "multifamily": f"private residential dwelling for {tenant}",
    }[asset]

    expense_section = {
        "industrial": NNN_INDUSTRIAL,
        "retail": NNN_INDUSTRIAL + "\n" + CAM_RETAIL,
        "office": """
**Operating Expenses.** Tenant shall pay its Pro Rata Share of Operating Expenses over the Base Year, capped at 5% compounded annually on controllable expenses. Operating Expenses include taxes, insurance, utilities, janitorial, and building services, but exclude capital expenditures and lease commissions.
""",
        "multifamily": """
**Utilities.** Tenant shall be responsible for electricity, gas, and internet service. Landlord shall provide water, sewer, and trash removal.
""",
    }[asset]

    renewal_section = OPTIONS.format(n=rng.choice([1, 2, 2, 3]), y=rng.choice([3, 5, 5]))
    assignment_section = ASSIGNMENT_RETAIL if asset != "multifamily" else """
**Assignment and Subletting.** Resident shall not assign this Lease or sublet the Apartment without the prior written consent of Landlord. Short-term rental arrangements (including through third-party platforms) are expressly prohibited.
"""

    body = f"""# LEASE AGREEMENT

**Property:** {prop['name']}
**Address:** {prop['address']}, {prop['city']}, {prop['state']} {prop.get('zip', '')}
**Premises:** {unit.get('unit', 'Suite')} ({unit.get('sqft', 0):,} sqft) — {unit.get('type', 'demised premises')}
**Landlord:** {prop['name']} Owner LLC
**Tenant:** {tenant}
**Commencement Date:** {commence.isoformat()}
**Expiration Date:** {expire.isoformat()}
**Primary Term:** {term_years} year(s)
**Base Monthly Rent:** ${base_rent:,}
**Rent Escalation:** {escalation_pct}% annually on anniversary of Commencement Date

---

## 1. Premises
Landlord leases to Tenant and Tenant leases from Landlord the Premises described above, together with non-exclusive rights to use common areas. The permitted use is {use_stmt}.

## 2. Term
The Term commences on the Commencement Date and expires on the Expiration Date unless sooner terminated pursuant to this Lease.

## 3. Rent
Base Rent shall be payable in equal monthly installments in advance on the first day of each calendar month. Late payments beyond five (5) days incur a late fee equal to 5% of the unpaid amount.

{expense_section}

## 4. Escalations
Base Rent shall increase by {escalation_pct}% on each anniversary of the Commencement Date throughout the Term and any renewal terms.

{renewal_section}

## 5. Use; Compliance with Laws
Tenant shall use the Premises only for the permitted use set forth above and shall comply with all applicable laws, ordinances, and regulations, including the Americans with Disabilities Act.

{HAZARDOUS_CLAUSE}

{assignment_section}

{FORCE_MAJEURE}

{SURRENDER}

## 6. Insurance
Tenant shall maintain commercial general liability insurance in amounts not less than $2,000,000 per occurrence / $5,000,000 aggregate, naming Landlord as additional insured. Tenant shall also maintain property insurance on its trade fixtures and personal property at full replacement cost.

## 7. Default; Remedies
The occurrence of any of the following shall constitute a default: (a) failure to pay Rent within ten (10) days after written notice; (b) breach of any non-monetary obligation continuing thirty (30) days after written notice; (c) insolvency, bankruptcy, or assignment for the benefit of creditors.

## 8. Miscellaneous
This Lease constitutes the entire agreement between the parties and supersedes all prior discussions. It shall be governed by the laws of the State of {prop['state']}. Any dispute arising hereunder shall be resolved in the courts of {prop['city']}, {prop['state']}.

---

IN WITNESS WHEREOF, the parties have executed this Lease as of the dates set forth below.

**Landlord:** _________________________  Date: _____________
**Tenant:** _________________________    Date: _____________
"""
    return body
