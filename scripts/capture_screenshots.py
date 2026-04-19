"""Capture a product tour of the Bricksmith **app** into ./screenshots.

Drives a real browser via Playwright against a locally-running server
(default http://localhost:5057). Focused on app functionality — pipeline
kanban, per-deal chat with right-pane brief, instructions editor, analytics
NL→SQL→Plotly, and the 3-pane chat with streamed agent output. Landing
frames are included only as a single cover.

Usage:
    # server already running on :5057
    python -m scripts.capture_screenshots
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

log = logging.getLogger("capture")

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "screenshots"

BASE_URL = os.environ.get("BRICKSMITH_URL", "http://localhost:5057")
VIEWPORT = {"width": 1440, "height": 900}


# Each tour entry produces one frame. `action` drives any post-navigation
# interaction (typing into the chat, running an analytics query, etc.).
#
# The filenames sort lexicographically so make_gif.py and make_pdf.py pick
# them up in the intended narrative order.
TOUR = [
    # (filename, url, wait_selector, full_page, action)
    ("01-home.png",              "/",                     "text=22 specialist agents", False, None),
    ("02-pipeline.png",          "/app/pipeline",         ".kanban-board",             True,  None),
    ("03-pipeline-filtered.png", "/app/pipeline?asset=multifamily", ".kanban-board",   True,  None),
    ("04-deal-detail.png",       None,                    ".deal-brief",               False, "first_deal"),
    ("05-chat-empty.png",        "/app",                  "#chat-input",               False, None),
    ("06-chat-triage.png",       "/app",                  "#chat-input",               False, "chat_triage"),
    ("07-chat-comps.png",        "/app",                  "#chat-input",               False, "chat_comps"),
    ("08-chat-memo.png",         "/app",                  "#chat-input",               False, "chat_memo"),
    ("09-instructions.png",      "/app/instructions",     ".instr-list",               True,  None),
    ("10-instructions-edit.png", "/app/instructions/deal_triage", ".instr-textarea",   False, None),
    ("11-analytics-empty.png",   "/app/analytics",        "#analytics-q",              False, None),
    ("12-analytics-result.png",  "/app/analytics",        "#analytics-q",              False, "analytics_run"),
]


CHAT_MSGS = {
    "chat_triage": "triage: 220-unit MF in Austin, $62M ask, 4.9% cap in-place",
    "chat_comps":  "comps: multifamily Austin Class A 2020+ vintage",
    "chat_memo":   "memo: draft the investment memo for Arden Buckhead",
}


def _run_chat(page, msg: str) -> None:
    page.fill("#chat-input", msg)
    page.evaluate(
        "() => document.querySelector('#chat-form').dispatchEvent("
        "new Event('submit', {cancelable: true}))"
    )
    try:
        page.wait_for_function(
            """() => {
                const m = document.querySelector('#messages');
                if (!m) return false;
                const bubbles = m.querySelectorAll('.msg-assistant .msg-bubble');
                if (!bubbles.length) return false;
                const last = bubbles[bubbles.length-1];
                return last && (last.textContent||'').length > 60
                       && !last.parentElement.classList.contains('streaming');
            }""",
            timeout=75_000,
        )
    except Exception as e:
        log.warning("chat stream didn't finish in time (%s) — capturing mid-stream", e)
    time.sleep(0.8)  # paint


def _run_analytics(page, q: str) -> None:
    page.fill("#analytics-q", q)
    page.evaluate("() => window.runAnalytics()")
    # Wait for plotly chart to render
    page.wait_for_function(
        "() => document.querySelector('.analytics-chart .plotly') !== null",
        timeout=60_000,
    )
    time.sleep(0.8)


def _first_deal_slug(page) -> str:
    page.goto(BASE_URL + "/app/pipeline", wait_until="networkidle", timeout=30_000)
    page.wait_for_selector(".deal-card-link", timeout=10_000)
    return page.evaluate(
        "() => document.querySelector('.deal-card-link').getAttribute('href')"
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    SHOTS.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=1)
        page = ctx.new_page()

        # Resolve the first deal slug dynamically so the detail page
        # screenshot doesn't break if the seed changes.
        deal_href = _first_deal_slug(page)
        log.info("first deal href: %s", deal_href)

        for fname, path, wait_for, full_page, action in TOUR:
            # Resolve action-driven navigation
            if action == "first_deal":
                url = BASE_URL + deal_href
            elif path is None:
                continue
            else:
                url = BASE_URL + path

            log.info("→ %s", url)
            page.goto(url, wait_until="networkidle", timeout=30_000)
            if wait_for:
                try:
                    page.wait_for_selector(wait_for, timeout=12_000)
                except Exception:
                    log.warning("selector %r didn't appear on %s", wait_for, url)

            if action == "chat_triage":
                _run_chat(page, CHAT_MSGS["chat_triage"])
            elif action == "chat_comps":
                _run_chat(page, CHAT_MSGS["chat_comps"])
            elif action == "chat_memo":
                _run_chat(page, CHAT_MSGS["chat_memo"])
            elif action == "analytics_run":
                _run_analytics(page, "Median cap rate by asset type")

            out = SHOTS / fname
            page.screenshot(path=str(out), full_page=full_page)
            log.info("  saved %s", out.relative_to(ROOT))

        browser.close()

    log.info("done — %d frames in %s", len(TOUR), SHOTS)


if __name__ == "__main__":
    main()
