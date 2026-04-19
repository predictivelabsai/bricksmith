"""Marketing routes: /, /platform, /agents, /agents/<slug>, /how-it-works, /pricing, /contact."""

from __future__ import annotations

from fasthtml.common import (
    Div, H1, H2, H3, H4, P, Ul, Li, Section, Article, Span, A, Form, Input, Textarea, Label, Button, NotStr,
)

from app import rt
from agents.registry import AGENTS, AGENTS_BY_CATEGORY, AGENTS_BY_SLUG, CATEGORIES
from landing.components import (
    page, Hero, CategoryPillar, AgentCard, CategorySection, CaseStudyStrip, CTASection,
    Eyebrow, Heading, Body_, Button_, Pill, Section_, SITE_NAME, SITE_TAGLINE,
)


# ── / ────────────────────────────────────────────────────────────────
@rt("/")
def home():
    pillars = Section_(
        Div(
            Eyebrow("Five stages, one system"),
            Heading(2, "Every role your deal team plays — live inside PropAnalyst.", cls="mt-3 max-w-4xl mb-10"),
            cls="mb-6",
        ),
        Div(
            *[CategoryPillar(c) for c in CATEGORIES],
            cls="grid md:grid-cols-2 lg:grid-cols-5 gap-4",
        ),
        cls="border-t border-line",
    )

    showcase = Section_(
        Div(
            Eyebrow("See it running"),
            Heading(2, "A kanban, a chat, an analytics bar — one system.", cls="mt-3 max-w-4xl mb-6"),
            P("Pipeline across 10 deal stages, per-deal chat with the property brief "
              "pre-rendered, editable agent prompts, and natural-language analytics over "
              "your CRE database — all against the same synthetic dataset.",
              cls="text-ink-muted text-sm max-w-3xl mb-8"),
            cls="mb-6",
        ),
        Div(
            NotStr(
                """
                <div class="relative rounded-2xl overflow-hidden border border-line bg-bg-elevated">
                  <img src="/docs/bricksmith.gif"
                       alt="Bricksmith app demo — pipeline, chat, instructions, analytics"
                       style="width:100%; display:block;"
                       loading="lazy">
                </div>
                """
            ),
            cls="max-w-5xl mx-auto",
        ),
        Div(
            A("Open the app", href="/app", cls="inline-flex items-center gap-2 text-accent text-sm font-medium mr-6"),
            A("Product tour (PDF)", href="/docs/bricksmith-product-tour.pdf",
              cls="inline-flex items-center gap-2 text-ink-muted text-sm hover:text-accent"),
            cls="mt-6 text-center",
        ),
        cls="border-t border-line",
    )

    how = Section_(
        Div(
            Eyebrow("How it works"),
            Heading(2, "Source → Underwrite → Close.", cls="mt-3 max-w-3xl mb-10"),
            cls="mb-6",
        ),
        Div(
            *[Article(
                P(num, cls="font-mono text-[11px] tracking-widest uppercase text-ink-dim mb-3"),
                H3(title, cls="text-ink text-xl font-medium mb-3"),
                P(body, cls="text-ink-muted text-sm leading-relaxed"),
                cls="p-7 rounded-2xl bg-bg-elevated border border-line h-full",
            ) for (num, title, body) in [
                ("01", "Source deals that fit",
                 "Market Scanner and Deal Triage filter thousands of listings against your fund's mandate so the first deal you see is already shortlisted."),
                ("02", "Model them in hours, not weeks",
                 "Rent Roll Parser, T12 Normalizer and Pro Forma Builder take owner financials straight into an investor-ready model with sensitivity."),
                ("03", "Close, raise, operate",
                 "Memo Writer, LP Update Generator and the Asset Management agents keep every commitment, covenant and opex variance in view."),
            ]],
            cls="grid md:grid-cols-3 gap-4",
        ),
        cls="border-t border-line",
    )

    return page(
        "Agentic AI for commercial real estate",
        Hero(),
        pillars,
        showcase,
        how,
        CaseStudyStrip(),
        CTASection(),
        current_path="/",
    )


