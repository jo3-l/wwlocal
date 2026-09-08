"""`wwlocal login`: complete UW SSO + Duo in a real browser, keep the cookies."""

import json
import re

from playwright.sync_api import sync_playwright

from wwlocal.config import BASE, COOKIES_FILE, JOBS_URL


def run() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(BASE + "/waterloo.htm")
        print("Complete the UW login (SSO + Duo) in the browser window...")
        page.wait_for_url(re.compile(r"/myAccount/"), timeout=600_000)
        page.goto(JOBS_URL)
        page.wait_for_load_state("networkidle")
        cookies = [c for c in page.context.cookies() if "uwaterloo.ca" in c.get("domain", "")]
        browser.close()
    COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    COOKIES_FILE.write_text(json.dumps(cookies, indent=1))
    COOKIES_FILE.chmod(0o600)
    print(f"Saved {len(cookies)} cookies to {COOKIES_FILE}")
