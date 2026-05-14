"""Tüm sitelere login yapıp ürün sayfası DOM'unu kaydet."""
import os, sys, time, json
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
load_dotenv()

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "_dom_dumps")
os.makedirs(OUTPUT_DIR, exist_ok=True)

SITES = [
    {
        "name": "tiryakiler",
        "login_url": "https://bayi.tiryakilerotomotiv.com/tr/giris",
        "user": os.getenv("TIRYAKILER_KULLANICI", ""),
        "pwd": os.getenv("TIRYAKILER_SIFRE", ""),
        "search_query": "205/55R16",
    },
    {
        "name": "mollaoglu",
        "login_url": "https://bayi.mollaoglu.com.tr/tr/giris",
        "user": os.getenv("MOLLAOGLU_KULLANICI", ""),
        "pwd": os.getenv("MOLLAOGLU_SIFRE", ""),
        "search_query": "205/55R16",
    },
    {
        "name": "uspa",
        "login_url": "https://www.uspalastik.com/",
        "user": os.getenv("USPA_KULLANICI", ""),
        "pwd": os.getenv("USPA_SIFRE", ""),
        "search_query": "205/55R16",
    },
    {
        "name": "lastsis",
        "login_url": "https://panel.lastsis.com/customer-user/login",
        "user": os.getenv("LASTSIS_KULLANICI", ""),
        "pwd": os.getenv("LASTSIS_SIFRE", ""),
        "search_query": "205/55R16",
    },
    {
        "name": "cakiroglu",
        "login_url": "http://b2b.cakirogluotomotiv.com/B2B_Stoklar.asp",
        "user": os.getenv("CAKIROGLU_KULLANICI", ""),
        "pwd": os.getenv("CAKIROGLU_SIFRE", ""),
        "search_query": "205/55R16",
    },
    {
        "name": "netlastik",
        "login_url": "https://netlastik.com/",
        "user": os.getenv("NETLASTIK_KULLANICI", ""),
        "pwd": os.getenv("NETLASTIK_SIFRE", ""),
        "search_query": "205/55R16",
    },
    {
        "name": "otosemih",
        "login_url": "https://portal.otosemih.com/giris",
        "user": os.getenv("OTOSEMIH_KULLANICI", ""),
        "pwd": os.getenv("OTOSEMIH_SIFRE", ""),
        "search_query": "205/55R16",
    },
]

