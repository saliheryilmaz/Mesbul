"""
Koç Otomotiv B2B Scraper
Site: https://www.kocotomotiv.com.tr
Altyapı: PHP / Özel sistem

Login: input[name="kullaniciadi"] + input[name="password"]
Login sonrası: anasayfa.php (aynı sayfada arama formu var)

Arama formu (anasayfa.php'de):
  input[name="Kelime"]   — ebat / ürün kodu
  input[name="Kelime2"]  — 2. ebat (opsiyonel)
  checkbox: yazlastik, dortmevsim, kislastik, runflat
  id="basla" butonu — submit

Tablo sütunları (tbody tr):
  0=Mevsim  1=Ürün Kodu  2=Marka  3=Ürün Adı  4=Dot  5=Detay  6=Fiyat  7=Nakit/Havale  8=Stok  9=Sepete Ekle
Fiyat formatı: 3.500,00 TL
"""
import re
import time
import logging
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
from .base import BaseScraper, LastikSonuc

logger = logging.getLogger(__name__)

LOGIN_URL = "https://www.kocotomotiv.com.tr/"
HOME_URL  = "https://kocotomotiv.com.tr"


class KocOtomotivScraper(BaseScraper):
    TOPTANCI_ADI = "Koç Otomotiv"

    def login(self, page: Page) -> bool:
        try:
            page.goto(LOGIN_URL, timeout=30_000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(2)

            # Koç Otomotiv: input[name="kullaniciadi"] + input[name="password"]
            user_el = page.query_selector('input[name="kullaniciadi"]')
            pass_el = page.query_selector('input[name="password"]')

            if not (user_el and pass_el):
                logger.error(f"[{self.TOPTANCI_ADI}] Login inputları bulunamadı")
                return False

            user_el.fill(self.kullanici)
            pass_el.fill(self.sifre)

            btn = page.query_selector('button[type="submit"], input[type="submit"], button:has-text("Giriş")')
            if btn:
                btn.click()
            else:
                page.keyboard.press("Enter")

            page.wait_for_load_state("domcontentloaded", timeout=20_000)
            time.sleep(3)

            body = page.inner_text("body")[:500]
            url  = page.url.lower()

            if any(w in body for w in ["ERHAN", "Sepetim", "Siparişlerim", "Bakiye", "Ana Sayfa"]):
                logger.info(f"[{self.TOPTANCI_ADI}] ✅ Login başarılı")
                return True
            if "anasayfa" in url or "login" not in url:
                logger.info(f"[{self.TOPTANCI_ADI}] ✅ Login başarılı (URL)")
                return True

            logger.warning(f"[{self.TOPTANCI_ADI}] ❌ Login başarısız — URL: {page.url}")
            return False
        except Exception as e:
            logger.error(f"[{self.TOPTANCI_ADI}] Login hatası: {e}")
            return False

    def ara(self, page: Page, ebat: str, marka: str = "") -> list[LastikSonuc]:
        try:
            # Arama formu anasayfa.php'de — zaten oradayız
            # Eğer değilsek git
            if "anasayfa" not in page.url.lower():
                page.goto(f"{HOME_URL}/anasayfa.php", timeout=30_000)
                page.wait_for_load_state("domcontentloaded")
                time.sleep(2)

            # Kelime alanını doldur
            kelime = page.query_selector('input[name="Kelime"]')
            if not kelime:
                logger.warning(f"[{self.TOPTANCI_ADI}] Kelime inputu bulunamadı")
                return []

            kelime.fill(ebat)
            logger.info(f"[{self.TOPTANCI_ADI}] Arama: {ebat}")

            # Ürün Bul butonuna tıkla
            btn = page.query_selector('#basla, button:has-text("Ürün Bul"), input[value*="Bul"]')
            if btn:
                btn.click()
            else:
                kelime.press("Enter")

            page.wait_for_load_state("domcontentloaded", timeout=20_000)
            time.sleep(4)

            # Sayfa boyutunu büyüt (DataTables/benzeri)
            try:
                length_select = page.query_selector(
                    'select[name*="length"], .dataTables_length select, select[id*="length"]'
                )
                if length_select:
                    options = length_select.query_selector_all("option")
                    if options:
                        last_val = options[-1].get_attribute("value")
                        if last_val:
                            length_select.select_option(last_val)
                            time.sleep(2)
            except Exception:
                pass

            # Tüm sayfaları dolaşarak satırları topla
            rows = self._collect_all_rows(page)
            logger.info(f"[{self.TOPTANCI_ADI}] Toplam {len(rows)} satır toplandı")

            sonuclar = []
            seen = set()
            for row in rows:
                s = self._parse_row(row, ebat, marka)
                if not s:
                    continue
                key = (
                    s.marka.strip().lower(),
                    s.model.strip().lower(),
                    s.ebat.strip().lower(),
                    round(s.fiyat, 2),
                    s.dot.strip().lower(),
                )
                if key in seen:
                    continue
                seen.add(key)
                sonuclar.append(s)
            return sonuclar

        except Exception as e:
            logger.error(f"[{self.TOPTANCI_ADI}] Arama hatası: {e}")
            return []

    def _collect_all_rows(self, page: Page) -> list:
        """Tablo satırlarını mümkünse tüm sayfalardan toplar."""
        tum_rows = []
        max_page = 100  # güvenlik sınırı

        for _ in range(max_page):
            for _ in range(2):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.0)

            rows = page.query_selector_all("table tbody tr")
            if rows:
                tum_rows.extend(rows)

            next_btn = page.query_selector(
                '.dataTables_paginate a.next:not(.disabled), '
                '.pagination .next:not(.disabled), '
                'a[rel="next"], '
                'button[aria-label*="Next"]:not([disabled])'
            )
            if not next_btn:
                break

            try:
                next_btn.click()
                time.sleep(4.0)
            except Exception:
                break

        return tum_rows

    def _parse_row(self, row, ebat_f: str, marka_f: str) -> LastikSonuc | None:
        """
        Koç Otomotiv tablo sütunları:
        0=Mevsim  1=Ürün Kodu  2=Marka  3=Ürün Adı  4=Dot  5=Detay  6=Fiyat  7=Nakit/Havale  8=Stok  9=Sepete Ekle
        """
        cells = row.query_selector_all("td")
        if len(cells) < 7:
            return None

        texts = [c.inner_text().strip() for c in cells]

        mevsim_raw = texts[0] if len(texts) > 0 else ""
        marka_text = texts[2] if len(texts) > 2 else ""
        urun_adi   = texts[3] if len(texts) > 3 else ""
        dot        = texts[4] if len(texts) > 4 else ""
        fiyat_str  = texts[6] if len(texts) > 6 else ""
        stok       = texts[8] if len(texts) > 8 else "Var"

        if not urun_adi or len(urun_adi) < 5:
            return None

        # Başlık satırını atla
        if "Ürün Adı" in urun_adi or "Marka" in marka_text:
            return None

        full = " ".join(texts).lower()

        # Ebat filtresi
        if ebat_f:
            from .base import _ebat_eslesir
            if not _ebat_eslesir(ebat_f, full):
                return None

        # Marka filtresi
        if marka_f and marka_f.lower() not in (full + marka_text.lower()):
            return None

        # Ebat
        ebat_match = re.search(r'(\d{3}/\d{2}\s*R?\s*\d{2,3})', urun_adi)
        ebat = ebat_match.group(1).replace(" ", "") if ebat_match else ebat_f

        # Marka normalize et (Koç'ta "Brıdgestone", "Mıchelın" gibi yazıyor)
        marka_norm = (marka_text
                      .replace("ı", "i").replace("İ", "I")
                      .title())

        # Mevsim
        mevsim = "Yaz"
        mv = mevsim_raw.lower()
        if "kış" in mv or "kis" in mv or "winter" in mv:
            mevsim = "Kış"
        elif "4 mevsim" in mv or "all season" in mv or "mevsim" in mv:
            mevsim = "4 Mevsim"

        fiyat = self._fiyat_parse(fiyat_str)
        if fiyat < 100:
            return None

        # Stok temizle
        stok_clean = stok.replace("Ekle", "").strip() or "Var"

        return self.sonuc_olustur(
            marka=marka_norm or "—",
            model=urun_adi,
            ebat=ebat,
            mevsim=mevsim,
            dot=dot,
            fiyat=fiyat,
            para_birimi="TL",
            stok=stok_clean,
            site_url=f"{HOME_URL}/anasayfa.php",
        )

    @staticmethod
    def _fiyat_parse(s: str) -> float:
        try:
            t = s.replace("₺", "").replace("TL", "").replace(".", "").replace(",", ".").strip()
            m = re.search(r'[\d]+\.?\d*', t)
            return float(m.group()) if m else 0.0
        except Exception:
            return 0.0
