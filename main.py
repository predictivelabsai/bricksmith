"""Entrypoint. Kept as a thin shim so standard runners (`python main.py`)
work without changes. All routing lives in app.py."""

from utils.logging import setup_logging

setup_logging()

from app import app, _serve_default  # noqa: E402,F401

if __name__ == "__main__":
    _serve_default()
