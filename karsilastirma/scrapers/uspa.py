"""
USPA Lastik B2B Scraper
Site: https://www.uspalastik.com
Altyapı: PHP / OpenCart tabanlı özel sistem

Login URL: index.php?url=account/login
Login form: input[name="email"] + input[name="password"]
Submit: form.submit() via JavaScript (buton yok)
Login başarı: URL değişmez, body'de "Çıkış" görünür

Arama URL: index.php?url=bayi/lastikbul/lastik
Arama formu: input[name="ebat"] — format: 2055516 (205/55R16 → rakamlar birleşik)
Submit: button:has-text("Filtrele")

Tablo sütunları (td index):
0=Resim  1=Ürün Adı  2=Stok Kodu  3=Marka(img)  4=?  5=Dot  6=Stok  7=Fiyat  8=?  9=Adet
Fiyat formatı: 6.600,00 ₺
"""
import re
import time
import logging
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
from .base import BaseScraper, LastikSonuc

logger = logging.getLogger(__name__)

LOGIN_URL  = "https://www.uspalastik.com/index.php?url=account/login"
SEARCH_URL = "https://www.uspalastik.com/index.php?url=bayi/lastikbul/lastik"
HOME_URL   = "https://www.uspalastik.com"


class UspaScraper(BaseScraper):
    TOPTANCI_ADI = "USPA Lastik"

    def login(self, page: Page) -> bool:
        try:
            page.goto(LOGIN_URL, timeout=30_000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(3)

            user_el = page.query_selector('input[name="email"]')
            pass_el = page.query_selector('input[name="password"]')

            if not (user_el and pass_el):
                logger.error(f"[{self.TOPTANCI_ADI}] Login inputları bulunamadı")
                return False

            user_el.fill(self.kullanici)
            pass_el.fill(self.sifre)

            # Submit butonu yok — JavaScript ile form submit
            page.evaluate("document.querySelector('form').submit()")
            page.wait_for_load_state("domcontentloaded", timeout=20_000)
            time.sleep(3)

            body = page.inner_text("body")[:500]
            if any(w in body for w in ["Çıkış", "Hesabım", "Sepetim", "Lastik Sorgulama"]):
                logger.info(f"[{self.TOPTANCI_ADI}] ✅ Login başarılı")
                return True

            logger.warning(f"[{self.TOPTANCI_ADI}] ❌ Login başarısız")
            return False
        except Exception as e:
            logger.error(f"[{self.TOPTANCI_ADI}] Login hatası: {e}")
            return False

    def ara(self, page: Page, ebat: str, marka: str = "") -> list[LastikSonuc]:
        try:
            # Ebatı rakam formatına çevir: 205/55R16 → 2055516
            ebat_rakam = re.sub(r'[^0-9]', '', ebat)
            logger.info(f"[{self.TOPTANCI_ADI}] Ebat rakam: {ebat_rakam}")

            page.goto(SEARCH_URL, timeout=30_000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(3)

            # input[name="ebat"] — placeholder: "Ön: 2254518"
            ebat_el = page.query_selector('input[name="ebat"]')
            if not ebat_el:
                logger.warning(f"[{self.TOPTANCI_ADI}] Ebat inputu bulunamadı")
                return []

            ebat_el.fill(ebat_rakam)
            logger.info(f"[{self.TOPTANCI_ADI}] Ebat girildi: {ebat_rakam}")

            # Filtrele butonuna tıkla
            btn = page.query_selector(
                'button:has-text("Filtrele"), input[value*="Filtrele"], '
                'button[type="submit"], input[type="submit"]'
            )
            if btn:
                btn.click()
                logger.info(f"[{self.TOPTANCI_ADI}] Filtrele tıklandı")
            else:
                ebat_el.press("Enter")

            page.wait_for_load_state("domcontentloaded", timeout=20_000)
            time.sleep(4)

            # Scroll
            for _ in range(3):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)

            # Tablo satırları
            rows = page.query_selector_all("table tbody tr")
            logger.info(f"[{self.TOPTANCI_ADI}] {len(rows)} satır bulundu")

            sonuclar = []
            for row in rows:
                s = self._parse_row(row, ebat, marka)
                if s:
                    sonuclar.append(s)
            return sonuclar

        except Exception as e:
            logger.error(f"[{self.TOPTANCI_ADI}] Arama hatası: {e}")
            return []

    def _parse_row(self, row, ebat_f: str, marka_f: str) -> LastikSonuc | None:
        """
        USPA tablo sütunları (td index):
        0=Resim  1=Ürün Adı  2=Stok Kodu  3=Marka(img)  4=?  5=Dot  6=Stok  7=Fiyat  8=?  9=Adet
        """
        cells = row.query_selector_all("td")
        if len(cells) < 7:
            return None

        texts = [c.inner_text().strip() for c in cells]

        urun_adi  = texts[1] if len(texts) > 1 else ""
        dot       = texts[5] if len(texts) > 5 else ""
        stok      = texts[6] if len(texts) > 6 else "Var"
        fiyat_str = texts[7] if len(texts) > 7 else ""

        # Marka: td[3] içinde img alt veya text
        marka_text = ""
        if len(cells) > 3:
            marka_cell = cells[3]
            img = marka_cell.query_selector("img")
            if img:
                marka_text = img.get_attribute("alt") or img.get_attribute("title") or ""
            if not marka_text:
                marka_text = texts[3]

        if not urun_adi or len(urun_adi) < 3:
            return None

        # Ebat filtresi — rakamları karşılaştır
        if ebat_f:
            from .base import _ebat_eslesir
            if not _ebat_eslesir(ebat_f, urun_adi):
                return None

        # Marka filtresi
        if marka_f and marka_f.lower() not in (urun_adi.lower() + marka_text.lower()):
            return None

        # Ebat — ürün adından çıkar
        ebat_match = re.search(r'(\d{3}/\d{2}\s*R?\s*\d{2,3})', urun_adi)
        ebat = ebat_match.group(1).replace(" ", "") if ebat_match else ebat_f

        # Marka — ürün adından da çıkar
        if not marka_text:
            markalar = ["Continental", "Michelin", "Pirelli", "Bridgestone", "Goodyear",
                        "Lassa", "Petlas", "Hankook", "Dunlop", "Yokohama", "Nokian",
                        "Starmaxx", "Nexen", "Kumho", "Falken", "Firestone", "Maxxis",
                        "Linglong", "Triangle", "Kormoran", "BFGoodrich", "Debica", "Tigar",
                        "Accelera", "Nankang", "Toyo"]
            marka_text = next((m for m in markalar if m.lower() in urun_adi.lower()), "—")

        # Mevsim
        mevsim = "Yaz"
        low = urun_adi.lower()
        if "kış" in low or "winter" in low or "kis" in low or "w " in low:
            mevsim = "Kış"
        elif "4 mevsim" in low or "all season" in low or "allseason" in low:
            mevsim = "4 Mevsim"

        fiyat = self._fiyat_parse(fiyat_str)
        if fiyat < 100:
            return None

        return self.sonuc_olustur(
            marka=marka_text,
            model=urun_adi,
            ebat=ebat,
            mevsim=mevsim,
            dot=dot,
            fiyat=fiyat,
            para_birimi="TL",
            stok=stok or "Var",
            site_url=SEARCH_URL,
        )

    @staticmethod
    def _fiyat_parse(s: str) -> float:
        try:
            t = s.replace("₺", "").replace("TL", "").replace(".", "").replace(",", ".").strip()
            m = re.search(r'[\d]+\.?\d*', t)
            return float(m.group()) if m else 0.0
        except Exception:
            return 0.0
