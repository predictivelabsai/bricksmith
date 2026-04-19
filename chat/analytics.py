"""Analytics page — natural-language → SQL over bricksmith.*, rendered as Plotly.

/app/analytics           → text input + 8 example prompts
POST /app/analytics/run  → returns JSON {sql, title, figure, rows, table}

Uses Grok to draft SQL against a hand-curated schema snippet, runs read-only,
and picks a sensible chart (bar|line|scatter|pie) based on the model spec.
"""

from __future__ import annotations

import json
import logging
import re

import pandas as pd
import plotly.express as px
from fasthtml.common import (
    Html, Head, Body, Meta, Title, Link, Script, NotStr,
    Div, Span, H2, P, A, Button, Form, Input,
)
from starlette.requests import Request
from starlette.responses import JSONResponse

from app import rt
from chat.components import left_pane, signin_overlay
from chat.routes import _ensure_user, _list_sessions
from db import connect
from utils.llm import build_llm

log = logging.getLogger(__name__)


SCHEMA_SNIPPET = """\
-- Bricksmith read-only PostgreSQL schema — target tables to query.
-- Schemas are `bricksmith` (OLTP) and `bricksmith_rag` (embedded docs).
-- ONLY generate SELECT queries. Use schema-qualified names.

bricksmith.properties (
    id, slug, name, address, city, state, metro, asset_type,
    -- asset_type ∈ multifamily | office | industrial | retail
    submarket, units, year_built, year_renovated, sqft, land_sqft,
    occupancy_pct, asking_price, listing_status,
    -- listing_status ∈ on_market | off_market | closed
    seller_intent,   -- cold | warm | hot
    deal_stage,      -- sourced|screened|loi|psa|diligence|committee|closing|closed|held|exited
    ownership,       -- institutional|private|family_office|reit|developer|jv
    noi_annual, cap_rate
)

bricksmith.t12_statements (
    property_id, month DATE, gross_rent, other_income, vacancy_loss,
    opex JSONB, noi
)

bricksmith.rent_rolls (property_id, as_of_date DATE, units JSONB)

bricksmith.leases (
    property_id, unit, tenant, unit_type, sqft,
    start_date, end_date, base_rent, status
)

bricksmith.comps_sales (
    property_id, comp_name, city, state, asset_type, sqft, units,
    sale_date, sale_price, cap_rate, price_per_unit, price_per_sqft
)

bricksmith.comps_rents (
    property_id, comp_name, unit_type, sqft, rent, rent_per_sqft, effective_date
)

bricksmith.market_signals (
    metro, asset_type, metric,
    -- metric ∈ cap_rate | absorption | employment | rent_growth | vacancy
    value, as_of_date
)

bricksmith.investor_crm (
    name, firm, email, check_size, stage, focus, geography, last_touch
)

bricksmith.dd_findings (property_id, agent_slug, category, severity, summary)
bricksmith.pro_formas (property_id, name, assumptions JSONB, projections JSONB, returns JSONB)
bricksmith.debt_stacks (property_id, name, tranches JSONB, ltv, dscr)
"""


SAMPLE_QUERIES = [
    "Property count by deal stage",
    "Median cap rate by asset type",
    "Top 10 properties by NOI, show asset type",
    "Cap rate trend by metro over last 24 months",
    "LP check size distribution by stage",
    "Monthly NOI trend for Parkline Downtown",
    "Sales comps volume by state, last 18 months",
    "DD findings severity breakdown by category",
]


SYSTEM = f"""You translate plain-English questions into a single PostgreSQL SELECT
query against the Bricksmith schema below, and suggest a chart.

Rules:
- Return ONLY a JSON object with exactly these keys:
  {{ "sql": "...", "chart": "bar|line|scatter|pie|none", "x": "...", "y": "...", "color": "...", "title": "..." }}
- Never modify data. SELECT (or WITH … SELECT) only.
- Use schema-qualified names (bricksmith.properties, bricksmith.t12_statements, etc).
- Limit results sensibly (≤200 rows) unless a time-series needs more.
- For time series, order by the time column.
- For percentages that are already in percent (cap_rate, occupancy_pct), don't multiply.

Schema:
{SCHEMA_SNIPPET}
"""


