import re
import time
import logging
from playwright.sync_api import Page, Locator
from .base import BaseScraper, LastikSonuc, _ebat_eslesir

logger = logging.getLogger(__name__)

LOGIN_URL = "https://bayiportal.lastikpark.com/#TatkoLogin"
HOME_URL = "https://bayiportal.lastikpark.com"


class LastikParkScraper(BaseScraper):
    TOPTANCI_ADI = "LastikPark (Tatko)"

    def __init__(self, kullanici: str, sifre: str, sirket: str = ""):
        super().__init__(kullanici, sifre)
        self.sirket = sirket

    def login(self, page: Page) -> bool:
        try:
            page.goto(LOGIN_URL, timeout=30_000)
            try:
                page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass
            time.sleep(3)

            company_el = page.query_selector("#company")
            if company_el and self.sirket:
                company_el.fill(self.sirket)
                time.sleep(1)
                try:
                    dropdown_item = page.query_selector(
                        '.autocomplete-item, .dropdown-item, li[role="option"], .suggestion'
                    )
                    if dropdown_item:
                        dropdown_item.click()
                        time.sleep(1)
                except Exception:
                    pass

            username_el = page.query_selector("#username")
            password_el = page.query_selector("#password")

            if not (username_el and password_el):
                logger.error(f"[{self.TOPTANCI_ADI}] Login inputlari bulunamadi")
                return False

            username_el.fill(self.kullanici)
            password_el.fill(self.sifre)

            submit = page.locator("form:has(#username):has(#password)").locator(
                'button[type="submit"], button:has-text("GİRİŞ"), button:has-text("Giriş")'
            ).first
            try:
                if submit.is_visible(timeout=4000):
                    submit.click()
                else:
                    page.keyboard.press("Enter")
            except Exception:
                page.keyboard.press("Enter")

            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass
            time.sleep(4)

            body = page.inner_text("body")[:600].lower()

            if any(
                w in body
                for w in [
                    "cikis",
                    "stok",
                    "urun",
                    "arama",
                    "sepet",
                    "hosgeldiniz",
                    "anasayfa",
                    "lastik",
                ]
            ):
                logger.info(f"[{self.TOPTANCI_ADI}] Login basarili")
                return True

            logger.warning(f"[{self.TOPTANCI_ADI}] Login basarisiz - URL: {page.url}")
            logger.warning(f"[{self.TOPTANCI_ADI}] Body: {body[:200]}")
            return False
        except Exception as e:
            logger.error(f"[{self.TOPTANCI_ADI}] Login hatasi: {e}")
            return False

    def _stok_sayfasi(self, page: Page) -> None:
        page.goto(f"{HOME_URL}/#/Stok", wait_until="domcontentloaded", timeout=30_000)
        try:
            page.wait_for_load_state("networkidle", timeout=12_000)
        except Exception:
            pass
        time.sleep(2.5)

    def _otomobil_kategori(self, page: Page) -> None:
        """Fiyat & stok ekranında segment seçilmezse arama sonuç dönmüyor."""
        try:
            oto = page.get_by_text("Otomobil", exact=True).first
            if oto.is_visible(timeout=4000):
                oto.click(timeout=5000)
                time.sleep(1.2)
                logger.info(f"[{self.TOPTANCI_ADI}] Otomobil kategorisi seçildi")
        except Exception as e:
            logger.warning(f"[{self.TOPTANCI_ADI}] Otomobil tıklanamadı: {e}")

    def _ebat1_editor(self, page: Page) -> Locator:
        return page.locator("div.col-md-3").filter(
            has_text=re.compile(r"Ebat-1", re.I)
        ).locator("input.dx-texteditor-input").first

    def _ara_buton_ebat1(self, page: Page) -> Locator:
        return page.locator("div.col-md-3").filter(
            has_text=re.compile(r"Ebat-1", re.I)
        ).locator(
            "xpath=following::div[contains(@class,'dx-button')]"
            "[.//text()='ARA' or .//span[text()='ARA']]"
        ).first

    def _dev_extreme_ebat_yaz(self, page: Page, loc: Locator, ebat_rakam: str) -> None:
        """DevExtreme editör .fill() ile güncellenmiyor; tuş vuruşu gerekir."""
        loc.scroll_into_view_if_needed(timeout=10_000)
        loc.click(timeout=10_000)
        loc.press("Control+a")
        loc.press("Backspace")
        page.keyboard.type(ebat_rakam, delay=35)
        time.sleep(0.4)

    def ara(self, page: Page, ebat: str, marka: str = "") -> list[LastikSonuc]:
        try:
            self._stok_sayfasi(page)
            self._otomobil_kategori(page)

            ebat_rakam = re.sub(r"[^0-9]", "", ebat)
            if len(ebat_rakam) < 4:
                logger.warning(f"[{self.TOPTANCI_ADI}] Ebat en az 4 rakam olmalı: {ebat!r}")
                return []

            editor = self._ebat1_editor(page)
            if editor.count() == 0 or not editor.is_visible(timeout=8000):
                logger.warning(f"[{self.TOPTANCI_ADI}] Ebat-1 alanı bulunamadı")
                return []

            logger.info(f"[{self.TOPTANCI_ADI}] Arama (rakam): {ebat_rakam}")
            self._dev_extreme_ebat_yaz(page, editor, ebat_rakam)

            ara_btn = self._ara_buton_ebat1(page)
            if ara_btn.count() == 0:
                logger.warning(f"[{self.TOPTANCI_ADI}] ARA düğmesi bulunamadı")
                return []
            ara_btn.click(timeout=15_000)

            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass
            time.sleep(4)

            for _ in range(6):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)

            sonuclar = self._dx_grid_parse(page, ebat, marka)
            if sonuclar:
                logger.info(f"[{self.TOPTANCI_ADI}] {len(sonuclar)} satır grid'den okundu")
                return sonuclar

            body_text = page.inner_text("body")
            logger.info(f"[{self.TOPTANCI_ADI}] Grid boş, body parse deneniyor ({len(body_text)} char)")
            return self._body_parse_lastikpark(body_text, ebat, marka)

        except Exception as e:
            logger.error(f"[{self.TOPTANCI_ADI}] Arama hatasi: {e}")
            return []

    def _dx_grid_parse(self, page: Page, ebat_f: str, marka_f: str) -> list[LastikSonuc]:
        rows = page.query_selector_all(
            ".dx-datagrid-rowsview tr.dx-data-row, "
            ".dx-datagrid-rowsview .dx-row.dx-data-row, "
            "table.dx-datagrid-table tbody tr"
        )
        sonuclar: list[LastikSonuc] = []
        for row in rows:
            try:
                full = row.inner_text().replace("\t", " ").strip()
            except Exception:
                continue
            s = self._parse_urun_satiri(full, ebat_f, marka_f)
            if s:
                sonuclar.append(s)
        return sonuclar

    def _parse_urun_satiri(self, full: str, ebat_f: str, marka_f: str) -> LastikSonuc | None:
        if not full or len(full) < 20:
            return None
        low = full.lower()
        if "gösterilecek veri bulunamad" in low or "gosterilecek veri bulunamad" in low:
            return None
        if re.search(r"\bkampanya\b", low) and re.search(r"\bstok\s+kodu\b", low):
            return None

        if not _ebat_eslesir(ebat_f, full):
            return None
        if marka_f and marka_f.lower() not in full.lower():
            return None

        fiyat_m = re.findall(r"\b(\d{1,3}(?:,\d{3})*\.\d{2})\b", full)
        if not fiyat_m:
            fiyat_m = re.findall(
                r"\b(\d{1,3}(?:\.\d{3})*,\d{2})\s*(?:TL|₺)?\b", full.replace("\xa0", " ")
            )
        if not fiyat_m:
            return None
        fiyat = self._fiyat_parse(fiyat_m[-1])
        if fiyat < 100:
            return None

        ebat_m = re.search(r"(\d{3}/\d{2}\s*R?\s*\d{2,3})", full)
        ebat_out = re.sub(r"\s", "", ebat_m.group(1)) if ebat_m else ebat_f

        markalar = [
            "Continental", "Michelin", "Pirelli", "Bridgestone", "Goodyear",
            "Lassa", "Petlas", "Hankook", "Dunlop", "Yokohama", "Nokian",
            "Starmaxx", "Nexen", "Kumho", "Falken", "Firestone", "Maxxis",
            "Linglong", "Triangle", "Kormoran", "BFGoodrich", "Debica", "Tigar",
            "Nankang", "Toyo", "Accelera", "Barum", "Sava", "Matador",
            "Semperit", "Uniroyal", "Giti", "Leao", "Minerva", "Milestone",
            "Tatko", "Riken", "Gripmax", "Delinte", "Sentury",
        ]
        marka_text = next((m for m in markalar if m.lower() in full.lower()), "Diger")

        mevsim = "Yaz"
        if any(w in low for w in ["kis", "winter", "blizzak", "snovanis"]):
            mevsim = "Kis"
        elif "4 mevsim" in low or "all season" in low:
            mevsim = "4 Mevsim"

        dot = ""
        dm = re.search(r"\b(20\d{2})\b", full)
        if dm:
            dot = dm.group(1)

        stok = "Var"
        sm = re.search(
            r"(?:\d{1,3}(?:,\d{3})*\.\d{2})\s*(\+?\d+)\b",
            full.replace("\xa0", " "),
        )
        if sm:
            stok = sm.group(1)

        model = " ".join(full.split())[:220]

        return self.sonuc_olustur(
            marka=marka_text,
            model=model,
            ebat=ebat_out,
            mevsim=mevsim,
            dot=dot,
            fiyat=fiyat,
            para_birimi="TL",
            stok=stok,
            site_url=HOME_URL,
        )

    def _body_parse_lastikpark(self, body: str, ebat_f: str, marka_f: str) -> list[LastikSonuc]:
        sonuclar = []
        for line in body.split("\n"):
            line = line.strip()
            if not line:
                continue
            s = self._parse_urun_satiri(line, ebat_f, marka_f)
            if s:
                sonuclar.append(s)
        logger.info(f"[{self.TOPTANCI_ADI}] {len(sonuclar)} urun body satirindan")
        return sonuclar

    @staticmethod
    def _fiyat_parse(s: str) -> float:
        s = (s or "").strip().replace("TL", "").replace("₺", "").strip()
        try:
            # LastikPark grid: 2,461.00 (virgül binlik, nokta ondalık)
            m_us = re.match(r"^(\d{1,3}(?:,\d{3})*)\.(\d{2})$", s.replace(" ", ""))
            if m_us:
                return float(m_us.group(1).replace(",", "") + "." + m_us.group(2))
            # Klasik TR: 2.461,00
            t = s.replace(".", "").replace(",", ".").strip()
            m = re.search(r"[\d]+\.?\d*", t)
            return float(m.group()) if m else 0.0
        except Exception:
            return 0.0
