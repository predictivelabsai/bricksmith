"""Generate a Bricksmith **slide-deck style** product-tour PDF.

Output: docs/bricksmith-product-tour.pdf

Layout: 16:9 landscape, one slide per screenshot. Each slide has a title,
short caption, the app screenshot fitted to the page, and a minimal footer.
Focused on **app functionality** — pipeline kanban, per-deal chat, instructions
editor, analytics, streaming chat. A single opening cover sets context.

Usage:
    python -m scripts.make_pdf
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import Paragraph


ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "screenshots"
OUT = ROOT / "docs" / "bricksmith-product-tour.pdf"

# 16:9 landscape slide (like PowerPoint Widescreen).
PAGE_W = 33.87 * cm   # 13.33 in
PAGE_H = 19.05 * cm   # 7.5 in
SLIDE_SIZE = landscape((PAGE_W, PAGE_H))

# Palette lifted from the app (dark navy + amber) for the slide chrome.
BG        = HexColor("#0B1220")
BG_ELEV   = HexColor("#111A2E")
INK       = HexColor("#F5F5F7")
INK_DIM   = HexColor("#8AA0C8")
ACCENT    = HexColor("#E7B66B")
ACCENT_D  = HexColor("#3A2E1A")
LINE      = HexColor("#1F2E4F")


SLIDES = [
    # (filename, title, caption)   filename=None → cover slide
    (None,
     "Bricksmith",
     "Agentic AI for commercial real estate. 22 specialist agents across "
     "sourcing, underwriting, diligence, capital & asset management — "
     "backed by a shared property catalog, T12 / rent-roll store, and "
     "pgvector RAG across leases, zoning, PCRs, titles and Phase I ESAs. "
     "All screens are live against the synthetic demo dataset."),

    ("02-pipeline.png",
     "Pipeline — kanban across 10 deal stages",
     "40 properties, colour-coded by stage. Heat dot = seller intent, "
     "card shows NOI, cap rate and ask price. Filter chips by asset type "
     "and ownership."),

    ("03-pipeline-filtered.png",
     "Pipeline — filtered to multifamily",
     "Filters are stackable — assets × ownership × stage. Every card "
     "links through to a per-deal chat with the property brief pre-rendered "
     "in the right pane."),

    ("04-deal-detail.png",
     "Deal detail — chat + pre-rendered brief",
     "Opening a card lands you in a scoped conversation for that property. "
     "The right pane is already populated with address, LTM financials, "
     "top tenants and the current DD findings."),

    ("05-chat-empty.png",
     "Chat — 3-pane shell",
     "Sessions + 22 agents on the left, streaming transcript in the centre, "
     "contextual artifacts on the right. Type a message or click a "
     "sample card to route to a specialist."),

    ("06-chat-triage.png",
     "Chat — Deal Triage",
     "`triage:` routes to the Deal Triage Agent. Streaming tokens and a "
     "live \u201cThinking\u2026 Ns \u00b7 calling <tool>\u201d indicator keep "
     "the analyst oriented while the agent loads the property + market "
     "context."),

    ("07-chat-comps.png",
     "Chat — Comp Finder",
     "`comps:` routes to the Comp Finder. Structured tool output lands in "
     "the artifact pane as a sortable table — sales comps or rent comps, "
     "filtered by asset type, vintage and geography."),

    ("08-chat-memo.png",
     "Chat — Investor Memo",
     "`memo:` assembles an IC-ready memo from the deal\u2019s own data: "
     "exec summary, market, underwriting, risks, recommendation. Every "
     "figure is cited from a tool call."),

    ("09-instructions.png",
     "Instructions — edit any agent\u2019s system prompt",
     "All 22 agent prompts (plus the shared CRE glossary) are editable from "
     "the app. Changes are written to <code>prompts/system/&lt;slug&gt;.md</code> "
     "and reloaded on the next conversation — no redeploy."),

    ("10-instructions-edit.png",
     "Instructions — editor view",
     "Full markdown editor with the path to disk exposed. Save clears the "
     "agent cache so the next invocation re-reads the prompt."),

    ("11-analytics-empty.png",
     "Analytics — ask your CRE database a question",
     "Natural-language input, eight seeded example questions, dark Plotly "
     "charts. Queries are translated to SELECT-only SQL against the "
     "bricksmith schema and run read-only."),

    ("12-analytics-result.png",
     "Analytics — NL \u2192 guarded SQL \u2192 Plotly",
     "Grok drafts the SQL; a guard rejects anything that isn\u2019t pure "
     "SELECT / WITH; results render as a Plotly figure plus the underlying "
     "table. The generated query is shown inline for verification."),
]


def _styles():
    ss = getSampleStyleSheet()
    return {
        "slide_title": ParagraphStyle(
            "slide_title", parent=ss["Title"], fontName="Helvetica-Bold",
            fontSize=22, leading=26, textColor=INK, alignment=TA_LEFT, spaceAfter=0,
        ),
        "slide_caption": ParagraphStyle(
            "slide_caption", parent=ss["Normal"], fontName="Helvetica",
            fontSize=10.5, leading=14, textColor=INK_DIM, alignment=TA_LEFT,
        ),
        "cover_title": ParagraphStyle(
            "cover_title", parent=ss["Title"], fontName="Helvetica-Bold",
            fontSize=46, leading=54, textColor=INK, alignment=TA_LEFT,
        ),
        "cover_tag": ParagraphStyle(
            "cover_tag", parent=ss["Normal"], fontName="Helvetica",
            fontSize=14, leading=20, textColor=INK_DIM, alignment=TA_LEFT,
        ),
    }


def _fit_image_dims(path: Path, max_w: float, max_h: float) -> tuple[float, float]:
    """Return (width, height) in points that fit inside the box, preserving aspect."""
    with Image.open(path) as im:
        w, h = im.size
    ratio = min(max_w / w, max_h / h)
    return (w * ratio, h * ratio)


def _draw_chrome(canvas: rl_canvas.Canvas, page_idx: int, total: int) -> None:
    # Full-bleed dark background
    canvas.setFillColor(BG)
    canvas.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    # Accent rule across the top
    canvas.setStrokeColor(ACCENT)
    canvas.setLineWidth(1.2)
    canvas.line(1.8 * cm, PAGE_H - 0.9 * cm, PAGE_W - 1.8 * cm, PAGE_H - 0.9 * cm)
    # Footer: brand, synthetic-data note, page counter
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(ACCENT)
    canvas.drawString(1.8 * cm, 0.7 * cm, "BRICKSMITH")
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(INK_DIM)
    canvas.drawString(4.1 * cm, 0.7 * cm, "  synthetic demo data  \u2022  agentic AI for commercial real estate")
    canvas.drawRightString(PAGE_W - 1.8 * cm, 0.7 * cm, f"{page_idx}/{total}")


def _draw_cover(canvas: rl_canvas.Canvas, styles: dict, caption: str, total: int) -> None:
    _draw_chrome(canvas, 1, total)
    # Big wordmark
    canvas.setFillColor(ACCENT)
    canvas.setFont("Helvetica-Bold", 72)
    canvas.drawString(2.2 * cm, PAGE_H - 5.5 * cm, "Bricksmith")
    canvas.setFillColor(INK)
    canvas.setFont("Helvetica", 18)
    canvas.drawString(2.2 * cm, PAGE_H - 7.0 * cm, "Agentic AI for commercial real estate")
    # Caption block
    p = Paragraph(caption, styles["cover_tag"])
    w = PAGE_W - 4.4 * cm
    w_need, h_need = p.wrap(w, PAGE_H)
    p.drawOn(canvas, 2.2 * cm, PAGE_H - 8.0 * cm - h_need)
    # KPI strip along the bottom-right
    kpis = [
        ("22",   "specialist agents"),
        ("40",   "synthetic properties"),
        ("10",   "deal stages"),
        ("237",  "RAG documents"),
        ("8",    "metros"),
    ]
    x = 2.2 * cm
    y = 3.5 * cm
    for num, label in kpis:
        canvas.setFillColor(ACCENT)
        canvas.setFont("Helvetica-Bold", 26)
        canvas.drawString(x, y, num)
        canvas.setFillColor(INK_DIM)
        canvas.setFont("Helvetica", 9)
        canvas.drawString(x, y - 0.55 * cm, label.upper())
        x += 5.5 * cm


def _draw_content_slide(
    canvas: rl_canvas.Canvas, styles: dict,
    title: str, caption: str, image_path: Path,
    page_idx: int, total: int,
) -> None:
    _draw_chrome(canvas, page_idx, total)

    # Title (top-left, below the accent rule)
    p_title = Paragraph(title, styles["slide_title"])
    w_need, h_need = p_title.wrap(PAGE_W - 4.4 * cm, 3 * cm)
    title_y = PAGE_H - 1.7 * cm - h_need
    p_title.drawOn(canvas, 1.8 * cm, title_y)

    # Caption under the title
    p_cap = Paragraph(caption, styles["slide_caption"])
    w_need, cap_h = p_cap.wrap(PAGE_W - 4.4 * cm, 5 * cm)
    cap_y = title_y - 0.3 * cm - cap_h
    p_cap.drawOn(canvas, 1.8 * cm, cap_y)

    # Screenshot slot — fills below caption, with a subtle panel behind it
    pad = 0.45 * cm
    slot_top = cap_y - 0.5 * cm
    slot_bottom = 1.3 * cm
    slot_left = 1.8 * cm
    slot_right = PAGE_W - 1.8 * cm
    slot_w = slot_right - slot_left
    slot_h = slot_top - slot_bottom
    img_w, img_h = _fit_image_dims(image_path, slot_w - 2 * pad, slot_h - 2 * pad)
    img_x = slot_left + (slot_w - img_w) / 2
    img_y = slot_bottom + (slot_h - img_h) / 2

    # Panel
    canvas.setFillColor(BG_ELEV)
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.6)
    canvas.roundRect(slot_left, slot_bottom, slot_w, slot_h,
                     6, stroke=1, fill=1)

    canvas.drawImage(
        str(image_path),
        img_x, img_y, width=img_w, height=img_h,
        preserveAspectRatio=True, mask="auto",
    )


def build() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()
    total = len(SLIDES)

    c = rl_canvas.Canvas(str(OUT), pagesize=SLIDE_SIZE)
    c.setTitle("Bricksmith — Product Tour")
    c.setAuthor("Predictive Labs")

    for idx, (fname, title, caption) in enumerate(SLIDES, 1):
        if fname is None:
            _draw_cover(c, styles, caption, total)
        else:
            path = SHOTS / fname
            if not path.exists():
                # Graceful degrade — draw a placeholder so we don't silently skip
                _draw_content_slide(
                    c, styles, title,
                    caption + f"  (missing frame: {fname})",
                    # Use any available screenshot to render something rather
                    # than skipping. Fallback search.
                    next(iter(sorted(SHOTS.glob("*.png"))), path),
                    idx, total,
                )
            else:
                _draw_content_slide(c, styles, title, caption, path, idx, total)
        c.showPage()

    c.save()
    kb = OUT.stat().st_size / 1024
    print(f"Wrote {OUT}  ({kb:.1f} KB, {total} slides)")


if __name__ == "__main__":
    build()
