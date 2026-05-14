"""
OtoSemih B2B scraper.

The site uses a GridJS table. Its search box can return a broad result set
for sizes such as 205/55R16, so this scraper visits every GridJS page and
then applies our exact tyre-size matcher locally.
"""
import logging
import re
import time

from playwright.sync_api import Page

from .base import BaseScraper, LastikSonuc, _ebat_eslesir

logger = logging.getLogger(__name__)

LOGIN_URL = "https://portal.otosemih.com/giris"
HOME_URL = "https://portal.otosemih.com"
LASTIK_URL = "https://portal.otosemih.com/urunler/lastik/"


class OtoSemihScraper(BaseScraper):
    TOPTANCI_ADI = "OtoSemih"

    def login(self, page: Page) -> bool:
        try:
            page.goto(LOGIN_URL, timeout=30_000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(2)

            user_el = page.query_selector('#username, input[name="username"]')
            pass_el = page.query_selector('#password-input, input[name="password"]')

            if not (user_el and pass_el):
                inputs = page.query_selector_all("input")
                user_el = next((el for el in inputs if el.get_attribute("type") in ("text", "email")), None)
                pass_el = next((el for el in inputs if el.get_attribute("type") == "password"), None)

            if not (user_el and pass_el):
                logger.error(f"[{self.TOPTANCI_ADI}] Login inputlari bulunamadi")
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

            body = page.inner_text("body")[:800].lower()
            url = page.url.lower()

            if "giris" not in url:
                logger.info(f"[{self.TOPTANCI_ADI}] Login basarili (URL)")
                return True
            if any(w in body for w in ["anasayfa", "lastik", "bakiyem", "siparis"]):
                logger.info(f"[{self.TOPTANCI_ADI}] Login basarili")
                return True

            logger.warning(f"[{self.TOPTANCI_ADI}] Login basarisiz - URL: {page.url}")
            return False
        except Exception as e:
            logger.error(f"[{self.TOPTANCI_ADI}] Login hatasi: {e}")
            return False

    def ara(self, page: Page, ebat: str, marka: str = "") -> list[LastikSonuc]:
        try:
            page.goto(LASTIK_URL, timeout=30_000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(5)

            search = page.query_selector(
                '#searchProductList, input[placeholder*="Urun Arama"], '
                'input[placeholder*="Ürün Arama"], input[placeholder*="Ara"]'
            )
            if search:
                search.fill(ebat)
                time.sleep(3)
                logger.info(f"[{self.TOPTANCI_ADI}] Arama yapildi: {ebat}")
            else:
                logger.warning(f"[{self.TOPTANCI_ADI}] Arama inputu bulunamadi")

            rows = self._collect_all_row_texts(page)
            logger.info(f"[{self.TOPTANCI_ADI}] {len(rows)} satir toplandi")

            sonuclar: list[LastikSonuc] = []
            seen = set()
            for row_texts in rows:
                sonuc = self._parse_texts(row_texts, ebat, marka)
                if not sonuc:
                    continue
                key = (
                    sonuc.marka.strip().lower(),
                    sonuc.model.strip().lower(),
                    sonuc.ebat.strip().lower(),
                    round(sonuc.fiyat, 2),
                    sonuc.dot.strip().lower(),
                )
                if key in seen:
                    continue
                seen.add(key)
                sonuclar.append(sonuc)

            return sonuclar
        except Exception as e:
            logger.error(f"[{self.TOPTANCI_ADI}] Arama hatasi: {e}")
            return []

    def _collect_all_row_texts(self, page: Page) -> list[list[str]]:
        rows: list[list[str]] = []
        seen_rows = set()
        seen_pages = set()

        for page_no in range(1, 100):
            for _ in range(2):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(0.5)

            row_handles = page.query_selector_all(".gridjs-tbody .gridjs-tr")
            if not row_handles:
                row_handles = page.query_selector_all("table tbody tr")

            page_signature = ""
            if row_handles:
                first = row_handles[0].inner_text().strip()
                last = row_handles[-1].inner_text().strip()
                page_signature = f"{first}||{last}"

            if page_signature and page_signature in seen_pages:
                break
            if page_signature:
                seen_pages.add(page_signature)

            for row in row_handles:
                cells = row.query_selector_all("td")
                if len(cells) < 6:
                    continue
                texts = [c.inner_text().strip() for c in cells]
                row_key = "||".join(texts)
                if row_key in seen_rows:
                    continue
                seen_rows.add(row_key)
                rows.append(texts)

            logger.info(f"[{self.TOPTANCI_ADI}] Sayfa {page_no}: {len(row_handles)} satir")

            next_btn = page.locator(
                'button[aria-label="Sonraki"]:not([disabled]), '
                'button:has-text("Sonraki"):not([disabled])'
            ).first
            try:
                if next_btn.count() == 0 or not next_btn.is_visible(timeout=1000):
                    break
                next_btn.scroll_into_view_if_needed(timeout=3000)
                next_btn.click(timeout=5000)
                time.sleep(3.5)
            except Exception:
                break


        return rows

    def _parse_row(self, row, ebat_f: str, marka_f: str) -> LastikSonuc | None:
        cells = row.query_selector_all("td")
        if len(cells) < 6:
            return None
        return self._parse_texts([c.inner_text().strip() for c in cells], ebat_f, marka_f)

    def _parse_texts(self, texts: list[str], ebat_f: str, marka_f: str) -> LastikSonuc | None:
        if len(texts) < 6:
            return None

        product_blob = texts[1] if len(texts) > 1 else ""
        product_lines = [line.strip() for line in product_blob.splitlines() if line.strip()]
        urun_adi = product_lines[0] if product_lines else product_blob.strip()
        if not urun_adi:
            return None

        full = " ".join(texts)
        full_lower = full.lower()

        # Ebat eşleşmesi: GridJS'te ebat bazen ilk satırda olmayabiliyor.
        # Bu yüzden tüm satır metninde kontrol ediyoruz.
        if ebat_f and not _ebat_eslesir(ebat_f, full):
            return None


        marka_text = texts[4].strip() if len(texts) > 4 else ""
        if marka_f and marka_f.lower() not in full_lower:
            return None

        ebat_match = re.search(
            r"(\d{3}/\d{2}\s*(?:Z?R)?\s*\d{2,3}\s*C?)",
            urun_adi,
            re.IGNORECASE,
        )
        ebat = ebat_f
        if ebat_match:
            ebat = re.sub(r"\s+", "", ebat_match.group(1))
            ebat = re.sub(r"(?i)ZR", "R", ebat)

        stok = texts[2].strip() if len(texts) > 2 and texts[2].strip() else "Var"
        dot = self._dot_temizle(texts[3] if len(texts) > 3 else "")

        fiyat = 0.0
        for fiyat_str in texts[5:8]:
            fiyat = self._fiyat_parse(fiyat_str)
            if fiyat >= 100:
                break
        if fiyat < 100:
            return None

        mevsim = "Yaz"
        if any(w in full_lower for w in ["kis", "winter", "polar", "arcterrain", "snow"]):
            mevsim = "Kis"
        elif any(w in full_lower for w in ["4 mevsim", "dortmevsim", "mevsim", "all season", "allseason"]):
            mevsim = "4 Mevsim"

        return self.sonuc_olustur(
            marka=marka_text or "-",
            model=urun_adi,
            ebat=ebat,
            mevsim=mevsim,
            dot=dot,
            fiyat=fiyat,
            para_birimi="TL",
            stok=stok,
            site_url=LASTIK_URL,
        )

    @staticmethod
    def _dot_temizle(dot_raw: str) -> str:
        years = re.findall(r"20\d{2}", dot_raw or "")
        if not years:
            return (dot_raw or "").strip()
        return "/".join(dict.fromkeys(years))

    @staticmethod
    def _fiyat_parse(s: str) -> float:
        try:
            t = (
                (s or "")
                .replace("\u20ba", "")
                .replace("TL", "")
                .replace(".", "")
                .replace(",", ".")
                .strip()
            )
            m = re.search(r"[\d]+\.?\d*", t)
            return float(m.group()) if m else 0.0
        except Exception:
            return 0.0
