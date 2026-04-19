"""Due diligence tools — abstract leases, audit doc rooms, check title/zoning/environmental."""

from __future__ import annotations

import json
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from db import connect, fetch_all, fetch_one
from rag.retriever import retrieve


class AbstractLeaseArgs(BaseModel):
    slug_or_id: Optional[str] = Field(default=None, description="Property slug or id.")
    tenant: Optional[str] = Field(default=None, description="Tenant name filter.")
    unit: Optional[str] = Field(default=None)


def _abstract_lease(**kw) -> str:
    args = AbstractLeaseArgs(**kw)
    sql = ["SELECT l.*, p.name as property_name FROM bricksmith.leases l "
           "JOIN bricksmith.properties p ON p.id = l.property_id WHERE l.status = 'active'"]
    params: list = []
    if args.slug_or_id:
        try:
            pid = int(args.slug_or_id)
            sql.append("AND l.property_id = %s"); params.append(pid)
        except (TypeError, ValueError):
            sql.append("AND p.slug = %s"); params.append(args.slug_or_id)
    if args.tenant:
        sql.append("AND l.tenant ILIKE %s"); params.append(f"%{args.tenant}%")
    if args.unit:
        sql.append("AND l.unit ILIKE %s"); params.append(f"%{args.unit}%")
    sql.append("LIMIT 10")
    rows = fetch_all(" ".join(sql), tuple(params))
    if not rows:
        return "No matching leases."
    abstracts = [
        {
            "property": r["property_name"],
            "unit": r["unit"],
            "tenant": r["tenant"],
            "unit_type": r["unit_type"],
            "sqft": r["sqft"],
            "start_date": str(r["start_date"]) if r["start_date"] else None,
            "end_date": str(r["end_date"]) if r["end_date"] else None,
            "monthly_base_rent": float(r["base_rent"]) if r["base_rent"] else None,
            "escalations": r["escalations"],
        }
        for r in rows
    ]
    return "__ARTIFACT__" + json.dumps({
        "kind": "table",
        "title": "Lease abstracts",
        "columns": ["property", "unit", "tenant", "sqft", "start_date", "end_date", "monthly_base_rent"],
        "rows": abstracts,
        "summary": {"count": len(abstracts)},
    })


abstract_leases = StructuredTool.from_function(
    func=_abstract_lease,
    name="abstract_leases",
    description="Abstract active leases into structured records — unit, tenant, term, rent, escalations. Filter by property and/or tenant name.",
    args_schema=AbstractLeaseArgs,
)


class DocRoomArgs(BaseModel):
    slug_or_id: str = Field(description="Property to audit.")


DD_CHECKLIST = [
    ("lease", "Active leases abstracted and reconciled to rent roll"),
    ("zoning", "Current zoning verification letter"),
    ("environmental", "Phase I ESA within 12 months"),
    ("pcr", "Property condition report from licensed inspector"),
    ("title", "Current title commitment with Schedule B-II exceptions"),
    ("market", "Current market report for metro + asset type"),
    ("rent_roll", "Certified rent roll as of current month"),
    ("t12", "T12 trailing-twelve-month operating statement"),
]


def _audit_doc_room(slug_or_id: str) -> str:
    try:
        pid = int(slug_or_id)
    except (TypeError, ValueError):
        row = fetch_one("SELECT id FROM bricksmith.properties WHERE slug = %s", (slug_or_id,))
        pid = row["id"] if row else None
    if not pid:
        return "Property not found."

    prop = fetch_one("SELECT name FROM bricksmith.properties WHERE id = %s", (pid,))
    # Check RAG corpus
    rag_docs = fetch_all(
        "SELECT doc_type, count(*) AS n FROM bricksmith_rag.documents "
        "WHERE property_id = %s GROUP BY doc_type",
        (pid,),
    )
    rag_counts = {r["doc_type"]: r["n"] for r in rag_docs}
    # OLTP-backed docs
    rr = fetch_one("SELECT count(*) as n FROM bricksmith.rent_rolls WHERE property_id = %s", (pid,))
    t12 = fetch_one("SELECT count(*) as n FROM bricksmith.t12_statements WHERE property_id = %s", (pid,))
    leases = fetch_one("SELECT count(*) as n FROM bricksmith.leases WHERE property_id = %s AND status='active'", (pid,))
    market = fetch_one("SELECT count(*) as n FROM bricksmith_rag.documents WHERE doc_type='market'", (pid,))

    findings = []
    for doc_type, label in DD_CHECKLIST:
        if doc_type == "lease":
            present = (leases["n"] or 0) > 0
        elif doc_type == "rent_roll":
            present = (rr["n"] or 0) > 0
        elif doc_type == "t12":
            present = (t12["n"] or 0) > 0
        elif doc_type == "market":
            present = (market["n"] or 0) > 0
        else:
            present = (rag_counts.get(doc_type, 0) > 0)
        findings.append({
            "item": label,
            "doc_type": doc_type,
            "status": "Present" if present else "Missing",
            "severity": "info" if present else "high",
        })

    rows = findings
    return "__ARTIFACT__" + json.dumps({
        "kind": "table",
        "title": f"DD room audit — {prop['name']}",
        "subtitle": f"{sum(1 for f in findings if f['status']=='Present')}/{len(findings)} items present",
        "columns": ["item", "status", "severity"],
        "rows": rows,
    })


