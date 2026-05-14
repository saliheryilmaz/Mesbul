import os, time, re
from dotenv import load_dotenv
load_dotenv()
from playwright.sync_api import sync_playwright

USERNAME = os.getenv("LASTIKPARK_KULLANICI", "")
PASSWORD = os.getenv("LASTIKPARK_SIFRE", "")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ).new_page()
    page.set_default_timeout(30_000)

    page.goto("https://bayiportal.lastikpark.com/#TatkoLogin", timeout=30_000)
    try: page.wait_for_load_state("networkidle", timeout=10_000)
    except: pass
    time.sleep(3)

    # Sirket alanini incele
    company_el = page.query_selector('#company')
    print(f"#company: {company_el is not None}")
    if company_el:
        # Bos birak ve kullanici/sifre doldur
        company_el.fill("")

    # Kullanici ve sifre doldur
    page.query_selector('#username').fill(USERNAME)
    page.query_selector('#password').fill(PASSWORD)

    # Giris butonuna tikla
    btn = page.query_selector('button:has-text("GİRİŞ"), button:has-text("Giriş")')
    print(f"Giris butonu: {btn is not None}")
    if btn:
        btn.click()
    else:
        page.keyboard.press("Enter")

    try: page.wait_for_load_state("networkidle", timeout=15_000)
    except: pass
    time.sleep(5)

    print(f"URL: {page.url}")
    body = page.inner_text("body")[:800]
    print(f"Body:\n{body}")

    login_ok = any(w in body.lower() for w in ["cikis", "stok", "urun", "arama",
                                                 "sepet", "hosgeldiniz", "lastik",
                                                 "anasayfa", "portal"])
    print(f"\nLogin OK: {login_ok}")

    if login_ok:
        # Arama sayfasini bul
        inputs = page.query_selector_all("input")
        print(f"\nInputlar ({len(inputs)}):")
        for inp in inputs[:10]:
            t  = inp.get_attribute("type") or ""
            n  = inp.get_attribute("name") or ""
            i  = inp.get_attribute("id") or ""
            ph = inp.get_attribute("placeholder") or ""
            print(f"  type={t} name={n} id={i} placeholder={ph}")

        # Tablolar
        tables = page.query_selector_all("table")
        print(f"\nTablolar: {len(tables)}")

        # Linkler
        links = page.query_selector_all("a")
        print(f"\nLinkler (stok/urun/ara iceren):")
        for link in links[:30]:
            href = link.get_attribute("href") or ""
            text = link.inner_text().strip()[:40]
            if any(w in (href+text).lower() for w in ["stok", "urun", "ara", "lastik", "search", "ebat"]):
                print(f"  '{text}' -> {href}")

    page.screenshot(path="debug_screenshots/lastikpark_test.png", full_page=False)
    print("\nScreenshot kaydedildi")
    browser.close()
