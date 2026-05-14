"""
Çakıroğlu Otomotiv B2B Scraper
Site: http://b2b.cakirogluotomotiv.com
Altyapı: Classic ASP

Login: name="USER" + name="SIFRE"
Arama: form#lastik → input name="URUN1"
Tablo: table.ptable → tbody tr
Sütunlar: İNCELE | ÜRÜN KODU | MARKA | ÜRÜN | DOT | MEVSİM | ETİKET | ÖZELLİK | NET FİYAT | STOK | SİPARİŞ
"""
import re
import time
import logging
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
from .base import BaseScraper, LastikSonuc

logger = logging.getLogger(__name__)

LOGIN_URL  = "http://b2b.cakirogluotomotiv.com/"
STOKLAR_URL = "http://b2b.cakirogluotomotiv.com/B2B_Stoklar.asp"


class CakirogluScraper(BaseScraper):
    TOPTANCI_ADI = "Çakıroğlu Otomotiv"

    def login(self, page: Page) -> bool:
        try:
            page.goto(LOGIN_URL, timeout=30_000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(2)

            user_el = page.query_selector('input[name="USER"]')
            pass_el = page.query_selector('input[name="SIFRE"]')

            if not (user_el and pass_el):
                logger.error(f"[{self.TOPTANCI_ADI}] Login inputları bulunamadı")
                return False

            user_el.fill(self.kullanici)
            pass_el.fill(self.sifre)

            btn = page.query_selector('button[type="submit"], input[type="submit"]')
            if btn:
                btn.click()
            else:
                page.keyboard.press("Enter")

            page.wait_for_load_state("domcontentloaded", timeout=20_000)
            time.sleep(3)

            body = page.inner_text("body")[:500]
            url  = page.url

            if any(w in body for w in ["ERHAN", "MESLAS", "Stoklar", "Çıkış", "Sipariş"]):
                logger.info(f"[{self.TOPTANCI_ADI}] ✅ Login başarılı")
                return True
            if "B2B_" in url or "Default" in url or "Tablet" in url:
                logger.info(f"[{self.TOPTANCI_ADI}] ✅ Login başarılı (URL)")
                return True

            logger.warning(f"[{self.TOPTANCI_ADI}] ❌ Login başarısız — URL: {url}")
            return False
        except Exception as e:
            logger.error(f"[{self.TOPTANCI_ADI}] Login hatası: {e}")
            return False

    def ara(self, page: Page, ebat: str, marka: str = "") -> list[LastikSonuc]:
        try:
            page.goto(STOKLAR_URL, timeout=30_000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(4)

            # Arama formu: input name="URUN1"
            urun1 = page.query_selector('input[name="URUN1"]')
            if urun1:
                urun1.fill(ebat)
                logger.info(f"[{self.TOPTANCI_ADI}] URUN1 alanına '{ebat}' yazıldı")
                # Formu submit et
                btn = page.query_selector('button[onclick*="lastik"], button.blue-chambray, button[type="button"]:has-text("Ara")')
                if btn:
                    btn.click()
                else:
                    page.query_selector('form#lastik button').click() if page.query_selector('form#lastik button') else page.keyboard.press("Enter")
                time.sleep(5)

                # DataTables'ta tüm ürünleri göster — sayfa boyutunu artır
                try:
                    length_select = page.query_selector('select[name*="DataTables_Table"][name*="length"], .dataTables_length select')
                    if length_select:
                        options = length_select.query_selector_all("option")
                        if options:
                            length_select.select_option(options[-1].get_attribute("value"))
                            time.sleep(3)
                except Exception:
                    pass
            else:
                # DataTables search kutusu
                search = page.query_selector('.dataTables_filter input, input[type="search"]')
                if search:
                    search.fill(ebat)
                    time.sleep(3)

            # Scroll
            for _ in range(3):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)

            # Tablo satırları: table.ptable tbody tr
            rows = page.query_selector_all("table.ptable tbody tr, table.table-hover tbody tr")
            if not rows:
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
        Sütun sırası (DOM dump'a göre):
        0=İNCELE  1=ÜRÜN KODU  2=MARKA  3=ÜRÜN  4=DOT  5=MEVSİM  6=ETİKET  7=ÖZELLİK  8=NET FİYAT  9=STOK  10=SİPARİŞ
        """
        cells = row.query_selector_all("td")
        if len(cells) < 9:
            return None

        texts = [c.inner_text().strip() for c in cells]

        marka_text = texts[2] if len(texts) > 2 else ""
        urun_adi   = texts[3] if len(texts) > 3 else ""
        dot        = texts[4] if len(texts) > 4 else ""
        mevsim_raw = texts[5] if len(texts) > 5 else ""
        fiyat_str  = texts[8] if len(texts) > 8 else ""
        stok       = texts[9] if len(texts) > 9 else "Bilinmiyor"

        if not urun_adi:
            return None

        # Ebat filtresi
        full = " ".join(texts).lower()
        if ebat_f:
            from .base import _ebat_eslesir
            if not _ebat_eslesir(ebat_f, full):
                return None

        # Marka filtresi
        if marka_f and marka_f.lower() not in full:
            return None

        # Ebat — ürün adından çıkar
        ebat_match = re.search(r'(\d{3}/\d{2}\s*R?\d{2,3})', urun_adi)
        ebat = ebat_match.group(1) if ebat_match else ebat_f

        # Mevsim
        mevsim = "Yaz"
        mv = (mevsim_raw + " " + urun_adi).lower()
        if "kış" in mv or "kis" in mv or "winter" in mv or "kıs" in mv:
            mevsim = "Kış"
        elif "4 mevsim" in mv or "all season" in mv or "dörtmevsim" in mv:
            mevsim = "4 Mevsim"

        fiyat = self._fiyat_parse(fiyat_str)
        if fiyat < 100:
            return None

        return self.sonuc_olustur(
            marka=marka_text or "—",
            model=urun_adi,
            ebat=ebat,
            mevsim=mevsim,
            dot=dot,
            fiyat=fiyat,
            para_birimi="TL",
            stok=stok or "Var",
            site_url=STOKLAR_URL,
        )

    @staticmethod
    def _fiyat_parse(s: str) -> float:
        try:
            t = s.replace("₺","").replace("TL","").replace(".","").replace(",",".").strip()
            m = re.search(r'[\d]+\.?\d*', t)
            return float(m.group()) if m else 0.0
        except Exception:
            return 0.0