# ── /platform ────────────────────────────────────────────────────────
@rt("/platform")
def platform():
    return page(
        "Platform",
        Section_(
            Eyebrow("Platform"),
            Heading(1, "One system. Every stage. All your data.", cls="mt-4 max-w-4xl"),
            P(
                "Bricksmith lives where your deal team already works. Twenty-two specialist "
                "agents share a single model of your pipeline, your portfolio, and your market. "
                "Each agent has its own tools and prompts — and they pass artifacts between each "
                "other without the analyst re-keying anything.",
                cls="mt-6 text-ink-muted text-lg max-w-3xl leading-relaxed",
            ),
            cls="border-t border-line",
        ),
        Section_(
            Div(
                *[Article(
                    Div(Span(c["icon"], cls="text-accent text-xl"),
                        Span(f"{len(AGENTS_BY_CATEGORY[c['key']])} agents",
                             cls="ml-auto font-mono text-[11px] tracking-widest uppercase text-ink-dim"),
                        cls="flex items-center mb-4"),
                    H3(c["name"], cls="text-ink text-xl font-medium mb-2"),
                    P(c["blurb"], cls="text-ink-muted leading-relaxed"),
                    cls="p-7 rounded-2xl bg-bg-elevated border border-line h-full",
                ) for c in CATEGORIES],
                cls="grid md:grid-cols-2 lg:grid-cols-5 gap-4",
            ),
            cls="border-t border-line",
        ),
        Section_(
            Eyebrow("Under the hood"),
            Heading(2, "Not a wrapper. A system.", cls="mt-3 max-w-3xl mb-10"),
            Div(
                *[Article(
                    P(k, cls="text-[11px] font-mono tracking-widest uppercase text-ink-dim mb-3"),
                    P(v, cls="text-ink leading-relaxed"),
                    cls="p-7 rounded-2xl bg-bg-elevated border border-line h-full",
                ) for (k, v) in [
                    ("Agents", "22 LangGraph ReAct agents, one per specialty, sharing a common tool registry and prompt library."),
                    ("Tools", "70+ StructuredTools that read rent rolls, T12s, comps, PDFs, and market signals directly — not through copy-paste."),
                    ("RAG", "Postgres + pgvector index of every lease, title commitment, environmental report, and market memo in your deal."),
                    ("Memory", "Every conversation and every artifact persists, queryable across agents, so Week 3 of diligence still knows what Week 1 agreed."),
                ]],
                cls="grid md:grid-cols-2 lg:grid-cols-4 gap-4",
            ),
            cls="border-t border-line",
        ),
        CTASection(),
        current_path="/platform",
    )


# ── /agents ──────────────────────────────────────────────────────────
@rt("/agents")
def agents_page():
    return page(
        "Agents",
        Section_(
            Eyebrow("22 specialist agents"),
            Heading(1, "Every role already wired in.", cls="mt-4 max-w-4xl"),
            P(
                "Each agent has a narrow remit, deep tooling, and a prefix you can type in the chat "
                "to call it directly. Or just ask in plain English — the router picks the right one.",
                cls="mt-6 text-ink-muted text-lg max-w-3xl leading-relaxed",
            ),
            cls="border-t border-line",
        ),
        *[CategorySection(c) for c in CATEGORIES],
        CTASection(),
        current_path="/agents",
    )


# ── /agents/<slug> ───────────────────────────────────────────────────
@rt("/agents/{slug}")
def agent_detail(slug: str):
    agent = AGENTS_BY_SLUG.get(slug)
    if agent is None:
        return page(
            "Agent not found",
            Section_(
                H1("Not found", cls="text-ink text-3xl"),
                P("No agent at that URL. See all ", A("22 agents", href="/agents", cls="text-accent underline"), ".",
                  cls="text-ink-muted mt-4"),
            ),
            current_path="/agents",
        )
    cat = next(c for c in CATEGORIES if c["key"] == agent.category)
    return page(
        f"{agent.name}",
        Section_(
            Div(
                A("← All agents", href="/agents", cls="text-ink-dim text-xs hover:text-accent"),
                cls="mb-6",
            ),
            Div(
                Span(agent.icon, cls="text-accent text-4xl"),
                Span(cat["name"], cls="ml-4 font-mono text-[11px] tracking-widest uppercase text-ink-dim"),
                cls="flex items-center mb-4",
            ),
            Heading(1, agent.name, cls="max-w-4xl"),
            P(agent.one_liner, cls="mt-5 text-ink-muted text-lg max-w-3xl"),
            Div(Pill(f"prefix: {agent.prefix}"),
                Pill(f"category: {cat['key']}"),
                cls="mt-6 flex flex-wrap gap-2"),
            cls="border-t border-line",
        ),
        Section_(
            Div(
                Div(
                    Eyebrow("What it does"),
                    P(agent.description, cls="mt-4 text-ink leading-relaxed"),
                    cls="md:col-span-2",
                ),
                Div(
                    Eyebrow("Example prompts"),
                    Ul(
                        *[Li(
                            Div(f'"{p}"', cls="px-4 py-3 rounded-xl bg-bg-elevated border border-line text-sm text-ink leading-relaxed"),
                            cls="mb-2",
                        ) for p in agent.example_prompts],
                        cls="mt-4 space-y-2",
                    ),
                    cls="",
                ),
                cls="grid md:grid-cols-3 gap-10",
            ),
            cls="border-t border-line",
        ),
        CTASection(headline=f"Try {agent.name} now.",
                   body="Synthetic CRE data is already loaded. Open the app and type the example prompt above.",
                   cta_label="Open the app", cta_href="/app"),
        current_path="/agents",
    )


