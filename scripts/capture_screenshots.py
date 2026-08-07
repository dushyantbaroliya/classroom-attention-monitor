"""Capture dashboard screenshots to docs/screenshots/ via Playwright.

Uses the system browser (Edge on Windows, Chrome elsewhere) so no Chromium
download is needed. The frontend dev server must be running on :5173 and the
backend on :8000 with a seeded session (python scripts/seed_demo.py).

Dev-only tool, install Playwright first (not in requirements.txt):

    pip install playwright
    python scripts/capture_screenshots.py

If no system Edge/Chrome is available, run `playwright install chromium` once.
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:5173"
OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"

# (route, filename, extra settle for charts/animations)
PAGES = [
    ("/", "dashboard"),
    ("/live", "live"),
    ("/students", "students"),
    ("/analytics", "analytics"),
    ("/reports", "reports"),
]


def launch(p):
    """Prefer the installed system browser; fall back to bundled Chromium."""
    for channel in ("msedge", "chrome"):
        try:
            return p.chromium.launch(channel=channel, headless=True)
        except Exception:
            continue
    return p.chromium.launch(headless=True)  # requires `playwright install chromium`


def capture(page, theme: str) -> None:
    page.emulate_media(color_scheme=theme)
    # Force the app's own theme (it persists to localStorage) before load.
    page.add_init_script(
        f"try{{localStorage.setItem('cam-theme','{theme}');}}catch(e){{}}"
    )
    for route, name in PAGES:
        page.goto(f"{BASE}{route}", wait_until="networkidle")
        page.wait_for_timeout(2200)  # count-up + chart mount animations
        suffix = "" if theme == "dark" else "-light"
        dest = OUT / f"{name}{suffix}.png"
        page.screenshot(path=str(dest), full_page=False)
        print(f"  saved {dest.name}")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = launch(p)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,  # crisp 2x captures
        )
        page = context.new_page()
        print("Dark theme:")
        capture(page, "dark")
        print("Light theme:")
        capture(page, "light")
        browser.close()
    print(f"\nScreenshots written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
