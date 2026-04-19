"""Seed the Bricksmith databases with synthetic CRE data.

Usage:
    python -m synthetic.generate                  # seed=42, ~40 properties, indexes RAG
    python -m synthetic.generate --seed 7
    python -m synthetic.generate --skip-rag       # OLTP only
    python -m synthetic.generate --limit 5        # small subset for quick testing
    python -m synthetic.generate --fresh          # truncates tables first (safer than --drop)
"""

from __future__ import annotations

import argparse
import json
import logging
import random
from datetime import date

from dateutil.relativedelta import relativedelta

from db import connect
from rag.indexer import DocIn, upsert_documents, build_ann_index
from synthetic import properties as P
from synthetic import rent_rolls as RR
from synthetic import t12s as T12
from synthetic import comps as CMP
from synthetic import market_signals as MS
from synthetic import lps as LP
from synthetic import leases as LEASE
from synthetic import documents as DOC

log = logging.getLogger(__name__)

TRUNCATE_TABLES = [
    "bricksmith.agent_invocations",
    "bricksmith.dd_findings",
    "bricksmith.market_signals",
    "bricksmith.investor_crm",
    "bricksmith.debt_stacks",
    "bricksmith.pro_formas",
    "bricksmith.comps_rents",
    "bricksmith.comps_sales",
    "bricksmith.leases",
    "bricksmith.t12_statements",
    "bricksmith.rent_rolls",
    "bricksmith.properties",
    # chat left alone to preserve user sessions across reseed
]


