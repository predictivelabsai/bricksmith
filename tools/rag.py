"""Retrieval tool for the bricksmith_rag corpus."""

from __future__ import annotations

import json
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from rag.retriever import retrieve


class RetrieveArgs(BaseModel):
    query: str = Field(description="Natural-language query to retrieve relevant document chunks for.")
    k: int = Field(default=6, ge=1, le=20)
    doc_types: Optional[list[str]] = Field(default=None,
        description="Restrict to specific doc types: lease, zoning, environmental, pcr, title, market.")
    property_id: Optional[int] = Field(default=None, description="Restrict to a single property's docs.")


def _retrieve(**kw) -> str:
    args = RetrieveArgs(**kw)
    chunks = retrieve(args.query, k=args.k, doc_types=args.doc_types, property_id=args.property_id)
    if not chunks:
        return "No relevant documents found."
    items = [
        {
            "title": c.title,
            "doc_type": c.doc_type,
            "property_id": c.property_id,
            "score": round(c.score, 3),
            "snippet": c.text[:500],
        }
        for c in chunks
    ]
    artifact_payload = {
        "kind": "citations",
        "title": f"Retrieved {len(chunks)} sources",
        "subtitle": args.query[:60],
        "items": items,
    }
    # Return both the tool result (for the LLM to consume) and an inline
    # artifact envelope (for the UI to render in the right pane).
    return "__ARTIFACT__" + json.dumps(artifact_payload)


retrieve_documents = StructuredTool.from_function(
    func=_retrieve,
    name="retrieve_documents",
    description="Semantic search across leases, zoning memos, environmental reports, PCRs, title commitments, and market reports indexed in the RAG corpus. Use this when the user asks about document contents.",
    args_schema=RetrieveArgs,
)