# ── /how-it-works ────────────────────────────────────────────────────
@rt("/how-it-works")
def how_it_works():
    return page(
        "How it works",
        Section_(
            Eyebrow("How it works"),
            Heading(1, "From broker flyer to signed PSA — in one system.", cls="mt-4 max-w-4xl"),
            cls="border-t border-line",
        ),
        *[Section_(
            Div(
                Span(num, cls="font-mono text-[11px] tracking-widest uppercase text-ink-dim"),
                Heading(2, title, cls="mt-3 max-w-3xl"),
                P(body, cls="mt-5 text-ink-muted text-lg max-w-3xl leading-relaxed"),
                cls="mb-8",
            ),
            Div(*[Pill(name) for name in agents], cls="flex flex-wrap gap-2"),
            cls="border-t border-line",
        ) for (num, title, body, agents) in [
            ("01 — Source",
             "Surface the right deals faster than the next analyst.",
             "Market Scanner watches hundreds of broker feeds, off-market databases, and seller-intent signals. Deal Triage returns a go/no-go on each in under 90 seconds. Comp Finder tightens valuation confidence before you commit.",
             ["Market Scanner", "Deal Triage", "Comp Finder", "Seller Intent"]),
            ("02 — Underwrite",
             "Owner financials to investor-ready model in under an hour.",
             "Rent Roll Parser and T12 Normalizer ingest whatever format the seller sends. Pro Forma Builder produces a 5-year model with sensitivity. Debt Stack Modeler sizes the capital structure. Return Metrics spits out levered and unlevered IRR, CoC, MOIC.",
             ["Rent Roll Parser", "T12 Normalizer", "Pro Forma Builder", "Debt Stack Modeler", "Return Metrics"]),
            ("03 — Diligence",
             "No surprise at closing.",
             "Document Room Auditor checks the seller data room against a 120-item DD list. Lease Abstractor reads every lease. Title & Zoning, Physical Condition, and Environmental agents flag material issues with page-level citations.",
             ["Document Room Auditor", "Lease Abstractor", "Title & Zoning", "Physical Condition", "Environmental Risk"]),
            ("04 — Raise",
             "LP material that your chair will actually sign.",
             "Investor Memo Writer drafts the IC memo from your own data. Deal Teaser Designer produces a 2-page LP teaser. LP Update Generator writes the quarterly letter. Fundraising CRM Copilot ranks prospects and drafts outreach.",
             ["Investor Memo Writer", "Deal Teaser Designer", "LP Update Generator", "Fundraising CRM Copilot"]),
            ("05 — Operate",
             "Post-close, the agents stay on.",
             "Rent Optimization recommends renewal pricing. Opex Variance Watcher flags drift weekly. Capex Prioritizer ranks projects by NOI impact. Tenant Churn Predictor scores renewal risk across commercial tenants.",
             ["Rent Optimization", "Opex Variance Watcher", "Capex Prioritizer", "Tenant Churn Predictor"]),
        ]],
        CTASection(),
        current_path="/how-it-works",
    )


