"""
NetLastik B2B Scraper
Site: https://netlastik.com
Altyapı: Next.js (React SSR)

Login: #email + #password → /login
Ürün arama: /products?search=<ebat>  veya  /search?q=<ebat>
Ürünler: Next.js render — wait_for_selector ile bekle
"""
import re
import time
import logging
from urllib.parse import quote
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
from .base import BaseScraper, LastikSonuc, _ebat_eslesir

logger = logging.getLogger(__name__)

LOGIN_URL = "https://netlastik.com/login"
HOME_URL  = "https://netlastik.com"


class NetLastikScraper(BaseScraper):
    TOPTANCI_ADI = "NetLastik"

    def login(self, page: Page) -> bool:
        try:
            page.goto(LOGIN_URL, timeout=30_000)
            page.wait_for_load_state("networkidle", timeout=15_000)
            time.sleep(2)

            # NetLastik sometimes opens the SMS login tab by default.
            try:
                email_tab = page.locator("button:has-text('E-posta'), [role='tab']:has-text('E-posta')").first
                if email_tab.count() and email_tab.is_visible(timeout=1000):
                    email_tab.click(timeout=3000)
                    time.sleep(0.8)
            except Exception:
                pass

            # Next.js: #email + #password
            user_el = page.query_selector('#email, input[name="email"], input[type="email"]')
            pass_el = page.query_selector('#password, input[name="password"], input[type="password"]')

            if not (user_el and pass_el):
                logger.error(f"[{self.TOPTANCI_ADI}] Login inputları bulunamadı")
                return False

            user_el.fill(self.kullanici)
            pass_el.fill(self.sifre)

            # Prefer submitting the focused email/password form. Some tab buttons
            # also have submit-like markup, so a broad button selector can switch
            # back to SMS login instead of signing in.
            page.keyboard.press("Enter")
            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass
            time.sleep(2)
            early_url = page.url.lower()
            early_body = page.inner_text("body")[:1200].lower()
            if "login" not in early_url:
                logger.info(f"[{self.TOPTANCI_ADI}] Login başarılı (email form)")
                return True
            if any(w in early_body for w in ["çıkış", "sepet", "siparişler", "orders", "profil", "ürünler", "products"]):
                logger.info(f"[{self.TOPTANCI_ADI}] Login başarılı (email body)")
                return True

            btn = page.query_selector(
                'button[type="submit"], button:has-text("Giriş"), button:has-text("Login"), input[type="submit"]'
            )
            if btn:
                btn.click()
            else:
                page.keyboard.press("Enter")

            # login sonrası sayfanın gerçek şekilde yüklendiğini bekle (Next.js)
            try:
                # dashboard/product page işaretleri
                page.wait_for_selector("[class*='ProductCard'], [data-testid*='product'], nav, main", timeout=15_000)
            except Exception:
                pass

            page.wait_for_load_state("domcontentloaded", timeout=10_000)
            time.sleep(2)

            url  = page.url.lower()
            body = page.inner_text("body")[:1200].lower()

            # Eğer hâlâ giriş sayfasındaysa ya da hata mesajı varsa başarısız kabul et
            if "login" in url or "giriş" in body[:400]:
                if any(w in body for w in ["şifre", "email", "hatal", "invalid", "denied"]):
                    logger.warning(f"[{self.TOPTANCI_ADI}] ❌ Login başarısız (invalid) — URL: {page.url}")
                    return False

            if any(w in body for w in ["çıkış", "sepet", "siparişler", "orders", "profil", "ürünler", "products"]):
                logger.info(f"[{self.TOPTANCI_ADI}] ✅ Login başarılı (body)")
                return True

            # En son fallback: giriş sayfasına dönülmediyse kabul et
            if "login" not in url:
                logger.info(f"[{self.TOPTANCI_ADI}] ✅ Login başarılı (URL)")
                return True

            logger.warning(f"[{self.TOPTANCI_ADI}] ❌ Login başarısız — URL: {page.url}")
            return False

        except Exception as e:
            logger.error(f"[{self.TOPTANCI_ADI}] Login hatası: {e}")
            return False

    def ara(self, page: Page, ebat: str, marka: str = "") -> list[LastikSonuc]:
        try:
            sorgu = f"{ebat} {marka}".strip()
            sorgu_url = quote(sorgu)

            # Next.js arama URL'leri
            search_urls = [
                f"{HOME_URL}/?search={sorgu_url}",
                f"{HOME_URL}/lastikler?search={sorgu_url}",
                f"{HOME_URL}/products?search={sorgu_url}",
                f"{HOME_URL}/search?q={sorgu_url}",
                f"{HOME_URL}/urunler?search={sorgu_url}",
            ]

            for url in search_urls:
                try:
                    page.goto(url, timeout=20_000)
                    page.wait_for_load_state("networkidle", timeout=10_000)
                    self._dismiss_overlays(page)
                    self._try_search_box(page, ebat)
                    time.sleep(3)
                    body = page.inner_text("body")[:300].lower()
                    if "404" not in body and "bulunamadı" not in body[:50]:
                        logger.info(f"[{self.TOPTANCI_ADI}] Arama URL: {url}")
                        break
                except Exception:
                    continue

            # Scroll — lazy load
            prev_len = 0
            for rnd in range(100):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.5)
                cur = len(page.inner_text("body"))
                if cur == prev_len and rnd > 5:
                    break
                prev_len = cur

            # Next.js ürün selector'ları
            urun_selectors = [
                "[class*='ProductCard']",
                "[class*='product-card']",
                "[class*='ProductItem']",
                "[class*='product-item']",
                ".product-card",
                "article",
                "[data-testid*='product']",
                "table tbody tr",
            ]

            urunler = []
            for sel in urun_selectors:
                urunler = page.query_selector_all(sel)
                if urunler and len(urunler) > 0:
                    logger.info(f"[{self.TOPTANCI_ADI}] {len(urunler)} ürün ({sel})")
                    break

            if not urunler:
                body_text = page.inner_text("body")
                return self._body_parse(body_text, ebat, marka)

            sonuclar = []
            seen = set()
            for u in urunler:
                s = self._parse_urun(u, ebat, marka)
                if s:
                    key = (s.marka.lower(), s.model.lower(), s.ebat.lower(), round(s.fiyat, 2), s.dot.lower())
                    if key in seen:
                        continue
                    seen.add(key)
                    sonuclar.append(s)
            return sonuclar

        except Exception as e:
            logger.error(f"[{self.TOPTANCI_ADI}] Arama hatası: {e}")
            return []

    def _parse_urun(self, urun, ebat_f: str, marka_f: str) -> LastikSonuc | None:
        try:
            text = urun.inner_text().strip()
            if not text or len(text) < 5:
                return None

            cells = [c.inner_text().strip() for c in urun.query_selector_all("td")]
            if len(cells) >= 7:
                return self._parse_table_cells(cells, ebat_f, marka_f)

            fm = re.search(r'([\d.,]+)\s*(?:TL|₺)', text)
            if not fm:
                return None

            fiyat = self._fiyat_parse(fm.group(1))
            if fiyat < 100 or fiyat > 100_000:
                return None

            lines = [l.strip() for l in text.split('\n') if l.strip()]
            urun_adi = lines[0] if lines else ""
            full = text.lower()

            if ebat_f and not _ebat_eslesir(ebat_f, text):
                return None

            if marka_f and marka_f.lower() not in full:
                return None

            em = re.search(r'(\d{3}/\d{2}\s*R?\d{2,3})', text)
            ebat = em.group(1) if em else ebat_f

            markalar = ["Continental","Michelin","Pirelli","Bridgestone","Goodyear",
                        "Lassa","Petlas","Hankook","Dunlop","Yokohama","Nokian",
                        "Starmaxx","Nexen","Kumho","Falken","Firestone","Maxxis",
                        "Linglong","Triangle","Kormoran","Nankang","Toyo"]
            marka = next((m for m in markalar if m.lower() in full), "Diğer")

            mevsim = "Yaz"
            if "kış" in full or "winter" in full or "kis" in full:
                mevsim = "Kış"
            elif "4 mevsim" in full or "all season" in full:
                mevsim = "4 Mevsim"

            return self.sonuc_olustur(
                marka=marka, model=urun_adi, ebat=ebat,
                mevsim=mevsim, dot="", fiyat=fiyat,
                para_birimi="TL", stok="Var", site_url=HOME_URL
            )
        except Exception:
            return None

    def _parse_table_cells(self, cells: list[str], ebat_f: str, marka_f: str) -> LastikSonuc | None:
        full = " ".join(cells)
        full_lower = full.lower()
        if ebat_f and not _ebat_eslesir(ebat_f, full):
            return None
        if marka_f and marka_f.lower() not in full_lower:
            return None

        model = next(
            (c for c in cells if re.search(r"\d{3}/\d{2}\s*(?:Z?R|/)?\s*\d{2,3}", c, re.I)),
            cells[0],
        )
        ebat_match = re.search(r"(\d{3}/\d{2}\s*(?:Z?R|/)?\s*\d{2,3}\s*C?)", model, re.I)
        ebat = re.sub(r"\s+", "", ebat_match.group(1)) if ebat_match else ebat_f
        ebat = re.sub(r"(?i)ZR", "R", ebat)
        ebat = re.sub(r"(\d{3}/\d{2})/(\d{2,3})", r"\1R\2", ebat)

        fiyat = 0.0
        for cell in reversed(cells):
            fiyat = self._fiyat_parse(cell)
            if fiyat >= 100:
                break
        if fiyat < 100:
            return None

        markalar = ["Continental", "Michelin", "Pirelli", "Bridgestone", "Goodyear",
                    "Lassa", "Petlas", "Hankook", "Dunlop", "Yokohama", "Nokian",
                    "Starmaxx", "Nexen", "Kumho", "Falken", "Firestone", "Maxxis",
                    "Linglong", "Triangle", "Kormoran", "Nankang", "Toyo", "Waterfall",
                    "Kleber", "Marshal", "Laufenn"]
        marka = next((m for m in markalar if m.lower() in full_lower), "Diğer")
        dot = "/".join(dict.fromkeys(re.findall(r"\b20\d{2}\b", full)[:3]))
        stok_match = re.search(r"\b(\+?\d{1,3})\s*(?:adet|stok)?\b", full, re.I)
        stok = stok_match.group(1) if stok_match else "Var"

        mevsim = "Yaz"
        if any(w in full_lower for w in ["kış", "kis", "winter", "snow"]):
            mevsim = "Kış"
        elif any(w in full_lower for w in ["4 mevsim", "all season", "allseason"]):
            mevsim = "4 Mevsim"

        return self.sonuc_olustur(
            marka=marka, model=model, ebat=ebat,
            mevsim=mevsim, dot=dot, fiyat=fiyat,
            para_birimi="TL", stok=stok, site_url=HOME_URL
        )

    def _body_parse(self, body: str, ebat_f: str, marka_f: str) -> list[LastikSonuc]:
        sonuclar = []
        for m in re.finditer(r'(.{0,100})([\d.,]+)\s*(?:TL|₺)', body):
            ctx   = m.group(1)
            fiyat = self._fiyat_parse(m.group(2))
            if fiyat < 100 or fiyat > 100_000:
                continue
            em = re.search(r'(\d{3}/\d{2}\s*R?\d{2,3})', ctx)
            if not em:
                continue
            if ebat_f and not _ebat_eslesir(ebat_f, ctx):
                continue
            sonuclar.append(self.sonuc_olustur(
                marka="Diğer", model=ctx.strip()[:60],
                ebat=em.group(1), mevsim="Yaz", dot="",
                fiyat=fiyat, para_birimi="TL", stok="Var", site_url=HOME_URL
            ))
        return sonuclar

    @staticmethod
    def _fiyat_parse(s: str) -> float:
        try:
            t = s.replace("₺","").replace("TL","").replace(".","").replace(",",".").strip()
            m = re.search(r'[\d]+\.?\d*', t)
            return float(m.group()) if m else 0.0
        except Exception:
            return 0.0

    def _dismiss_overlays(self, page: Page) -> None:
        for _ in range(3):
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
            for selector in [
                "button:has-text('Kabul Ediyorum')",
                "button:has-text('Okudum')",
                "button:has-text('Kapat')",
                "button[aria-label='Close']",
                "button[aria-label='close']",
            ]:
                try:
                    loc = page.locator(selector).first
                    if loc.count() and loc.is_visible(timeout=500) and loc.is_enabled(timeout=500):
                        loc.click(timeout=1000)
                except Exception:
                    continue
            time.sleep(0.3)

    def _try_search_box(self, page: Page, ebat: str) -> bool:
        selectors = [
            "input[type='search']",
            "input[placeholder*='Ara']",
            "input[placeholder*='Ürün']",
            "input[placeholder*='Ebat']",
            "input[name*='search']",
            "input[id*='search']",
        ]
        for selector in selectors:
            try:
                loc = page.locator(selector).first
                if loc.count() == 0 or not loc.is_visible(timeout=800):
                    continue
                loc.fill(ebat, timeout=2000)
                loc.press("Enter", timeout=2000)
                page.wait_for_load_state("networkidle", timeout=8000)
                return True
            except Exception:
                continue
        return False
