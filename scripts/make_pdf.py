"""Generate the Bricksmith slide-deck style product tour PDF.

Output: docs/bricksmith-product-tour.pdf

Layout: 16:9 landscape, one slide per screenshot. Each slide has a title,
a short marketing caption, the app screenshot fitted to the page, and a
minimal footer. Ends with a contact slide.

Usage:
    python -m scripts.make_pdf
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import Paragraph


ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "screenshots"
OUT = ROOT / "docs" / "bricksmith-product-tour.pdf"

# 16:9 landscape slide (PowerPoint Widescreen).
PAGE_W = 33.87 * cm   # 13.33 in
PAGE_H = 19.05 * cm   # 7.5 in
SLIDE_SIZE = landscape((PAGE_W, PAGE_H))

# Palette lifted from the app (dark navy + amber).
BG        = HexColor("#0B1220")
BG_ELEV   = HexColor("#111A2E")
INK       = HexColor("#F5F5F7")
INK_DIM   = HexColor("#8AA0C8")
ACCENT    = HexColor("#E7B66B")
LINE      = HexColor("#1F2E4F")


# Slide tuples: (filename | None, title, caption)
#   filename = None for cover + contact (special-cased layouts).
SLIDES = [
    (None,
     "Bricksmith",
     "Your CRE Deal AI Squad — specialist teammates for sourcing, "
     "underwriting, diligence, capital, and asset management, living "
     "inside one workspace alongside your team."),

    ("02-pipeline.png",
     "See every deal at a glance",
     "The pipeline board spans the full deal lifecycle — from the first "
     "broker tip to the asset you've owned for years. Heat dots flag "
     "seller motivation, each card surfaces the numbers you'd actually "
     "screen on."),

    ("03-pipeline-filtered.png",
     "Filter the board in a click",
     "Asset type, ownership, stage — stack any of the filter chips and "
     "the kanban narrows instantly. Every card opens into its own "
     "workspace with the brief already written up."),

    ("04-deal-detail.png",
     "One workspace per deal",
     "Open a card and the squad is scoped to that property. Address, "
     "occupancy, LTM financials, top tenants and open DD findings are "
     "already pre-rendered on the right — ready to work off."),

    ("05-chat-empty.png",
     "Your team, composed",
     "Sessions and the full squad on the left, the live conversation in "
     "the centre, artifacts on the right. Type a message or click a "
     "sample prompt — the right specialist picks it up."),

    ("06-chat-triage.png",
     "Triage a deal in 90 seconds",
     "Describe the opportunity and the squad returns a go / no-go with "
     "the reasoning. Tool calls are visible as they happen — no black "
     "box, the analyst sees exactly what was checked."),

    ("07-chat-comps.png",
     "Sales and rent comps, outliers filtered",
     "Comp tables land in the right pane, sortable and exportable. "
     "Narrow by asset type, vintage, and geography — the squad keeps "
     "the noise out of the set."),

    ("08-chat-memo.png",
     "An IC memo from the deal's own data",
     "Exec summary, market, underwriting, risks, recommendation. "
     "Every figure traces back to a tool call — ready to paste into the "
     "committee deck."),

    ("09-instructions.png",
     "Tune your squad's voice",
     "Every specialist's instructions are editable from inside the app. "
     "Codify your house view, your models, your phrasings — and every "
     "future answer speaks like your firm."),

    ("10-instructions-edit.png",
     "Edit, save, done",
     "Changes take effect on the next conversation. Version control "
     "lives in the repo, so every tweak is reviewable and revertable."),

    ("11-analytics-empty.png",
     "Ask your pipeline a question",
     "In plain English. Across every property, operating statement, comp "
     "and LP in the system — no SQL, no dashboards to build."),

    ("12-analytics-result.png",
     "From question to chart",
     "The squad drafts the query, runs it read-only, and renders the "
     "answer as a chart you can put in front of the IC — with the raw "
     "table one click away for the skeptics."),

    # contact / close
    (None,
     "Let's put the squad on your deals",
     "Want to see Bricksmith work against your own pipeline, your own "
     "models and your own data? We'll stand up a two-week pilot with "
     "your team and your deals in the loop."),
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
            fontSize=11, leading=15, textColor=INK_DIM, alignment=TA_LEFT,
        ),
        "cover_tag": ParagraphStyle(
            "cover_tag", parent=ss["Normal"], fontName="Helvetica",
            fontSize=15, leading=22, textColor=INK_DIM, alignment=TA_LEFT,
        ),
        "contact_tag": ParagraphStyle(
            "contact_tag", parent=ss["Normal"], fontName="Helvetica",
            fontSize=15, leading=22, textColor=INK_DIM, alignment=TA_CENTER,
        ),
    }


def _fit_image_dims(path: Path, max_w: float, max_h: float) -> tuple[float, float]:
    """Return (width, height) in points that fit inside the box, preserving aspect."""
    with Image.open(path) as im:
        w, h = im.size
    ratio = min(max_w / w, max_h / h)
    return (w * ratio, h * ratio)


def _draw_chrome(canvas: rl_canvas.Canvas, page_idx: int, total: int) -> None:
    canvas.setFillColor(BG)
    canvas.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    canvas.setStrokeColor(ACCENT)
    canvas.setLineWidth(1.2)
    canvas.line(1.8 * cm, PAGE_H - 0.9 * cm, PAGE_W - 1.8 * cm, PAGE_H - 0.9 * cm)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(ACCENT)
    canvas.drawString(1.8 * cm, 0.7 * cm, "BRICKSMITH")
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(INK_DIM)
    canvas.drawString(4.1 * cm, 0.7 * cm, "  your CRE deal AI squad")
    canvas.drawRightString(PAGE_W - 1.8 * cm, 0.7 * cm, f"{page_idx}/{total}")


def _draw_cover(canvas: rl_canvas.Canvas, styles: dict, caption: str, total: int) -> None:
    _draw_chrome(canvas, 1, total)
    canvas.setFillColor(ACCENT)
    canvas.setFont("Helvetica-Bold", 72)
    canvas.drawString(2.2 * cm, PAGE_H - 5.5 * cm, "Bricksmith")
    canvas.setFillColor(INK)
    canvas.setFont("Helvetica", 20)
    canvas.drawString(2.2 * cm, PAGE_H - 7.0 * cm, "Your CRE Deal AI Squad")

    p = Paragraph(caption, styles["cover_tag"])
    w = PAGE_W - 4.4 * cm
    _, h_need = p.wrap(w, PAGE_H)
    p.drawOn(canvas, 2.2 * cm, PAGE_H - 8.3 * cm - h_need)

    # Functional areas along the bottom, no numeric counts
    squad = ["SOURCING", "UNDERWRITING", "DILIGENCE", "CAPITAL", "ASSET MGMT"]
    x = 2.2 * cm
    y = 3.6 * cm
    for label in squad:
        canvas.setFillColor(ACCENT)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(x, y + 0.6 * cm, "◆")
        canvas.setFillColor(INK)
        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawString(x + 0.6 * cm, y + 0.6 * cm, label)
        x += 6.0 * cm


def _draw_contact(canvas: rl_canvas.Canvas, styles: dict, title: str, caption: str, total: int) -> None:
    _draw_chrome(canvas, total, total)
    # Centred block
    canvas.setFillColor(ACCENT)
    canvas.setFont("Helvetica-Bold", 44)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H - 5.2 * cm, "Bricksmith")
    canvas.setFillColor(INK)
    canvas.setFont("Helvetica", 16)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H - 6.2 * cm, "Your CRE Deal AI Squad")

    canvas.setFillColor(INK)
    canvas.setFont("Helvetica-Bold", 26)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H - 8.8 * cm, title)

    p = Paragraph(caption, styles["contact_tag"])
    w = 22 * cm
    _, h_need = p.wrap(w, PAGE_H)
    p.drawOn(canvas, (PAGE_W - w) / 2, PAGE_H - 10.2 * cm - h_need)

    # Contact details
    y = 5.0 * cm
    canvas.setFillColor(INK_DIM)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawCentredString(PAGE_W / 2, y + 2.2 * cm, "GET IN TOUCH")
    canvas.setFillColor(INK)
    canvas.setFont("Helvetica", 18)
    canvas.drawCentredString(PAGE_W / 2, y + 1.2 * cm, "bricksmith.predictivelabs.ai")
    canvas.setFillColor(ACCENT)
    canvas.setFont("Helvetica-Bold", 18)
    canvas.drawCentredString(PAGE_W / 2, y + 0.3 * cm, "bricksmith@predictivelabs.ai")


def _draw_content_slide(
    canvas: rl_canvas.Canvas, styles: dict,
    title: str, caption: str, image_path: Path,
    page_idx: int, total: int,
) -> None:
    _draw_chrome(canvas, page_idx, total)

    p_title = Paragraph(title, styles["slide_title"])
    _, h_need = p_title.wrap(PAGE_W - 4.4 * cm, 3 * cm)
    title_y = PAGE_H - 1.7 * cm - h_need
    p_title.drawOn(canvas, 1.8 * cm, title_y)

    p_cap = Paragraph(caption, styles["slide_caption"])
    _, cap_h = p_cap.wrap(PAGE_W - 4.4 * cm, 5 * cm)
    cap_y = title_y - 0.3 * cm - cap_h
    p_cap.drawOn(canvas, 1.8 * cm, cap_y)

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

    canvas.setFillColor(BG_ELEV)
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.6)
    canvas.roundRect(slot_left, slot_bottom, slot_w, slot_h, 6, stroke=1, fill=1)

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
        if idx == 1:
            _draw_cover(c, styles, caption, total)
        elif idx == total:
            _draw_contact(c, styles, title, caption, total)
        else:
            path = SHOTS / fname
            if not path.exists():
                _draw_content_slide(
                    c, styles, title,
                    caption + f"  (missing frame: {fname})",
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
