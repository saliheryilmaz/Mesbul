"""Tüm sitelere login + ürün arama - düzeltilmiş."""
import os, sys, time, json, traceback
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
load_dotenv()

OUT = os.path.join(os.path.dirname(__file__), "_dom_dumps")
os.makedirs(OUT, exist_ok=True)

def save(name, suffix, page):
    with open(os.path.join(OUT, f"{name}_{suffix}.html"), "w", encoding="utf-8") as f:
        f.write(page.content())
    page.screenshot(path=os.path.join(OUT, f"{name}_{suffix}.png"))

def info_tables(page):
    return page.evaluate("""() => {
        const tables = document.querySelectorAll('table');
        return Array.from(tables).map((t, i) => ({
            idx: i, rows: t.querySelectorAll('tr').length,
            heads: t.querySelector('tr') ? Array.from(t.querySelector('tr').querySelectorAll('th,td')).map(c=>c.textContent.trim().substring(0,25)) : []
        }));
    }""")

def info_inputs(page):
    return page.evaluate("""() => {
        return Array.from(document.querySelectorAll('input:not([type=hidden])')).map(i => ({
            type: i.type, name: i.name, id: i.id, ph: i.placeholder
        }));
    }""")

def do_cakiroglu(p):
    print("\n=== CAKIROGLU ===")
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width":1280,"height":900}, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    pg.goto("http://b2b.cakirogluotomotiv.com/B2B_Stoklar.asp", timeout=30000)
    pg.wait_for_load_state("networkidle"); time.sleep(2)
    pg.fill('input[name="USER"]', os.getenv("CAKIROGLU_KULLANICI",""))
    pg.fill('input[name="SIFRE"]', os.getenv("CAKIROGLU_SIFRE",""))
    pg.click('button.LoginForm')
    pg.wait_for_load_state("networkidle", timeout=20000); time.sleep(3)
    print(f"  URL: {pg.url}")
    save("cakiroglu", "afterlogin", pg)
    
    # Stok sayfasına git
    pg.goto("http://b2b.cakirogluotomotiv.com/B2B_Stoklar.asp", timeout=30000)
    pg.wait_for_load_state("networkidle"); time.sleep(3)
    print(f"  Stok URL: {pg.url}")
    save("cakiroglu", "stoklar", pg)
    print(f"  Inputs: {json.dumps(info_inputs(pg), ensure_ascii=False)}")
    print(f"  Tables: {json.dumps(info_tables(pg), ensure_ascii=False)}")
    
    # Arama dene
    search = pg.query_selector('input#txtAra, input[name*="ara" i], input[placeholder*="ara" i]')
    if search:
        search.fill("205/55R16"); search.press("Enter")
        pg.wait_for_load_state("networkidle", timeout=30000); time.sleep(5)
        save("cakiroglu", "search", pg)
        print(f"  Arama sonrası tables: {json.dumps(info_tables(pg), ensure_ascii=False)}")
    else:
        # Select/dropdown arama
        selects = pg.query_selector_all("select")
        for s in selects:
            sid = s.get_attribute("id") or ""
            sname = s.get_attribute("name") or ""
            opts = s.evaluate("el => Array.from(el.options).slice(0,5).map(o => o.text)")
            print(f"  Select: id={sid} name={sname} opts={opts}")
    
    b.close()

def do_otosemih(p):
    print("\n=== OTOSEMIH ===")
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width":1280,"height":900}, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    pg.goto("https://portal.otosemih.com/giris", timeout=30000)
    pg.wait_for_load_state("networkidle"); time.sleep(2)
    pg.fill('#username', os.getenv("OTOSEMIH_KULLANICI",""))
    pg.fill('#password-input', os.getenv("OTOSEMIH_SIFRE",""))
    pg.click('button[type="submit"]')
    pg.wait_for_load_state("networkidle", timeout=20000); time.sleep(3)
    print(f"  URL: {pg.url}")
    save("otosemih", "afterlogin", pg)
    
    # Lastik sayfasına git
    lastik = pg.query_selector('a[href*="lastik"], a:has-text("Lastik")')
    if lastik:
        href = lastik.get_attribute("href")
        print(f"  Lastik link: {href}")
        lastik.click()
        pg.wait_for_load_state("networkidle", timeout=20000); time.sleep(3)
    print(f"  Lastik URL: {pg.url}")
    save("otosemih", "lastik", pg)
    print(f"  Inputs: {json.dumps(info_inputs(pg), ensure_ascii=False)}")
    print(f"  Tables: {json.dumps(info_tables(pg), ensure_ascii=False)}")
    
    # Selects
    selects = pg.evaluate("""() => {
        return Array.from(document.querySelectorAll('select')).map(s => ({
            id: s.id, name: s.name,
            opts: Array.from(s.options).slice(0,5).map(o => o.text.trim())
        }));
    }""")
    print(f"  Selects: {json.dumps(selects, ensure_ascii=False)}")
    
    b.close()

