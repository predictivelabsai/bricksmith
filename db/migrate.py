"""Apply schema.sql + rag_schema.sql idempotently.

Usage:
    python -m db.migrate          # apply both
    python -m db.migrate --drop   # DANGER: drops bricksmith schemas first
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from db import connect
from utils.config import settings

log = logging.getLogger(__name__)

SCHEMA_FILES = [
    Path(__file__).with_name("schema.sql"),
    Path(__file__).with_name("rag_schema.sql"),
]


def _apply(sql: str) -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql)
        conn.commit()


def _render(path: Path) -> str:
    text = path.read_text()
    return text.replace("{{EMBEDDING_DIM}}", str(settings().embedding_dim))


def _seed_prompt_versions() -> None:
    """Insert v1 rows for every prompt file if the table is empty."""
    prompts_dir = Path(__file__).resolve().parent.parent / "prompts"
    system_dir = prompts_dir / "system"
    shared_file = prompts_dir / "shared" / "cre_context.md"

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM bricksmith.prompt_versions")
        if cur.fetchone()[0] > 0:
            return

        seeded = 0
        for md in sorted(system_dir.glob("*.md")):
            slug = md.stem
            content = md.read_text()
            cur.execute(
                "INSERT INTO bricksmith.prompt_versions (slug, content, changed_by) "
                "VALUES (%s, %s, %s)",
                (slug, content, "seed"),
            )
            seeded += 1

        if shared_file.exists():
            cur.execute(
                "INSERT INTO bricksmith.prompt_versions (slug, content, changed_by) "
                "VALUES (%s, %s, %s)",
                ("__shared__", shared_file.read_text(), "seed"),
            )
            seeded += 1

        conn.commit()
        print(f"seeded {seeded} prompt versions")


def migrate(drop: bool = False) -> None:
    if drop:
        print("dropping bricksmith + bricksmith_rag schemas…")
        _apply("DROP SCHEMA IF EXISTS bricksmith_rag CASCADE; DROP SCHEMA IF EXISTS bricksmith CASCADE;")

    for f in SCHEMA_FILES:
        print(f"applying {f.name} (embedding_dim={settings().embedding_dim})")
        _apply(_render(f))

    _seed_prompt_versions()
    print("migration complete")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--drop", action="store_true", help="drop bricksmith schemas first")
    args = ap.parse_args()
    migrate(drop=args.drop)