def _draft_sql(question: str) -> dict:
    llm = build_llm()
    resp = llm.invoke(f"{SYSTEM}\n\nQuestion: {question}\n\nJSON:").content
    m = re.search(r"\{.*\}", resp, re.DOTALL)
    if not m:
        raise ValueError(f"No JSON in model response: {resp[:400]}")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise ValueError(f"Bad JSON from model: {e} — {resp[:400]}")


def _guard_sql(sql: str) -> None:
    s = sql.strip().rstrip(";").strip()
    lowered = s.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise ValueError("Only SELECT / WITH queries are allowed.")
    banned = ["insert ", "update ", "delete ", "drop ", "truncate ",
              "alter ", "grant ", "revoke ", "create ", "copy ", ";"]
    for b in banned:
        if b in lowered:
            raise ValueError(f"Disallowed keyword in SQL: {b.strip()}")


def _run_sql(sql: str) -> pd.DataFrame:
    _guard_sql(sql)
    # Use the psycopg3 pool directly (pandas' DB-API path) — the SQLAlchemy
    # engine defaults to psycopg2 when the URL starts with `postgresql://`,
    # which we don't ship.
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [d.name for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        return pd.DataFrame(rows, columns=cols)


def _chart_for(df: pd.DataFrame, spec: dict) -> dict | None:
    if df.empty:
        return None
    kind = (spec.get("chart") or "").lower()
    x = spec.get("x"); y = spec.get("y")
    color = spec.get("color") or None
    title = spec.get("title") or ""

    cols = list(df.columns)
    if x and x not in cols:
        x = cols[0]
    if y and y not in cols:
        y = next((c for c in cols[1:] if pd.api.types.is_numeric_dtype(df[c])), cols[-1])
    if color and color not in cols:
        color = None
    if not x:
        x = cols[0]
    if not y and len(cols) > 1:
        y = cols[1]

    try:
        if kind == "bar":
            fig = px.bar(df, x=x, y=y, color=color, title=title, barmode="group")
        elif kind == "line":
            fig = px.line(df, x=x, y=y, color=color, title=title, markers=True)
        elif kind == "scatter":
            fig = px.scatter(df, x=x, y=y, color=color, title=title)
        elif kind == "pie":
            fig = px.pie(df, names=x, values=y, title=title)
        else:
            return None
    except Exception as e:  # noqa: BLE001
        log.warning("plotly failed: %s", e)
        return None

    # Dark theme — matches bricksmith app.css palette
    fig.update_layout(
        paper_bgcolor="#111A2E",
        plot_bgcolor="#0B1220",
        font=dict(family="Inter, system-ui", color="#F5F5F7"),
        margin=dict(l=40, r=20, t=50, b=40),
        title=dict(font=dict(size=15)),
        xaxis=dict(gridcolor="#1F2E4F"),
        yaxis=dict(gridcolor="#1F2E4F"),
    )
    return json.loads(fig.to_json())


def _head(title: str) -> Head:
    return Head(
        Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Title(f"{title} · Bricksmith"),
        Link(rel="preconnect", href="https://fonts.googleapis.com"),
        Link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
        Link(rel="stylesheet",
             href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"),
        Script(src="https://cdn.plot.ly/plotly-2.35.2.min.js"),
        Link(rel="stylesheet", href="/static/site.css"),
        Link(rel="stylesheet", href="/static/app.css"),
        Link(rel="stylesheet", href="/static/pipeline.css"),
    )


@rt("/app/analytics")
def analytics_home(sess):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []

    suggestions = Div(
        *[Button(q, cls="analytics-sugg", onclick=f"runAnalytics({q!r})")
          for q in SAMPLE_QUERIES],
        cls="analytics-suggestions",
    )

    body = Body(
        signin_overlay(),
        Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
        left_pane(user_email=email, sessions=sessions, current_sid="",
                  current_path="/app/analytics"),
        Div(
            Div(
                Div(
                    Button("☰", cls="mobile-menu-btn", onclick="toggleLeftPane()"),
                    Span("Analytics", cls="chat-header-title"),
                    Span("·", cls="chat-header-dot"),
                    Span("Text → SQL → Plotly", cls="chat-header-agent"),
                    cls="chat-header-left",
                ),
                Div(A("Back to chat", href="/app", cls="back-to-chat-btn"),
                    cls="chat-header-actions"),
                cls="chat-header",
            ),
            Div(
                Div(
                    H2("Ask a question of your CRE database.", cls="text-ink"),
                    P("Questions are translated to SQL against the bricksmith schema, run read-only, "
                      "and rendered as a Plotly chart plus the raw table.",
                      cls="text-ink-muted"),
                    cls="analytics-hero",
                ),
                Form(
                    Input(type="text", id="analytics-q", name="q",
                          placeholder="e.g. Median cap rate by asset type",
                          onkeydown="if(event.key==='Enter'){event.preventDefault();runAnalytics()}"),
                    Button("Run", type="button", onclick="runAnalytics()"),
                    cls="analytics-form",
                ),
                suggestions,
                Div(id="analytics-result"),
                cls="analytics-wrap",
            ),
            cls="center-pane",
        ),
        Script(NotStr("""
            async function runAnalytics(q) {
                if (q) document.getElementById('analytics-q').value = q;
                const question = document.getElementById('analytics-q').value.trim();
                const out = document.getElementById('analytics-result');
                if (!question) return;
                out.innerHTML = '<div class="analytics-result"><div class="muted">Thinking…</div></div>';
                const r = await fetch('/app/analytics/run', {
                    method: 'POST',
                    body: new URLSearchParams({ q: question })
                });
                const data = await r.json();
                if (data.error) {
                    out.innerHTML = `<div class="analytics-error"><strong>Error:</strong> ${data.error}<br><pre style="margin-top:.5rem;font-size:.7rem;overflow-x:auto">${data.sql || ''}</pre></div>`;
                    return;
                }
                const chartId = 'chart-' + Math.random().toString(36).slice(2, 8);
                const tableHtml = data.table
                    ? `<div class="analytics-table-wrap">${data.table}</div>` : '';
                out.innerHTML = `
                    <div class="analytics-result">
                        <h3>${data.title || question}</h3>
                        <div class="sql">${data.sql}</div>
                        <div id="${chartId}" class="analytics-chart"></div>
                        ${tableHtml}
                    </div>`;
                if (data.figure) {
                    Plotly.newPlot(chartId, data.figure.data, data.figure.layout, {responsive: true});
                } else {
                    document.getElementById(chartId).innerHTML = '<p class="text-ink-muted text-sm">(No chart — showing table only.)</p>';
                }
            }
            window.runAnalytics = runAnalytics;
        """)),
        Script(src="/static/chat.js"),
        cls="bg-bg text-ink font-sans antialiased app pane-closed pipeline-app",
    )
    return Html(_head("Analytics"), body, lang="en")


@rt("/app/analytics/run", methods=["POST"])
async def analytics_run(request: Request):
    form = await request.form()
    q = (form.get("q") or "").strip()
    if not q:
        return JSONResponse({"error": "Empty question."})

    try:
        spec = _draft_sql(q)
        sql = spec.get("sql", "").strip().rstrip(";")
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"LLM couldn't draft SQL: {e}"})

    try:
        df = _run_sql(sql)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"SQL failed: {e}", "sql": sql})

    fig = _chart_for(df, spec)
    table_html = df.head(50).to_html(
        index=False, classes="artifact-table", border=0,
        float_format=lambda x: f"{x:,.2f}" if isinstance(x, float) else str(x),
    )

    return JSONResponse({
        "sql": sql,
        "title": spec.get("title") or q,
        "figure": fig,
        "rows": len(df),
        "table": table_html,
    })
