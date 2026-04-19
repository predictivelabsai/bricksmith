"""Central registry of all 22 specialist CRE agents.

Each `AgentSpec` is the source of truth for routing, UI rendering, and prompt
loading. The agent module (in agents/<category>/<slug>.py) owns its TOOLS +
build() but imports its SPEC from here to avoid drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentSpec:
    slug: str
    name: str
    category: str        # sourcing | underwriting | diligence | capital | asset_mgmt
    icon: str            # unicode glyph for UI
    one_liner: str       # marketing sub-heading
    description: str     # full sentence for /agents page
    prefix: str          # router prefix (e.g., "triage:")
    example_prompts: tuple[str, ...] = field(default_factory=tuple)


CATEGORIES: list[dict] = [
    {
        "key": "sourcing",
        "name": "Deal Sourcing & Screening",
        "blurb": "Find deals before the broker flyer hits your inbox.",
        "icon": "◉",
    },
    {
        "key": "underwriting",
        "name": "Underwriting Engine",
        "blurb": "Rent roll to IRR in minutes, not days.",
        "icon": "◈",
    },
    {
        "key": "diligence",
        "name": "Due Diligence Stack",
        "blurb": "Document room audited, surprises flagged early.",
        "icon": "◆",
    },
    {
        "key": "capital",
        "name": "Capital & LP Relations",
        "blurb": "Memos, teasers and LP updates your chair can sign.",
        "icon": "◐",
    },
    {
        "key": "asset_mgmt",
        "name": "Asset Management",
        "blurb": "Keep portfolio NOI growing post-close.",
        "icon": "◼",
    },
]


AGENTS: tuple[AgentSpec, ...] = (
    # Deal Sourcing & Screening
    AgentSpec(
        slug="market_scanner", name="Market Scanner",
        category="sourcing", icon="⚯", prefix="scan:",
        one_liner="Off-market + on-market feeds, deduplicated and ranked.",
        description="Continuously scans broker BOVs, listing feeds, and off-market signal databases, clustering duplicates and surfacing deals that fit your mandate.",
        example_prompts=(
            "scan: Sun Belt industrial value-add, under $80M, built post-2000",
            "What multifamily deals have surfaced in Austin this month?",
            "Any off-market office deals in Dallas with occupancy below 70%?",
        ),
    ),
    AgentSpec(
        slug="deal_triage", name="Deal Triage Agent",
        category="sourcing", icon="✓", prefix="triage:",
        one_liner="Go / no-go in 90 seconds against your investment criteria.",
        description="Screens a deal against your fund's investment criteria — size, geography, asset type, return profile — and returns a go/no-go with 3-bullet rationale.",
        example_prompts=(
            "triage: 220-unit MF in Austin, $62M ask, 4.9% cap in-place",
            "Should we pursue the Raleigh industrial deal? 180k sqft, single-tenant.",
        ),
    ),
    AgentSpec(
        slug="comp_finder", name="Comp Finder",
        category="sourcing", icon="≡", prefix="comps:",
        one_liner="Sales + rent comps across 3 sources with outlier filtering.",
        description="Pulls sales and rent comps from CoStar, RCA, and broker surveys, filters statistical outliers, and returns a tight comp set for valuation.",
        example_prompts=(
            "comps: multifamily Austin Class A 2020+ vintage",
            "Find rent comps for 2BR in Scottsdale in last 6 months",
        ),
    ),
    AgentSpec(
        slug="seller_intent", name="Seller Intent Signal",
        category="sourcing", icon="∿", prefix="intent:",
        one_liner="Ranks properties by likelihood of sale in the next 6 months.",
        description="Combines loan maturity, holding period, ownership type, and operational stress indicators to score every asset in your pipeline for seller motivation.",
        example_prompts=(
            "intent: industrial properties Phoenix 2017 vintage Fannie loans",
            "Which Dallas office properties are likely to trade this year?",
        ),
    ),

    # Underwriting Engine
    AgentSpec(
        slug="rent_roll_parser", name="Rent Roll Parser",
        category="underwriting", icon="☰", prefix="rr:",
        one_liner="Any rent roll format → clean, normalized, ready to model.",
        description="Parses rent rolls in any format (CSV, PDF, scanned) into a consistent schema with occupancy, WALT, lease expiry schedule, and concessions.",
        example_prompts=(
            "rr: parse the rent roll for Parkline Downtown Austin",
            "Show me the WALT for Deep Ellum Commerce Center",
        ),
    ),
    AgentSpec(
        slug="t12_normalizer", name="T12 Normalizer",
        category="underwriting", icon="∑", prefix="t12:",
        one_liner="Ragged T12s into comparable, audit-ready operating statements.",
        description="Normalizes owner T12s onto a standard chart of accounts, removes non-recurring items, and flags revenue/opex anomalies vs. market.",
        example_prompts=(
            "t12: normalize the trailing twelve for Arden Buckhead",
            "Compare Arden Buckhead opex per unit to market",
        ),
    ),
    AgentSpec(
        slug="pro_forma_builder", name="Pro Forma Builder",
        category="underwriting", icon="▤", prefix="pf:",
        one_liner="5-year pro forma with sensitivity grid — editable assumptions.",
        description="Builds a 5-year pro forma with rent growth, vacancy, opex inflation, capex, and exit cap. Sensitivity grid across the two most impactful variables.",
        example_prompts=(
            "pf: build a 5-year pro forma for Vista East Austin assuming 4% rent growth",
            "What's the base case IRR on Cary Last-Mile?",
        ),
    ),
    AgentSpec(
        slug="debt_stack_modeler", name="Debt Stack Modeler",
        category="underwriting", icon="▥", prefix="debt:",
        one_liner="Senior + mezz + pref equity stacks with live DSCR + LTV.",
        description="Models capital stacks across senior debt, mezz, preferred equity, and sponsor common — with DSCR coverage, LTV, and refinance sensitivity.",
        example_prompts=(
            "debt: size a 65% LTV Fannie loan on Parkline Downtown",
            "What's the max proceeds at 1.35x DSCR on LoDo Tower?",
        ),
    ),
    AgentSpec(
        slug="return_metrics", name="Return Metrics",
        category="underwriting", icon="◈", prefix="ret:",
        one_liner="Levered + unlevered IRR, CoC, MOIC, equity multiple.",
        description="Computes return metrics from projected cash flows — levered/unlevered IRR, cash-on-cash, MOIC, equity multiple — with waterfall options.",
        example_prompts=(
            "ret: compute returns on the Alto RiNo pro forma",
            "What's the levered IRR with a 30% promote over 10%?",
        ),
    ),

    # Due Diligence Stack
    AgentSpec(
        slug="doc_room_auditor", name="Document Room Auditor",
        category="diligence", icon="☷", prefix="dr:",
        one_liner="Cross-checks the data room against a full DD checklist.",
        description="Audits the seller's data room against a 120-item DD checklist, flagging missing documents, stale versions, and internal inconsistencies.",
        example_prompts=(
            "dr: audit the data room for Grand Midtown",
            "Which DD items are missing for the Raleigh industrial deal?",
        ),
    ),
    AgentSpec(
        slug="lease_abstractor", name="Lease Abstractor",
        category="diligence", icon="▢", prefix="abstract:",
        one_liner="PDFs → lease abstracts with key terms, options, and risks.",
        description="Abstracts PDF leases into structured records — commencement, expiry, base rent, escalations, options, assignment, kickouts — with page-cited citations.",
        example_prompts=(
            "abstract: the lease for Suite 100 at Deep Ellum Commerce Center",
            "What are the force majeure terms across my industrial tenants?",
        ),
    ),
    AgentSpec(
        slug="title_zoning", name="Title & Zoning Checker",
        category="diligence", icon="◰", prefix="title:",
        one_liner="Reads title commitment + zoning memo, flags material exceptions.",
        description="Parses the title commitment and zoning letter, flags material Schedule B-II exceptions and nonconforming conditions that affect value or insurability.",
        example_prompts=(
            "title: summarize title issues for Vista East Austin",
            "Are there any zoning nonconformities on the Dallas deal?",
        ),
    ),
    AgentSpec(
        slug="physical_condition", name="Physical Condition Reviewer",
        category="diligence", icon="⌂", prefix="pcr:",
        one_liner="Reads PCR + inspection PDFs, builds a capex reserve schedule.",
        description="Reads property condition reports and inspection PDFs, extracts deferred maintenance, roof/HVAC life, and builds a Year 1–10 capex reserve schedule.",
        example_prompts=(
            "pcr: what deferred maintenance is flagged for Maple Downtown?",
            "Build a 10-year capex schedule for Grand Sandy Springs",
        ),
    ),
    AgentSpec(
        slug="environmental_risk", name="Environmental Risk Flagger",
        category="diligence", icon="⚠", prefix="env:",
        one_liner="Phase I ESA review — flags RECs and recommends scope.",
        description="Reads Phase I ESAs and environmental databases to identify RECs, off-site concerns like vapor intrusion, and recommends Phase II scope where warranted.",
        example_prompts=(
            "env: any RECs at the Phoenix industrial deal?",
            "Summarize environmental risk across my Sun Belt portfolio",
        ),
    ),

    # Capital & LP Relations
    AgentSpec(
        slug="investor_memo", name="Investor Memo Writer",
        category="capital", icon="✎", prefix="memo:",
        one_liner="Investment memo your IC will actually read.",
        description="Drafts a full investment memo — exec summary, strategy, market, underwriting, risks, returns — from the deal's data in your system.",
        example_prompts=(
            "memo: draft the investment memo for Arden Buckhead",
            "Write a 2-page IC memo for Parkline Downtown",
        ),
    ),
    AgentSpec(
        slug="deal_teaser", name="Deal Teaser Designer",
        category="capital", icon="✦", prefix="teaser:",
        one_liner="2-page teaser with property photos, summary, returns snapshot.",
        description="Generates a branded 2-page teaser suitable for LP distribution — cover, property summary, key metrics, returns table, risks.",
        example_prompts=(
            "teaser: build a teaser for the Phoenix industrial deal",
            "Draft a teaser for LPs on the Tampa retail portfolio",
        ),
    ),
    AgentSpec(
        slug="lp_update", name="LP Update Generator",
        category="capital", icon="⇄", prefix="lpupd:",
        one_liner="Quarterly LP letter with portfolio performance + outlook.",
        description="Generates a quarterly LP letter pulling portfolio performance, deals closed/under contract, market outlook, and capital calls.",
        example_prompts=(
            "lpupd: draft Q1 letter for Fund II LPs",
            "Generate a portfolio update for the industrial sleeve",
        ),
    ),
    AgentSpec(
        slug="fundraising_crm", name="Fundraising CRM Copilot",
        category="capital", icon="◎", prefix="crm:",
        one_liner="LP pipeline ranked by fit, staleness, and check size.",
        description="Reads your LP CRM to rank prospects by mandate fit, staleness of last touch, and committed check size — and drafts the next touchpoint.",
        example_prompts=(
            "crm: who are the top 10 LPs to reach out to this week?",
            "Draft a re-engagement email to LPs we haven't touched in 60 days",
        ),
    ),

    # Asset Management
    AgentSpec(
        slug="rent_optimization", name="Rent Optimization Agent",
        category="asset_mgmt", icon="↗", prefix="rentopt:",
        one_liner="Unit-by-unit rent recommendations driven by comps + lease expiry.",
        description="Evaluates in-place rents vs. current market, concessions, and lease expiry schedule to recommend renewal and new-lease pricing.",
        example_prompts=(
            "rentopt: what rent should we push for Parkline Downtown on renewals?",
            "Where is in-place most below market across my portfolio?",
        ),
    ),
    AgentSpec(
        slug="opex_variance", name="Opex Variance Watcher",
        category="asset_mgmt", icon="Δ", prefix="opex:",
        one_liner="Weekly opex variance vs. budget — with root cause commentary.",
        description="Watches weekly opex actuals vs. budget across the portfolio, surfaces variances above your threshold, and suggests root causes from expense metadata.",
        example_prompts=(
            "opex: what's driving the variance at Arden Buckhead this month?",
            "Show me the top 5 portfolio-wide opex variances",
        ),
    ),
    AgentSpec(
        slug="capex_prioritizer", name="Capex Prioritizer",
        category="asset_mgmt", icon="⚒", prefix="capex:",
        one_liner="Ranks capex projects by ROI, NOI impact, and urgency.",
        description="Ranks pending capex projects across the portfolio by expected NOI lift, return on cost, and urgency/risk of deferral.",
        example_prompts=(
            "capex: rank my open capex projects by ROI",
            "Should we do the roof replacement or the unit turn program first?",
        ),
    ),
    AgentSpec(
        slug="tenant_churn", name="Tenant Churn Predictor",
        category="asset_mgmt", icon="∠", prefix="churn:",
        one_liner="Scores each tenant's renewal likelihood; drives retention actions.",
        description="Predicts each commercial tenant's renewal likelihood from lease economics, usage signals, and tenure, and prioritizes renewal outreach.",
        example_prompts=(
            "churn: which industrial tenants are most at risk of leaving?",
            "Score renewal likelihood for Deep Ellum Commerce Center",
        ),
    ),
)


AGENTS_BY_SLUG: dict[str, AgentSpec] = {a.slug: a for a in AGENTS}
AGENTS_BY_CATEGORY: dict[str, list[AgentSpec]] = {}
for a in AGENTS:
    AGENTS_BY_CATEGORY.setdefault(a.category, []).append(a)


def all_agents() -> tuple[AgentSpec, ...]:
    return AGENTS


def by_slug(slug: str) -> AgentSpec | None:
    return AGENTS_BY_SLUG.get(slug)
