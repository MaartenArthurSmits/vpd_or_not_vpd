"""Playwright fixtures: a local Streamlit server and a Chromium browser."""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[2]

# Console messages that are not application errors.
BENIGN_CONSOLE = (
    "favicon",
    "Download the React DevTools",
)


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def app_url(artifacts_dir):
    port = _free_port()
    log = open(artifacts_dir / "streamlit-server.log", "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless", "true",
         "--server.port", str(port), "--server.address", "127.0.0.1",
         "--browser.gatherUsageStats", "false", "--server.fileWatcherType", "none"],
        cwd=PROJECT, stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 90
    while time.time() < deadline:
        if proc.poll() is not None:
            pytest.fail(f"Streamlit exited early (code {proc.returncode}); see {log.name}")
        try:
            if urllib.request.urlopen(f"{url}/_stcore/health", timeout=2).read() == b"ok":
                break
        except Exception:
            time.sleep(0.5)
    else:
        proc.terminate()
        pytest.fail("Streamlit server did not become healthy within 90 s")
    yield url
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
    log.close()


@pytest.fixture(scope="session")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:
            msg = f"Chromium unavailable ({type(e).__name__}); run `python -m playwright install chromium`"
            if os.environ.get("CI"):
                pytest.fail(msg)
            pytest.skip(msg)
        yield b
        b.close()


@pytest.fixture(scope="session")
def console_log():
    """Collects console errors and page errors across the whole session."""
    return []


@pytest.fixture
def page(browser, app_url, console_log):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
    pg = ctx.new_page()
    pg.on("console", lambda m: console_log.append({"type": m.type, "text": m.text, "url": pg.url})
          if m.type == "error" and not any(b in m.text for b in BENIGN_CONSOLE) else None)
    pg.on("pageerror", lambda e: console_log.append({"type": "pageerror", "text": str(e), "url": pg.url}))
    pg.goto(app_url)
    pg.get_by_text("Calculation mode").first.wait_for(timeout=60_000)
    yield pg
    ctx.close()


@pytest.fixture(scope="session", autouse=True)
def write_diagnostics(request, console_log, artifacts_dir):
    yield
    (artifacts_dir / "console-errors.json").write_text(json.dumps(console_log, indent=2), encoding="utf-8")
