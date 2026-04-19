"""Pipeline kanban view — properties grouped by deal_stage.

/app/pipeline          → kanban board across 10 CRE deal stages
/app/pipeline/<slug>   → per-deal chat; right pane pre-renders property brief
"""

from __future__ import annotations

import json

from fasthtml.common import (
    Html, Head, Body, Meta, Title, Link, Script, NotStr,
    Div, Span, A, H1, H3, P, Button, Form, Textarea, Input,
)

from app import rt
from agents.registry import AGENTS
from chat.components import (
    left_pane, signin_overlay, sample_cards, message_bubble,
)
from chat.routes import _ensure_user, _list_sessions, _session_messages
from db import fetch_all, fetch_one


# 10 CRE deal stages — mirrors bricksmith.properties.deal_stage values.
STAGES = [
    ("sourced",   "Sourced"),
    ("screened",  "Screened"),
    ("loi",       "LOI"),
    ("psa",       "Under Contract"),
    ("diligence", "Diligence"),
    ("committee", "Committee"),
    ("closing",   "Closing"),
    ("closed",    "Closed"),
    ("held",      "Held"),
    ("exited",    "Exited"),
]

STAGE_COLORS = {
    "sourced":   "#8AA0C8",
    "screened":  "#6B8FBD",
    "loi":       "#C89B5B",
    "psa":       "#D4A574",
    "diligence": "#E7B66B",   # accent
    "committee": "#B08A4A",
    "closing":   "#7FB08A",
    "closed":    "#4A8E66",
    "held":      "#34D399",
    "exited":    "#8AA0C8",
}

HEAT_COLORS = {"hot": "#F87171", "warm": "#E7B66B", "cold": "#8AA0C8"}


