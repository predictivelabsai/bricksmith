-- Bricksmith OLTP schema. Idempotent. Always qualify with `bricksmith.` —
-- never rely on `search_path`.

CREATE SCHEMA IF NOT EXISTS bricksmith;

-- ── users + sessions ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bricksmith.users (
    id          BIGSERIAL PRIMARY KEY,
    email       TEXT        NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bricksmith.chat_sessions (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT      NOT NULL REFERENCES bricksmith.users(id) ON DELETE CASCADE,
    agent_slug   TEXT,
    title        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chat_sessions_user_idx ON bricksmith.chat_sessions(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS bricksmith.chat_messages (
    id          BIGSERIAL PRIMARY KEY,
    session_id  BIGINT NOT NULL REFERENCES bricksmith.chat_sessions(id) ON DELETE CASCADE,
    role        TEXT   NOT NULL,   -- user | assistant | tool | system
    content     TEXT   NOT NULL,
    tool_calls  JSONB,
    agent_slug  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chat_messages_session_idx ON bricksmith.chat_messages(session_id, id);

-- ── property + CRE core ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bricksmith.properties (
    id             BIGSERIAL PRIMARY KEY,
    slug           TEXT UNIQUE NOT NULL,
    name           TEXT NOT NULL,
    address        TEXT,
    city           TEXT,
    state          TEXT,
    zip            TEXT,
    metro          TEXT,
    asset_type     TEXT NOT NULL,    -- multifamily | office | industrial | retail
    submarket      TEXT,
    units          INTEGER,
    year_built     INTEGER,
    year_renovated INTEGER,
    sqft           BIGINT,
    land_sqft      BIGINT,
    occupancy_pct  NUMERIC(5,2),
    asking_price   NUMERIC(14,2),
    description    TEXT,
    listing_status TEXT,             -- on_market | off_market | closed
    seller_intent  TEXT,             -- cold | warm | hot
    deal_stage     TEXT,             -- sourced|screened|loi|psa|diligence|committee|closing|closed|held|exited
    ownership      TEXT,             -- institutional|private|family_office|reit|developer|jv
    noi_annual     NUMERIC(14,2),    -- stabilized / in-place annualized NOI
    cap_rate       NUMERIC(5,2),     -- implied cap rate on asking_price
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Additive, idempotent alters for clusters seeded before these columns existed:
ALTER TABLE bricksmith.properties ADD COLUMN IF NOT EXISTS deal_stage TEXT;
ALTER TABLE bricksmith.properties ADD COLUMN IF NOT EXISTS ownership  TEXT;
ALTER TABLE bricksmith.properties ADD COLUMN IF NOT EXISTS noi_annual NUMERIC(14,2);
ALTER TABLE bricksmith.properties ADD COLUMN IF NOT EXISTS cap_rate   NUMERIC(5,2);

CREATE INDEX IF NOT EXISTS properties_metro_idx  ON bricksmith.properties(metro);
CREATE INDEX IF NOT EXISTS properties_type_idx   ON bricksmith.properties(asset_type);
CREATE INDEX IF NOT EXISTS properties_status_idx ON bricksmith.properties(listing_status);
CREATE INDEX IF NOT EXISTS properties_stage_idx  ON bricksmith.properties(deal_stage);

CREATE TABLE IF NOT EXISTS bricksmith.rent_rolls (
    id           BIGSERIAL PRIMARY KEY,
    property_id  BIGINT      NOT NULL REFERENCES bricksmith.properties(id) ON DELETE CASCADE,
    as_of_date   DATE        NOT NULL,
    units        JSONB       NOT NULL,    -- [{unit, type, sqft, tenant, rent, lease_start, lease_end, status}]
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (property_id, as_of_date)
);

CREATE TABLE IF NOT EXISTS bricksmith.t12_statements (
    id           BIGSERIAL PRIMARY KEY,
    property_id  BIGINT      NOT NULL REFERENCES bricksmith.properties(id) ON DELETE CASCADE,
    month        DATE        NOT NULL,    -- first-of-month
    gross_rent   NUMERIC(14,2),
    other_income NUMERIC(14,2),
    vacancy_loss NUMERIC(14,2),
    opex         JSONB,                    -- {taxes, insurance, utilities, maintenance, payroll, mgmt, other}
    noi          NUMERIC(14,2),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (property_id, month)
);
CREATE INDEX IF NOT EXISTS t12_property_month_idx ON bricksmith.t12_statements(property_id, month DESC);

CREATE TABLE IF NOT EXISTS bricksmith.leases (
    id           BIGSERIAL PRIMARY KEY,
    property_id  BIGINT NOT NULL REFERENCES bricksmith.properties(id) ON DELETE CASCADE,
    unit         TEXT,
    tenant       TEXT,
    unit_type    TEXT,
    sqft         INTEGER,
    start_date   DATE,
    end_date     DATE,
    base_rent    NUMERIC(14,2),
    escalations  JSONB,        -- [{date, pct | amount}]
    options      JSONB,        -- renewal options
    status       TEXT,         -- active | expired | pending
    doc_path     TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS leases_property_idx ON bricksmith.leases(property_id);
CREATE INDEX IF NOT EXISTS leases_tenant_idx   ON bricksmith.leases(tenant);

CREATE TABLE IF NOT EXISTS bricksmith.comps_sales (
    id           BIGSERIAL PRIMARY KEY,
    property_id  BIGINT REFERENCES bricksmith.properties(id) ON DELETE SET NULL,
    comp_name    TEXT,
    city         TEXT,
    state        TEXT,
    asset_type   TEXT,
    sqft         BIGINT,
    units        INTEGER,
    sale_date    DATE,
    sale_price   NUMERIC(14,2),
    cap_rate     NUMERIC(5,2),
    price_per_unit NUMERIC(14,2),
    price_per_sqft NUMERIC(10,2),
    source       TEXT
);
CREATE INDEX IF NOT EXISTS comps_sales_property_idx ON bricksmith.comps_sales(property_id);

CREATE TABLE IF NOT EXISTS bricksmith.comps_rents (
    id           BIGSERIAL PRIMARY KEY,
    property_id  BIGINT REFERENCES bricksmith.properties(id) ON DELETE SET NULL,
    comp_name    TEXT,
    unit_type    TEXT,
    sqft         INTEGER,
    rent         NUMERIC(10,2),
    rent_per_sqft NUMERIC(10,2),
    effective_date DATE,
    source       TEXT
);
CREATE INDEX IF NOT EXISTS comps_rents_property_idx ON bricksmith.comps_rents(property_id);

CREATE TABLE IF NOT EXISTS bricksmith.pro_formas (
    id           BIGSERIAL PRIMARY KEY,
    property_id  BIGINT NOT NULL REFERENCES bricksmith.properties(id) ON DELETE CASCADE,
    name         TEXT,
    assumptions  JSONB NOT NULL,  -- {hold_years, purchase_price, rent_growth, vacancy, expense_growth, exit_cap, …}
    projections  JSONB NOT NULL,  -- [{year, revenue, opex, noi, capex, cash_flow}]
    returns      JSONB NOT NULL,  -- {irr, coc, moic, dscr, ltv, equity_multiple}
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bricksmith.debt_stacks (
    id           BIGSERIAL PRIMARY KEY,
    property_id  BIGINT NOT NULL REFERENCES bricksmith.properties(id) ON DELETE CASCADE,
    name         TEXT,
    tranches     JSONB NOT NULL,  -- [{name, lender, amount, rate, amort_years, term_years, io_years, type}]
    ltv          NUMERIC(5,2),
    dscr         NUMERIC(5,2),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bricksmith.investor_crm (
    id           BIGSERIAL PRIMARY KEY,
    name         TEXT NOT NULL,
    firm         TEXT,
    email        TEXT,
    check_size   NUMERIC(14,2),
    stage        TEXT,          -- cold | qualified | meeting | committed | closed | passed
    focus        TEXT,          -- multifamily | office | mixed | industrial | retail
    geography    TEXT,
    last_touch   DATE,
    notes        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS crm_stage_idx ON bricksmith.investor_crm(stage);

CREATE TABLE IF NOT EXISTS bricksmith.market_signals (
    id           BIGSERIAL PRIMARY KEY,
    metro        TEXT NOT NULL,
    asset_type   TEXT,
    metric       TEXT NOT NULL,   -- cap_rate | absorption | employment | rent_growth | vacancy
    value        NUMERIC(14,4),
    as_of_date   DATE NOT NULL,
    source       TEXT,
    UNIQUE (metro, asset_type, metric, as_of_date)
);
CREATE INDEX IF NOT EXISTS market_signals_lookup_idx ON bricksmith.market_signals(metro, metric, as_of_date DESC);

CREATE TABLE IF NOT EXISTS bricksmith.dd_findings (
    id           BIGSERIAL PRIMARY KEY,
    property_id  BIGINT NOT NULL REFERENCES bricksmith.properties(id) ON DELETE CASCADE,
    agent_slug   TEXT NOT NULL,
    category     TEXT NOT NULL,   -- title | zoning | physical | environmental | lease | ops
    severity     TEXT NOT NULL,   -- info | low | medium | high | critical
    summary      TEXT NOT NULL,
    detail       TEXT,
    source_doc   TEXT,
    source_page  INTEGER,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS dd_property_idx ON bricksmith.dd_findings(property_id, severity);

CREATE TABLE IF NOT EXISTS bricksmith.agent_invocations (
    id           BIGSERIAL PRIMARY KEY,
    session_id   BIGINT REFERENCES bricksmith.chat_sessions(id) ON DELETE CASCADE,
    agent_slug   TEXT NOT NULL,
    input        TEXT,
    tools_used   TEXT[],
    duration_ms  INTEGER,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS agent_invocations_session_idx ON bricksmith.agent_invocations(session_id, created_at DESC);