def discover_site(p, site):
    name = site["name"]
    print(f"\n{'='*60}")
    print(f"[{name.upper()}] Başlatılıyor...")
    print(f"  URL: {site['login_url']}")
    print(f"  User: {site['user'][:10]}...")
    
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    page = context.new_page()
    
    results = {"name": name, "login_ok": False, "login_url_after": "", "search_ok": False}
    
    try:
        # 1. Login sayfasına git
        page.goto(site["login_url"], timeout=30000)
        page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(2)
        
        # Login sayfası DOM'unu kaydet
        login_html = page.content()
        with open(os.path.join(OUTPUT_DIR, f"{name}_login.html"), "w", encoding="utf-8") as f:
            f.write(login_html)
        
        # Login form elemanlarını bul
        inputs = page.query_selector_all("input")
        input_info = []
        for inp in inputs:
            inp_type = inp.get_attribute("type") or ""
            inp_name = inp.get_attribute("name") or ""
            inp_id = inp.get_attribute("id") or ""
            inp_ph = inp.get_attribute("placeholder") or ""
            input_info.append({"type": inp_type, "name": inp_name, "id": inp_id, "placeholder": inp_ph})
        
        print(f"  Login form inputs: {json.dumps(input_info, ensure_ascii=False)}")
        results["login_inputs"] = input_info
        
        # 2. Login dene - text/email inputa kullanıcı, password inputa şifre
        text_inputs = [i for i in inputs if (i.get_attribute("type") or "").lower() in ("text", "email", "")]
        pwd_inputs = [i for i in inputs if (i.get_attribute("type") or "").lower() == "password"]
        
        if text_inputs and pwd_inputs:
            text_inputs[0].fill(site["user"])
            pwd_inputs[0].fill(site["pwd"])
            
            # Submit butonu bul
            submit = page.query_selector('button[type="submit"], input[type="submit"]')
            if submit:
                submit.click()
            else:
                # Form varsa submit et
                form = page.query_selector("form")
                if form:
                    pwd_inputs[0].press("Enter")
            
            page.wait_for_load_state("networkidle", timeout=20000)
            time.sleep(3)
            
            after_url = page.url
            results["login_url_after"] = after_url
            print(f"  Login sonrası URL: {after_url}")
            
            # Login başarılı mı?
            if after_url != site["login_url"]:
                results["login_ok"] = True
                print(f"  ✅ Login başarılı!")
            else:
                # Sayfada hata mesajı var mı?
                body = page.inner_text("body")[:500]
                print(f"  ❌ Login başarısız? Body: {body[:200]}")
                results["login_error"] = body[:200]
        else:
            print(f"  ❌ Login form bulunamadı (text: {len(text_inputs)}, pwd: {len(pwd_inputs)})")
        
        # 3. Login başarılıysa ürün ara
        if results["login_ok"]:
            # Sayfadaki arama kutusunu bul
            after_login_html = page.content()
            with open(os.path.join(OUTPUT_DIR, f"{name}_afterlogin.html"), "w", encoding="utf-8") as f:
                f.write(after_login_html)
            
            # Arama inputu bul
            search_input = page.query_selector(
                'input[placeholder*="Ara"], input[placeholder*="ara"], '
                'input[placeholder*="Ürün"], input[placeholder*="ürün"], '
                'input[placeholder*="Ebat"], input[placeholder*="ebat"], '
                'input[name*="search"], input[name*="q"], '
                'input[type="search"], .search-input, #search'
            )
            
            if search_input:
                search_input.fill(site["search_query"])
                search_input.press("Enter")
                page.wait_for_load_state("networkidle", timeout=30000)
                time.sleep(5)
                results["search_ok"] = True
                print(f"  🔍 Arama yapıldı: {site['search_query']}")
            else:
                # URL'ye arama parametresi ekle
                print(f"  ⚠️ Arama inputu bulunamadı, sayfa DOM'u kaydedildi")
            
            # Arama sonuç sayfası
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            search_html = page.content()
            with open(os.path.join(OUTPUT_DIR, f"{name}_search.html"), "w", encoding="utf-8") as f:
                f.write(search_html)
            
            # Sayfa yapısı hakkında bilgi topla
            table_count = page.evaluate("document.querySelectorAll('table').length")
            tr_count = page.evaluate("document.querySelectorAll('tr').length")
            div_tr_count = page.evaluate("document.querySelectorAll('div.tr').length")
            product_divs = page.evaluate("""() => {
                const selectors = ['.product', '.urun', '.item', '[class*=product]', '[class*=urun]', '.card'];
                const counts = {};
                selectors.forEach(s => { counts[s] = document.querySelectorAll(s).length; });
                return counts;
            }""")
            
            results["page_info"] = {
                "url": page.url,
                "tables": table_count,
                "tr_rows": tr_count,
                "div_tr": div_tr_count,
                "product_elements": product_divs,
            }
            print(f"  Sayfa yapısı: tables={table_count}, tr={tr_count}, div.tr={div_tr_count}")
            print(f"  Product elements: {product_divs}")
            
            # Ekran görüntüsü
            page.screenshot(path=os.path.join(OUTPUT_DIR, f"{name}_screenshot.png"), full_page=False)
    
    except Exception as e:
        print(f"  ❌ HATA: {e}")
        results["error"] = str(e)
    finally:
        browser.close()
    
    return results

def main():
    all_results = []
    with sync_playwright() as p:
        for site in SITES:
            result = discover_site(p, site)
            all_results.append(result)
    
    # Sonuçları kaydet
    with open(os.path.join(OUTPUT_DIR, "_summary.json"), "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print("\n" + "="*60)
    print("ÖZET:")
    for r in all_results:
        status = "✅" if r["login_ok"] else "❌"
        print(f"  {status} {r['name']}: login={'OK' if r['login_ok'] else 'FAIL'}, URL={r.get('login_url_after','')[:60]}")

if __name__ == "__main__":
    main()