def _truncate():
    with connect() as conn, conn.cursor() as cur:
        for t in TRUNCATE_TABLES:
            cur.execute(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE")
        cur.execute("TRUNCATE TABLE bricksmith_rag.rag_queries RESTART IDENTITY")
        cur.execute("TRUNCATE TABLE bricksmith_rag.embeddings RESTART IDENTITY")
        cur.execute("TRUNCATE TABLE bricksmith_rag.chunks RESTART IDENTITY CASCADE")
        cur.execute("TRUNCATE TABLE bricksmith_rag.documents RESTART IDENTITY CASCADE")
        conn.commit()


def _insert_properties(specs: list[dict]) -> dict[str, int]:
    slug_to_id: dict[str, int] = {}
    with connect() as conn, conn.cursor() as cur:
        for s in specs:
            cur.execute(
                """
                INSERT INTO bricksmith.properties
                  (slug, name, address, city, state, zip, metro, asset_type, submarket,
                   units, year_built, year_renovated, sqft, land_sqft, occupancy_pct,
                   asking_price, description, listing_status, seller_intent,
                   deal_stage, ownership, noi_annual, cap_rate)
                VALUES (%(slug)s, %(name)s, %(address)s, %(city)s, %(state)s, %(zip)s,
                        %(metro)s, %(asset_type)s, %(submarket)s,
                        %(units)s, %(year_built)s, %(year_renovated)s, %(sqft)s, %(land_sqft)s,
                        %(occupancy_pct)s, %(asking_price)s, %(description)s,
                        %(listing_status)s, %(seller_intent)s,
                        %(deal_stage)s, %(ownership)s, %(noi_annual)s, %(cap_rate)s)
                ON CONFLICT (slug) DO UPDATE SET
                  name           = EXCLUDED.name,
                  description    = EXCLUDED.description,
                  asking_price   = EXCLUDED.asking_price,
                  listing_status = EXCLUDED.listing_status,
                  seller_intent  = EXCLUDED.seller_intent,
                  deal_stage     = EXCLUDED.deal_stage,
                  ownership      = EXCLUDED.ownership,
                  noi_annual     = EXCLUDED.noi_annual,
                  cap_rate       = EXCLUDED.cap_rate
                RETURNING id, slug
                """,
                s,
            )
            row = cur.fetchone()
            slug_to_id[row[1]] = row[0]
        conn.commit()
    return slug_to_id


def _insert_rent_rolls(props_with_ids: list[tuple[int, dict]], rng: random.Random) -> int:
    n = 0
    as_of = date.today().replace(day=1)
    with connect() as conn, conn.cursor() as cur:
        for pid, prop in props_with_ids:
            units = RR.generate_for_property(prop, as_of, rng)
            cur.execute(
                """
                INSERT INTO bricksmith.rent_rolls (property_id, as_of_date, units)
                VALUES (%s, %s, %s::jsonb)
                ON CONFLICT (property_id, as_of_date) DO UPDATE SET units = EXCLUDED.units
                """,
                (pid, as_of, json.dumps(units)),
            )
            # mirror into leases table (active only) for easy querying
            cur.execute("DELETE FROM bricksmith.leases WHERE property_id = %s", (pid,))
            for u in units:
                if u.get("status") != "active":
                    continue
                cur.execute(
                    """
                    INSERT INTO bricksmith.leases
                      (property_id, unit, tenant, unit_type, sqft, start_date, end_date,
                       base_rent, escalations, status)
                    VALUES (%s, %s, %s, %s, %s, %s::date, %s::date, %s, %s::jsonb, %s)
                    """,
                    (pid, u.get("unit"), u.get("tenant"), u.get("type"), u.get("sqft"),
                     u.get("lease_start"), u.get("lease_end"), u.get("rent"),
                     json.dumps([{"date": u.get("lease_start"), "pct": 3.0}] if u.get("lease_start") else []),
                     u.get("status")),
                )
            n += 1
        conn.commit()
    return n


def _insert_t12(props_with_ids: list[tuple[int, dict]], rng: random.Random) -> int:
    n = 0
    end_month = date.today().replace(day=1) - relativedelta(months=1)
    with connect() as conn, conn.cursor() as cur:
        for pid, prop in props_with_ids:
            rows = T12.generate_for_property(prop, end_month, rng)
            for r in rows:
                cur.execute(
                    """
                    INSERT INTO bricksmith.t12_statements
                      (property_id, month, gross_rent, other_income, vacancy_loss, opex, noi)
                    VALUES (%s, %s::date, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT (property_id, month) DO UPDATE SET
                      gross_rent   = EXCLUDED.gross_rent,
                      other_income = EXCLUDED.other_income,
                      vacancy_loss = EXCLUDED.vacancy_loss,
                      opex         = EXCLUDED.opex,
                      noi          = EXCLUDED.noi
                    """,
                    (pid, r["month"], r["gross_rent"], r["other_income"], r["vacancy_loss"],
                     json.dumps(r["opex"]), r["noi"]),
                )
                n += 1
        conn.commit()
    return n


def _insert_comps(props_with_ids: list[tuple[int, dict]], rng: random.Random) -> tuple[int, int]:
    s = r = 0
    with connect() as conn, conn.cursor() as cur:
        for pid, prop in props_with_ids:
            for c in CMP.generate_sales_comps(prop, rng):
                cur.execute(
                    """
                    INSERT INTO bricksmith.comps_sales
                      (property_id, comp_name, city, state, asset_type, sqft, units,
                       sale_date, sale_price, cap_rate, price_per_unit, price_per_sqft, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::date, %s, %s, %s, %s, %s)
                    """,
                    (pid, c["comp_name"], c["city"], c["state"], c["asset_type"], c["sqft"],
                     c.get("units"), c["sale_date"], c["sale_price"], c["cap_rate"],
                     c.get("price_per_unit"), c["price_per_sqft"], c["source"]),
                )
                s += 1
            for c in CMP.generate_rent_comps(prop, rng):
                cur.execute(
                    """
                    INSERT INTO bricksmith.comps_rents
                      (property_id, comp_name, unit_type, sqft, rent, rent_per_sqft,
                       effective_date, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::date, %s)
                    """,
                    (pid, c["comp_name"], c["unit_type"], c["sqft"], c["rent"],
                     c["rent_per_sqft"], c["effective_date"], c["source"]),
                )
                r += 1
        conn.commit()
    return s, r


def _insert_market_signals(rows: list[dict]) -> int:
    with connect() as conn, conn.cursor() as cur:
        for r in rows:
            cur.execute(
                """
                INSERT INTO bricksmith.market_signals
                  (metro, asset_type, metric, value, as_of_date, source)
                VALUES (%s, %s, %s, %s, %s::date, %s)
                ON CONFLICT (metro, asset_type, metric, as_of_date) DO UPDATE SET
                  value = EXCLUDED.value, source = EXCLUDED.source
                """,
                (r["metro"], r["asset_type"], r["metric"], r["value"], r["as_of_date"], r["source"]),
            )
        conn.commit()
    return len(rows)


def _insert_lps(rows: list[dict]) -> int:
    with connect() as conn, conn.cursor() as cur:
        for r in rows:
            cur.execute(
                """
                INSERT INTO bricksmith.investor_crm
                  (name, firm, email, check_size, stage, focus, geography, last_touch, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::date, %s)
                """,
                (r["name"], r["firm"], r["email"], r["check_size"], r["stage"], r["focus"],
                 r["geography"], r["last_touch"], r["notes"]),
            )
        conn.commit()
    return len(rows)


def _index_rag(props_with_ids: list[tuple[int, dict]], rng: random.Random) -> int:
    """Index leases (1 per property) + zoning/env/pcr/title per property + market reports."""
    docs: list[DocIn] = []

    # One representative lease per property
    for pid, prop in props_with_ids:
        # find first active commercial unit with tenant (or make one up for MF)
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT units FROM bricksmith.rent_rolls WHERE property_id = %s ORDER BY as_of_date DESC LIMIT 1",
                (pid,),
            )
            row = cur.fetchone()
        if not row:
            continue
        units = row[0]
        active_units = [u for u in units if u.get("status") == "active" and u.get("tenant")]
        if not active_units:
            continue
        # sample up to 2 for MF (less variety needed), 1 for commercial
        sample_count = 2 if prop["asset_type"] == "multifamily" else 1
        for unit in rng.sample(active_units, min(sample_count, len(active_units))):
            body = LEASE.generate_lease_body(prop=prop, unit=unit, rng=rng)
            docs.append(DocIn(
                title=f"Lease — {prop['name']} {unit.get('unit')}",
                doc_type="lease",
                text=body,
                property_id=pid,
                metadata={"tenant": unit.get("tenant"), "unit": unit.get("unit"),
                          "sqft": unit.get("sqft"), "asset_type": prop["asset_type"]},
            ))

    # DD docs per property
    for pid, prop in props_with_ids:
        for d in DOC.generate_all_for_property(prop, rng):
            docs.append(DocIn(
                title=d["title"],
                doc_type=d["doc_type"],
                text=d["text"],
                property_id=pid,
                metadata={"asset_type": prop["asset_type"], "city": prop["city"]},
            ))

    # Market reports (one per metro + asset type)
    for d in DOC.generate_market_reports([p for _, p in props_with_ids], rng):
        docs.append(DocIn(
            title=d["title"],
            doc_type=d["doc_type"],
            text=d["text"],
            metadata={},
        ))

    log.info("embedding + upserting %d documents", len(docs))
    ids = upsert_documents(docs, replace=False)
    return len(ids)