audit_doc_room = StructuredTool.from_function(
    func=_audit_doc_room,
    name="audit_doc_room",
    description="Audit a property's data room against a DD checklist; flags missing items.",
    args_schema=DocRoomArgs,
)


class RagDocArgs(BaseModel):
    slug_or_id: str
    query: str = Field(default="")


def _check_title(slug_or_id: str, query: str = "") -> str:
    """Surface material title exceptions for a property."""
    pid = _resolve_pid(slug_or_id)
    if not pid:
        return "Property not found."
    chunks = retrieve(query or "material title exceptions Schedule B-II",
                      k=5, doc_types=["title"], property_id=pid)
    if not chunks:
        return "No title commitment indexed."
    items = [{"title": c.title, "doc_type": c.doc_type, "score": round(c.score, 3),
              "snippet": c.text[:600]} for c in chunks]
    return "__ARTIFACT__" + json.dumps({
        "kind": "citations", "title": "Title check", "items": items,
    })


def _resolve_pid(slug_or_id):
    try:
        return int(slug_or_id)
    except (TypeError, ValueError):
        row = fetch_one("SELECT id FROM bricksmith.properties WHERE slug = %s", (slug_or_id,))
        return row["id"] if row else None


check_title = StructuredTool.from_function(
    func=_check_title,
    name="check_title",
    description="Extract title commitment Schedule B-II exceptions for a property from the RAG corpus.",
    args_schema=RagDocArgs,
)


def _check_zoning(slug_or_id: str, query: str = "") -> str:
    pid = _resolve_pid(slug_or_id)
    if not pid:
        return "Property not found."
    chunks = retrieve(query or "zoning nonconformities parking overlay",
                      k=5, doc_types=["zoning"], property_id=pid)
    if not chunks:
        return "No zoning memo indexed."
    items = [{"title": c.title, "doc_type": c.doc_type, "score": round(c.score, 3),
              "snippet": c.text[:600]} for c in chunks]
    return "__ARTIFACT__" + json.dumps({
        "kind": "citations", "title": "Zoning check", "items": items,
    })


check_zoning = StructuredTool.from_function(
    func=_check_zoning,
    name="check_zoning",
    description="Pull zoning memo details for a property — zoning code, FAR, height, nonconformities, parking.",
    args_schema=RagDocArgs,
)


def _flag_environmental(slug_or_id: str, query: str = "") -> str:
    pid = _resolve_pid(slug_or_id)
    if not pid:
        return "Property not found."
    chunks = retrieve(query or "recognized environmental conditions RECs vapor intrusion",
                      k=5, doc_types=["environmental"], property_id=pid)
    if not chunks:
        return "No Phase I ESA indexed."
    items = [{"title": c.title, "doc_type": c.doc_type, "score": round(c.score, 3),
              "snippet": c.text[:600]} for c in chunks]
    return "__ARTIFACT__" + json.dumps({
        "kind": "citations", "title": "Environmental risk flags", "items": items,
    })


flag_environmental = StructuredTool.from_function(
    func=_flag_environmental,
    name="flag_environmental",
    description="Pull environmental Phase I ESA findings — RECs, adjacent-property concerns, recommended Phase II scope.",
    args_schema=RagDocArgs,
)


def _pcr_findings(slug_or_id: str, query: str = "") -> str:
    pid = _resolve_pid(slug_or_id)
    if not pid:
        return "Property not found."
    chunks = retrieve(query or "roof HVAC deferred maintenance immediate repair capex budget",
                      k=5, doc_types=["pcr"], property_id=pid)
    if not chunks:
        return "No property condition report indexed."
    items = [{"title": c.title, "doc_type": c.doc_type, "score": round(c.score, 3),
              "snippet": c.text[:600]} for c in chunks]
    return "__ARTIFACT__" + json.dumps({
        "kind": "citations", "title": "Property condition findings", "items": items,
    })


pcr_findings = StructuredTool.from_function(
    func=_pcr_findings,
    name="pcr_findings",
    description="Pull property condition report findings — roof/HVAC life, deferred maintenance, capex reserves.",
    args_schema=RagDocArgs,
)


def _record_dd_finding(property_id: int, agent_slug: str, category: str,
                       severity: str, summary: str, detail: Optional[str] = None,
                       source_doc: Optional[str] = None) -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO bricksmith.dd_findings "
            "(property_id, agent_slug, category, severity, summary, detail, source_doc) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (property_id, agent_slug, category, severity, summary, detail, source_doc),
        )
        conn.commit()


class FindingArgs(BaseModel):
    slug_or_id: str
    category: str = Field(description="lease | title | zoning | physical | environmental | ops")
    severity: str = Field(description="info | low | medium | high | critical")
    summary: str
    detail: Optional[str] = None
    source_doc: Optional[str] = None


def _record_finding(**kw) -> str:
    args = FindingArgs(**kw)
    pid = _resolve_pid(args.slug_or_id)
    if not pid:
        return "Property not found."
    _record_dd_finding(pid, "diligence", args.category, args.severity, args.summary,
                       args.detail, args.source_doc)
    return "Recorded."


record_finding = StructuredTool.from_function(
    func=_record_finding,
    name="record_finding",
    description="Record a DD finding against a property for downstream tracking.",
    args_schema=FindingArgs,
)