def do_netlastik(p):
    print("\n=== NETLASTIK ===")
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width":1280,"height":900}, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    pg.goto("https://netlastik.com/", timeout=30000)
    pg.wait_for_load_state("networkidle"); time.sleep(3)
    pg.fill('#email', os.getenv("NETLASTIK_KULLANICI",""))
    pg.fill('#password', os.getenv("NETLASTIK_SIFRE",""))
    pg.click('button[type="submit"]')
    pg.wait_for_load_state("networkidle", timeout=20000); time.sleep(5)
    print(f"  URL: {pg.url}")
    save("netlastik", "afterlogin", pg)
    
    # Menü linklerini bul
    links = pg.evaluate("""() => {
        return Array.from(document.querySelectorAll('a')).filter(a => 
            /lastik|ürün|product|stok|ara/i.test(a.textContent + a.href)
        ).map(a => ({text: a.textContent.trim().substring(0,30), href: a.href}));
    }""")
    print(f"  Relevant links: {json.dumps(links[:10], ensure_ascii=False)}")
    
    # Ürünler sayfasına git
    product_link = pg.query_selector('a[href*="product"], a[href*="urun"], a[href*="lastik"]')
    if product_link:
        product_link.click()
        pg.wait_for_load_state("networkidle", timeout=20000); time.sleep(3)
    print(f"  Products URL: {pg.url}")
    save("netlastik", "products", pg)
    print(f"  Inputs: {json.dumps(info_inputs(pg), ensure_ascii=False)}")
    print(f"  Tables: {json.dumps(info_tables(pg), ensure_ascii=False)}")
    
    b.close()

def do_b2bstore(p, name, url, user_env, pwd_env):
    print(f"\n=== {name.upper()} (B2B Store) ===")
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width":1280,"height":900}, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    pg.goto(url, timeout=30000)
    pg.wait_for_load_state("networkidle"); time.sleep(2)
    
    pg.fill('#userName', os.getenv(user_env, ""))
    pg.fill('#password', os.getenv(pwd_env, ""))
    # B2B Store — butonun JS event'i var
    pg.evaluate("""() => {
        const btns = document.querySelectorAll('button, a.btn, .login-btn');
        for (const b of btns) {
            if (/giriş/i.test(b.textContent)) { b.click(); return true; }
        }
        // Fallback: form submit
        const form = document.querySelector('form');
        if (form) { form.submit(); return true; }
        return false;
    }""")
    pg.wait_for_load_state("networkidle", timeout=20000); time.sleep(5)
    print(f"  URL: {pg.url}")
    body = pg.inner_text("body")[:200]
    print(f"  Body: {body}")
    save(name, "afterlogin", pg)
    
    # Arama linkini bul
    links = pg.evaluate("""() => {
        return Array.from(document.querySelectorAll('a')).filter(a => 
            /ara|ürün|product|stok|katalog/i.test(a.textContent + a.href)
        ).map(a => ({text: a.textContent.trim().substring(0,30), href: a.href})).slice(0,10);
    }""")
    print(f"  Links: {json.dumps(links, ensure_ascii=False)}")
    
    b.close()

def do_uspa(p):
    print("\n=== USPA ===")
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width":1280,"height":900}, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    pg.goto("https://www.uspalastik.com/", timeout=30000)
    pg.wait_for_load_state("networkidle"); time.sleep(5)
    print(f"  Inputs: {json.dumps(info_inputs(pg), ensure_ascii=False)}")
    
    # Tüm input ve butonları bul (JS render sonrası)
    user_inp = pg.query_selector('input#login_email, input[name*="email"], input[name*="user"], input[type="text"], input[type="email"]')
    pwd_inp = pg.query_selector('input[type="password"]')
    
    if user_inp and pwd_inp:
        user_inp.fill(os.getenv("USPA_KULLANICI",""))
        pwd_inp.fill(os.getenv("USPA_SIFRE",""))
        submit = pg.query_selector('button[type="submit"], input[type="submit"], button:has-text("Giriş"), .btn-login')
        if submit: submit.click()
        else: pwd_inp.press("Enter")
        pg.wait_for_load_state("networkidle", timeout=20000); time.sleep(5)
    
    print(f"  URL: {pg.url}")
    save("uspa", "afterlogin", pg)
    body = pg.inner_text("body")[:300]
    print(f"  Body: {body[:200]}")
    
    b.close()

def do_lastsis(p):
    print("\n=== LASTSIS ===")
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width":1280,"height":900}, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    pg.goto("https://panel.lastsis.com/customer-user/login", timeout=30000)
    pg.wait_for_load_state("networkidle"); time.sleep(5)
    print(f"  Inputs: {json.dumps(info_inputs(pg), ensure_ascii=False)}")
    
    user_inp = pg.query_selector('input[type="email"], input[type="text"], input#email')
    pwd_inp = pg.query_selector('input[type="password"]')
    
    if user_inp and pwd_inp:
        user_inp.fill(os.getenv("LASTSIS_KULLANICI",""))
        pwd_inp.fill(os.getenv("LASTSIS_SIFRE",""))
        submit = pg.query_selector('button[type="submit"], button:has-text("Giriş")')
        if submit: submit.click()
        else: pwd_inp.press("Enter")
        pg.wait_for_load_state("networkidle", timeout=20000); time.sleep(5)
    
    print(f"  URL: {pg.url}")
    save("lastsis", "afterlogin", pg)
    body = pg.inner_text("body")[:300]
    print(f"  Body: {body[:200]}")
    
    b.close()

with sync_playwright() as p:
    for fn in [do_cakiroglu, do_otosemih, do_netlastik,
               lambda p: do_b2bstore(p, "tiryakiler", "https://bayi.tiryakilerotomotiv.com/tr/giris", "TIRYAKILER_KULLANICI", "TIRYAKILER_SIFRE"),
               lambda p: do_b2bstore(p, "mollaoglu", "https://bayi.mollaoglu.com.tr/tr/giris", "MOLLAOGLU_KULLANICI", "MOLLAOGLU_SIFRE"),
               do_uspa, do_lastsis]:
        try:
            fn(p)
        except Exception as e:
            print(f"  HATA: {e}")
            traceback.print_exc()
