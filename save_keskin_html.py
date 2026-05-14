import os
import time
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

LOGIN_URL = "https://keskinlastik.com/Giris"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = context.new_page()
    try:
        page.goto(LOGIN_URL, timeout=30000)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2)
        html = page.content()
        with open("keskin_login.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("Saved HTML to keskin_login.html")
    except Exception as e:
        print("Error:", e)
    finally:
        browser.close()