def run(seed: int = 42, skip_rag: bool = False, limit: int | None = None, fresh: bool = False) -> None:
    if fresh:
        print("truncating bricksmith tables (preserving chat history)…")
        _truncate()

    rng = random.Random(seed)
    specs = P.generate(seed=seed)
    if limit:
        specs = specs[:limit]
    print(f"generated {len(specs)} properties")

    slug_to_id = _insert_properties(specs)
    props_with_ids = [(slug_to_id[s["slug"]], s) for s in specs]

    n = _insert_rent_rolls(props_with_ids, rng)
    print(f"inserted rent rolls for {n} properties")

    n = _insert_t12(props_with_ids, rng)
    print(f"inserted {n} T12 month rows")

    s, r = _insert_comps(props_with_ids, rng)
    print(f"inserted {s} sales comps, {r} rent comps")

    ms_rows = MS.generate([p for _, p in props_with_ids], seed=seed)
    n = _insert_market_signals(ms_rows)
    print(f"inserted {n} market signal rows")

    n = _insert_lps(LP.generate(count=60, seed=seed))
    print(f"inserted {n} LP contacts")

    if not skip_rag:
        n = _index_rag(props_with_ids, rng)
        print(f"indexed {n} RAG documents")
        build_ann_index()

    print("done")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--skip-rag", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--fresh", action="store_true", help="truncate tables before seeding")
    args = ap.parse_args()
    run(seed=args.seed, skip_rag=args.skip_rag, limit=args.limit, fresh=args.fresh)