def _pipeline_head(title: str) -> Head:
    return Head(
        Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Title(f"{title} · Bricksmith"),
        Link(rel="icon", type="image/svg+xml", href="/static/favicon.svg"),
        Link(rel="preconnect", href="https://fonts.googleapis.com"),
        Link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
        Link(rel="stylesheet",
             href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"),
        Link(rel="stylesheet", href="/static/site.css"),
        Link(rel="stylesheet", href="/static/app.css"),
        Link(rel="stylesheet", href="/static/pipeline.css"),
    )


def _money(n: float | int | None) -> str:
    if n is None:
        return "—"
    n = float(n)
    if abs(n) >= 1_000_000:
        return f"${n/1_000_000:.1f}M"
    if abs(n) >= 1_000:
        return f"${n/1_000:.0f}k"
    return f"${n:,.0f}"


def _card_for(prop: dict) -> A:
    name = prop["name"]
    submarket = prop.get("submarket") or ""
    city = prop.get("city") or ""
    atype = (prop.get("asset_type") or "").replace("_", " ").title()
    intent = (prop.get("seller_intent") or "").lower()
    heat = HEAT_COLORS.get(intent, "#8AA0C8")

    noi = prop.get("noi_annual")
    cap = prop.get("cap_rate")
    ask = prop.get("asking_price")

    return A(
        Div(
            Div(
                Span(cls="heat-dot", style=f"background:{heat}"),
                Span(name, cls="card-title"),
                cls="card-head",
            ),
            Div(
                Span(f"{atype} · {submarket or city}", cls="card-sub"),
                cls="card-meta",
            ),
            Div(
                Span(f"NOI {_money(noi)}", cls="card-metric"),
                Span("·"),
                Span(f"{float(cap):.2f}% cap" if cap else "— cap", cls="card-metric"),
                cls="card-metrics-line",
            ),
            Div(
                Span(f"Ask {_money(ask)}" if ask else "Closed", cls="card-ev"),
                Span(f"{int(prop['units'])} units" if prop.get("units") else (
                    f"{int(prop['sqft']):,} sf" if prop.get("sqft") else ""),
                    cls="card-mult"),
                cls="card-ev-line",
            ),
            cls="deal-card",
        ),
        href=f"/app/pipeline/{prop['slug']}",
        cls="deal-card-link",
    )


def _board(by_stage: dict[str, list[dict]]) -> Div:
    cols = []
    for stage_key, label in STAGES:
        cards = by_stage.get(stage_key, [])
        cols.append(Div(
            Div(
                Span(label, cls="col-title"),
                Span(str(len(cards)), cls="col-count"),
                cls="col-head",
                style=f"border-bottom-color:{STAGE_COLORS.get(stage_key, '#8AA0C8')}",
            ),
            Div(*[_card_for(c) for c in cards], cls="col-body"),
            cls="kanban-col",
        ))
    return Div(*cols, cls="kanban-board")


@rt("/app/pipeline")
def pipeline_home(sess, asset: str = "", ownership: str = ""):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []

    sql_parts = ["SELECT * FROM bricksmith.properties WHERE TRUE"]
    params: list = []
    if asset:
        sql_parts.append("AND asset_type = %s"); params.append(asset)
    if ownership:
        sql_parts.append("AND ownership = %s"); params.append(ownership)
    sql_parts.append("ORDER BY deal_stage, name")
    rows = fetch_all(" ".join(sql_parts), tuple(params))

    by_stage: dict[str, list[dict]] = {}
    for r in rows:
        by_stage.setdefault(r.get("deal_stage") or "sourced", []).append(r)

    asset_types = sorted({r["asset_type"] for r in rows if r.get("asset_type")})
    ownership_types = sorted({r["ownership"] for r in rows if r.get("ownership")})

    filters = Div(
        A("All", href="/app/pipeline",
          cls=f"filter-chip{' active' if not asset and not ownership else ''}"),
        *[A(a.replace("_", " ").title(),
             href=f"/app/pipeline?asset={a}",
             cls=f"filter-chip{' active' if asset == a else ''}") for a in asset_types],
        Span("·", cls="filter-divider"),
        *[A(o.replace("_", " ").title(),
             href=f"/app/pipeline?ownership={o}",
             cls=f"filter-chip{' active' if ownership == o else ''}")
          for o in ownership_types],
        cls="pipeline-filters",
    )

    body = Body(
        signin_overlay(),
        Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
        left_pane(user_email=email, sessions=sessions, current_sid="",
                  current_path="/app/pipeline"),
        Div(
            Div(
                Div(
                    Button("☰", cls="mobile-menu-btn", onclick="toggleLeftPane()"),
                    Span("Pipeline", cls="chat-header-title"),
                    Span("·", cls="chat-header-dot"),
                    Span(f"{len(rows)} properties", cls="chat-header-agent"),
                    cls="chat-header-left",
                ),
                Div(
                    A("Back to chat", href="/app", cls="back-to-chat-btn"),
                    cls="chat-header-actions",
                ),
                cls="chat-header",
            ),
            filters,
            _board(by_stage),
            cls="center-pane pipeline-center",
        ),
        Script(src="/static/chat.js"),
        cls="bg-bg text-ink font-sans antialiased app pane-closed pipeline-app",
    )
    return Html(_pipeline_head("Pipeline"), body, lang="en")


@rt("/app/pipeline/{slug}")
def deal_detail(sess, slug: str):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []

    prop = fetch_one("SELECT * FROM bricksmith.properties WHERE slug = %s", (slug,))
    if not prop:
        return Html(
            _pipeline_head("Not found"),
            Body(Div(H1("Property not found"),
                     A("Back to pipeline", href="/app/pipeline"),
                     cls="p-10 text-ink"), lang="en"),
            lang="en",
        )

    pid = prop["id"]

    # LTM T12 aggregate (last 12 months)
    t12 = fetch_all(
        "SELECT gross_rent, other_income, vacancy_loss, noi FROM bricksmith.t12_statements "
        "WHERE property_id = %s ORDER BY month DESC LIMIT 12",
        (pid,),
    )
    ltm_rev = sum(float(r.get("gross_rent") or 0) + float(r.get("other_income") or 0) for r in t12)
    ltm_noi = sum(float(r.get("noi") or 0) for r in t12)

    # Top 5 active leases (biggest tenants by base_rent)
    leases = fetch_all(
        "SELECT unit, tenant, base_rent, end_date FROM bricksmith.leases "
        "WHERE property_id = %s AND status = 'active' AND tenant IS NOT NULL "
        "ORDER BY base_rent DESC NULLS LAST LIMIT 5",
        (pid,),
    )

    # Top 5 DD findings (severity ordered)
    findings = fetch_all(
        "SELECT agent_slug, category, severity, summary FROM bricksmith.dd_findings "
        "WHERE property_id = %s ORDER BY CASE severity "
        "WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 "
        "WHEN 'low' THEN 3 ELSE 4 END LIMIT 5",
        (pid,),
    )

    # Resume a per-deal chat session if one exists
    deal_sid_row = fetch_one(
        "SELECT id FROM bricksmith.chat_sessions WHERE user_id = %s AND title = %s "
        "ORDER BY updated_at DESC LIMIT 1",
        (uid or 0, f"Deal: {prop['name']}"),
    ) if uid else None
    session_id = deal_sid_row["id"] if deal_sid_row else None
    messages = _session_messages(session_id) if session_id else []

    ask = prop.get("asking_price")
    cap = prop.get("cap_rate")
    noi = prop.get("noi_annual")
    atype = (prop.get("asset_type") or "").replace("_", " ").title()
    stage = (prop.get("deal_stage") or "").upper()
    submarket = prop.get("submarket") or ""

    units_sf = (
        f"{int(prop['units'])} units" if prop.get("units")
        else (f"{int(prop['sqft']):,} sf" if prop.get("sqft") else "—")
    )
    occ = f"{float(prop['occupancy_pct']):.1f}%" if prop.get("occupancy_pct") is not None else "—"

    brief_html = f"""
    <div class="deal-brief">
      <h3 class="deal-name">{prop['name']}</h3>
      <div class="deal-tags">
        <span class="tag">{atype}</span>
        <span class="tag">{submarket}</span>
        <span class="tag tag-stage">{stage}</span>
      </div>
      <div class="deal-kv">
        <div><strong>Address</strong> {prop.get('address') or ''}</div>
        <div><strong>Location</strong> {prop.get('city') or ''}, {prop.get('state') or ''}</div>
        <div><strong>Size</strong> {units_sf}</div>
        <div><strong>Built</strong> {prop.get('year_built') or '—'}</div>
        <div><strong>Occupancy</strong> {occ}</div>
        <div><strong>Ownership</strong> {(prop.get('ownership') or '').replace('_', ' ').title()}</div>
      </div>
      <h4>Deal economics</h4>
      <div class="deal-kv">
        <div><strong>Ask price</strong> {_money(ask)}</div>
        <div><strong>NOI (annual)</strong> {_money(noi)}</div>
        <div><strong>Cap rate</strong> {(f"{float(cap):.2f}%" if cap is not None else '—')}</div>
        <div><strong>LTM revenue</strong> {_money(ltm_rev) if ltm_rev else '—'}</div>
        <div><strong>LTM NOI</strong> {_money(ltm_noi) if ltm_noi else '—'}</div>
        <div><strong>Seller intent</strong> {(prop.get('seller_intent') or '').title()}</div>
      </div>
      <h4>Top tenants</h4>
      <ul class="deal-list">
        {"".join(f"<li><span>{(l.get('tenant') or '—')} · {(l.get('unit') or '')}</span><span class='muted'>{_money(l.get('base_rent'))} base</span></li>" for l in leases) or "<li class='muted'>No active tenant leases on file.</li>"}
      </ul>
      <h4>DD findings</h4>
      <ul class="deal-list">
        {"".join(f"<li><span class='sev sev-{f['severity']}'>{f['severity']}</span><span>{f['summary']}</span></li>" for f in findings) or "<li class='muted'>No findings yet — try running the Doc Room Auditor.</li>"}
      </ul>
      <div class="deal-desc">{prop.get('description') or ''}</div>
    </div>
    """

    bubbles = [message_bubble(m["role"], m["content"], m.get("agent_slug")) for m in messages]
    hidden_slug = Input(type="hidden", id="deal-slug", value=slug)

    body = Body(
        signin_overlay(),
        Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
        left_pane(user_email=email, sessions=sessions,
                  current_sid=str(session_id) if session_id else "",
                  current_path="/app/pipeline"),
        Div(
            Div(
                Div(
                    Button("☰", cls="mobile-menu-btn", onclick="toggleLeftPane()"),
                    A("← Pipeline", href="/app/pipeline", cls="back-to-chat-btn"),
                    Span("·", cls="chat-header-dot"),
                    Span(prop["name"], cls="chat-header-title"),
                    Span("·", cls="chat-header-dot"),
                    Span(stage, cls="chat-header-agent"),
                    cls="chat-header-left",
                ),
                Div(
                    Button("Artifact", id="artifact-btn", cls="artifact-toggle-btn active",
                           onclick="toggleArtifactPane()"),
                    cls="chat-header-actions",
                ),
                cls="chat-header",
            ),
            Div(*bubbles, id="messages", cls="messages"),
            Div(
                Div(
                    P(f"Ask about {prop['name']} — the deal brief is on the right. "
                      "Try 'triage this deal', 'draft IC memo', or 'summarize DD findings'.",
                      cls="text-sm"),
                    cls="deal-chat-hint",
                ) if not bubbles else Div(id="welcome-hero", style="display:none"),
                id="welcome-wrap",
            ),
            Form(
                hidden_slug,
                Textarea(
                    id="chat-input", name="msg",
                    cls="chat-textarea",
                    placeholder=f"Ask about {prop['name']} — triage, pro forma, DD summary…",
                    rows="2",
                    onkeydown="handleKey(event)",
                    oninput="autoResize(this); onInputChange(this)",
                ),
                Button("Send", type="submit", cls="chat-send", id="send-btn"),
                id="chat-form",
                cls="chat-form",
                onsubmit="sendMessage(event)",
            ),
            sample_cards(),
            cls="center-pane",
        ),
        Div(
            Div(
                Div(H3("Deal brief", cls="right-title"),
                    Span(prop["name"], id="artifact-subtitle", cls="right-subtitle"),
                    cls="right-header-left"),
                Button("✕", cls="right-close", onclick="toggleArtifactPane()"),
                cls="right-header",
            ),
            Div(
                Div(id="artifact-empty", cls="artifact-empty", style="display:none"),
                Div(NotStr(brief_html), id="artifact-body", cls="artifact-body"),
                cls="right-body",
            ),
            id="right-pane", cls="right-pane open",
        ),
        NotStr(f'<script id="agent-prompts-data" type="application/json">{json.dumps({a.slug: list(a.example_prompts[:6]) for a in AGENTS})}</script>'),
        NotStr(f'<script id="agent-names-data" type="application/json">{json.dumps({a.slug: a.name for a in AGENTS})}</script>'),
        Script(src="/static/chat.js"),
        cls="bg-bg text-ink font-sans antialiased app",
    )
    return Html(_pipeline_head(prop["name"]), body, lang="en")
