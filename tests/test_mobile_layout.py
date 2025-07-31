import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
import pytest


def test_mobile_layout(tmp_path):
    proc = subprocess.Popen([
        "streamlit",
        "run",
        "streamlit_app.py",
        "--server.headless",
        "true",
    ])
    try:
        time.sleep(5)
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception:
                pytest.skip("browser launch failed")
            context = browser.new_context(viewport={"width": 375, "height": 812})
            page = context.new_page()
            page.goto("http://localhost:8501", timeout=60000)
            page.wait_for_selector("#root")
            page.screenshot(path=str(tmp_path / "mobile.png"))
            assert (tmp_path / "mobile.png").exists()
    finally:
        proc.terminate()
        proc.wait()