# ── /pricing ─────────────────────────────────────────────────────────
@rt("/pricing")
def pricing():
    tiers = [
        {
            "name": "Pilot",
            "price": "$0",
            "sub": "for 30 days",
            "blurb": "One analyst, one deal, all 22 agents, synthetic + your own data.",
            "features": [
                "All 22 agents",
                "1 concurrent user",
                "Up to 5 live deals",
                "Synthetic CRE dataset included",
                "Email support",
            ],
            "cta": ("Start pilot", "/contact"),
            "primary": False,
        },
        {
            "name": "Team",
            "price": "Contact us",
            "sub": "per fund",
            "blurb": "Sponsor or family office running active acquisitions.",
            "features": [
                "All 22 agents",
                "Up to 15 seats",
                "Unlimited deals + properties",
                "SSO + audit log",
                "Shared memory across team",
                "Priority support",
            ],
            "cta": ("Book a demo", "/contact"),
            "primary": True,
        },
        {
            "name": "Platform",
            "price": "Custom",
            "sub": "for larger operators",
            "blurb": "Dedicated cluster, your brand, custom agents.",
            "features": [
                "Everything in Team",
                "Unlimited seats",
                "Dedicated instance",
                "Bring your own LLM provider",
                "Custom agents and tools",
                "Onsite training",
            ],
            "cta": ("Contact sales", "/contact"),
            "primary": False,
        },
    ]
    return page(
        "Pricing",
        Section_(
            Eyebrow("Pricing"),
            Heading(1, "Start with synthetic data. Upgrade when it sticks.", cls="mt-4 max-w-4xl"),
            P("No setup fee. No per-seat tax. No prompt-token surprise.",
              cls="mt-6 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            cls="border-t border-line",
        ),
        Section_(
            Div(
                *[Article(
                    P(t["name"], cls="text-[11px] font-mono tracking-widest uppercase text-ink-dim mb-3"),
                    Div(
                        Span(t["price"], cls="text-4xl md:text-5xl font-medium tracking-tighter text-ink"),
                        Span(f" {t['sub']}", cls="text-ink-muted text-sm ml-2"),
                        cls="mb-4",
                    ),
                    P(t["blurb"], cls="text-ink-muted leading-relaxed mb-6"),
                    Ul(
                        *[Li(
                            Span("✓ ", cls="text-accent mr-2"),
                            Span(f, cls="text-ink text-sm"),
                            cls="mb-2 flex items-baseline",
                        ) for f in t["features"]],
                        cls="mb-8 space-y-1",
                    ),
                    Button_(t["cta"][0], href=t["cta"][1], primary=t["primary"]),
                    cls=("p-8 rounded-2xl bg-bg-elevated h-full flex flex-col " +
                         ("border border-accent/60" if t["primary"] else "border border-line")),
                ) for t in tiers],
                cls="grid md:grid-cols-3 gap-4",
            ),
            cls="border-t border-line",
        ),
        CTASection(),
        current_path="/pricing",
    )


# ── /contact ─────────────────────────────────────────────────────────
@rt("/contact")
def contact(sent: bool = False):
    form = Form(
        Div(
            Label("Your name", cls="block text-xs font-mono tracking-widest uppercase text-ink-dim mb-2"),
            Input(name="name", type="text", required=True,
                  cls="w-full px-4 py-3 rounded-xl bg-bg-elevated border border-line text-ink focus:border-accent focus:outline-none"),
            cls="mb-5",
        ),
        Div(
            Label("Email", cls="block text-xs font-mono tracking-widest uppercase text-ink-dim mb-2"),
            Input(name="email", type="email", required=True,
                  cls="w-full px-4 py-3 rounded-xl bg-bg-elevated border border-line text-ink focus:border-accent focus:outline-none"),
            cls="mb-5",
        ),
        Div(
            Label("Firm (optional)", cls="block text-xs font-mono tracking-widest uppercase text-ink-dim mb-2"),
            Input(name="firm", type="text",
                  cls="w-full px-4 py-3 rounded-xl bg-bg-elevated border border-line text-ink focus:border-accent focus:outline-none"),
            cls="mb-5",
        ),
        Div(
            Label("Tell us about your pipeline", cls="block text-xs font-mono tracking-widest uppercase text-ink-dim mb-2"),
            Textarea(name="message", rows="5", required=True,
                     cls="w-full px-4 py-3 rounded-xl bg-bg-elevated border border-line text-ink focus:border-accent focus:outline-none"),
            cls="mb-8",
        ),
        Button("Send message →", type="submit",
               cls="inline-flex items-center gap-2 px-5 py-3 rounded-full text-sm font-medium bg-accent text-bg hover:bg-ink transition-all"),
        method="post",
        action="/contact",
    )

    success = Div(
        Div(
            Span("✓", cls="text-accent text-2xl"),
            cls="mb-4",
        ),
        H3("Thanks — we'll be in touch shortly.", cls="text-ink text-xl mb-2"),
        P("Usually within one business day.", cls="text-ink-muted"),
        cls="p-8 rounded-2xl bg-bg-elevated border border-line",
    )

    return page(
        "Contact",
        Section_(
            Eyebrow("Contact"),
            Heading(1, "Let's look at one of your deals.", cls="mt-4 max-w-4xl"),
            P("Send us a note and we'll set up a 20-minute walkthrough. We'll load one of your "
              "recent deals into Bricksmith and show you the full agent flow — live.",
              cls="mt-6 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            Div(
                success if sent else form,
                cls="mt-12 max-w-xl",
            ),
            cls="border-t border-line",
        ),
        current_path="/contact",
    )


@rt("/contact", methods=["POST"])
def contact_post(name: str = "", email: str = "", firm: str = "", message: str = ""):
    # Synthetic handler — log it and redirect. Wire up a real inbox / CRM later.
    import logging
    logging.getLogger(__name__).info("contact form submitted: %s (%s) %s chars",
                                     name, email, len(message or ""))
    return page(
        "Thanks",
        Section_(
            Eyebrow("Contact"),
            Heading(1, "Thanks — we'll be in touch shortly.", cls="mt-4 max-w-4xl"),
            P("Usually within one business day. In the meantime, ",
              A("open the app", href="/app", cls="text-accent underline"),
              " — synthetic CRE data is already loaded.",
              cls="mt-6 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            cls="border-t border-line",
        ),
        current_path="/contact",
    )
