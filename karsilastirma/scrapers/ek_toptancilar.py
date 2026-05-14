import logging
import os
import re
import time
from urllib.parse import quote

from playwright.sync_api import Page

from .base import BaseScraper, LastikSonuc, _ebat_eslesir

logger = logging.getLogger(__name__)
FAST_MAX_PAGES = int(os.getenv("SCRAPER_FAST_MAX_PAGES", "12"))
FAST_SCROLL_ROUNDS = int(os.getenv("SCRAPER_FAST_SCROLL_ROUNDS", "6"))


MARKALAR = [
    "Continental", "Michelin", "Pirelli", "Bridgestone", "Goodyear",
    "Lassa", "Petlas", "Hankook", "Dunlop", "Yokohama", "Nokian",
    "Starmaxx", "Nexen", "Kumho", "Falken", "Firestone", "Maxxis",
    "Linglong", "Triangle", "Kormoran", "BFGoodrich", "Debica", "Tigar",
    "Nankang", "Toyo", "Accelera", "Barum", "Sava", "Matador",
    "Semperit", "Uniroyal", "Giti", "Leao", "Minerva", "Milestone",
    "Kelly", "Warrior", "Addo", "Riken", "Gripmax", "Tatko", "Delinte",
    "Sentury", "Momo", "Marshal", "Kleber", "Fulda", "Waterfall",
]


def _ebat_rakam(ebat: str) -> str:
    return re.sub(r"[^0-9]", "", ebat or "")


class GenericWebScraper(BaseScraper):
    TOPTANCI_ADI = "Generic"
    LOGIN_URL = ""
    HOME_URL = ""
    SEARCH_URLS: list[str] = []
    USER_SELECTOR = (
        "#userName, #username, #Usercode, #mail, input[name='username'], "
        "input[name='Usercode'], input[name='email'], input[type='email'], "
        "input[name='USER'], input[name='kullaniciadi'], input[name='adi'], "
        "input[placeholder*='Kullanici'], input[placeholder*='Kullanıcı']"
    )
    PASS_SELECTOR = (
        "#password, #password-input, #Pass, #SIFRE, #Sifre, input[name='password'], "
        "input[name='Pass'], input[name='SIFRE'], input[name='Sifre'], input[type='password']"
    )
    SUBMIT_SELECTOR = (
        "button[type='submit'], input[type='submit'], button:has-text('Giris'), "
        "button:has-text('Giriş'), input[value*='Giris'], input[value*='Giriş'], "
        ".btn-login, #login-btn, #btngirisyap, .LoginForm, #login"
    )
    SEARCH_SELECTOR = (
        "#inputsearchh-0, #searchProductList, input[name='Kelime'], input[name='URUN1'], "
        "input[name='ebat'], input[type='search'], input[placeholder*='Arama'], "
        "input[placeholder*='Ara'], input[placeholder*='Ürün']"
    )
    PRODUCT_ROW_SELECTOR = (
        "a.bs-login-prd, .gridjs-tbody .gridjs-tr, table tbody tr, "
        "[class*='product-card'], [class*='ProductCard'], article"
    )

    def login(self, page: Page) -> bool:
        try:
            page.goto(self.LOGIN_URL, timeout=30_000)
            self._wait(page)

            user_el = page.query_selector(self.USER_SELECTOR)
            pass_el = page.query_selector(self.PASS_SELECTOR)
            if not (user_el and pass_el):
                logger.error(f"[{self.TOPTANCI_ADI}] Login inputlari bulunamadi")
                return False

            user_el.fill(self.kullanici)
            pass_el.fill(self.sifre)
            self._fill_extra_login_fields(page)

            btn = page.query_selector(self.SUBMIT_SELECTOR)
            if btn:
                btn.click()
            else:
                page.keyboard.press("Enter")

            self._wait(page, extra=3)
            if self._login_success(page):
                logger.info(f"[{self.TOPTANCI_ADI}] Login basarili")
                return True

            logger.warning(f"[{self.TOPTANCI_ADI}] Login basarisiz - URL: {page.url}")
            return False
        except Exception as e:
            logger.error(f"[{self.TOPTANCI_ADI}] Login hatasi: {e}")
            return False

    def _fill_extra_login_fields(self, page: Page) -> None:
        return None

    def _login_success(self, page: Page) -> bool:
        url = page.url.lower()
        body = page.inner_text("body")[:1200].lower()
        if "login" not in url and "giris" not in url and "signin" not in url:
            return True
        return any(
            word in body
            for word in [
                "cikis", "çıkış", "sepet", "urunler", "ürünler", "anasayfa",
                "bakiye", "siparis", "sipariş", "hesabim", "hesabım",
            ]
        )

    def ara(self, page: Page, ebat: str, marka: str = "") -> list[LastikSonuc]:
        try:
            if self.SEARCH_URLS:
                urls = [u.format(ebat=quote(ebat), ebat_rakam=_ebat_rakam(ebat)) for u in self.SEARCH_URLS]
            else:
                urls = [self.HOME_URL or self.LOGIN_URL]

            for url in urls:
                try:
                    page.goto(url, timeout=30_000)
                    self._wait(page, extra=2)
                    if _ebat_eslesir(ebat, page.inner_text("body")):
                        break
                    if self._try_search_box(page, ebat):
                        break
                except Exception:
                    continue

            self._load_all(page)
            rows = self._collect_row_texts(page)
            logger.info(f"[{self.TOPTANCI_ADI}] {len(rows)} satir toplandi")
            return self._parse_rows(rows, ebat, marka)
        except Exception as e:
            logger.error(f"[{self.TOPTANCI_ADI}] Arama hatasi: {e}")
            return []

    def _try_search_box(self, page: Page, ebat: str) -> bool:
        search = page.query_selector(self.SEARCH_SELECTOR)
        if not search:
            return False
        try:
            value = _ebat_rakam(ebat) if (search.get_attribute("name") or "").lower() == "ebat" else ebat
            search.fill(value)
            search.press("Enter")
            self._wait(page, extra=3)
            logger.info(f"[{self.TOPTANCI_ADI}] Arama kutusu: {value}")
            return True
        except Exception:
            return False

    def _load_all(self, page: Page) -> None:
        for _ in range(FAST_SCROLL_ROUNDS):
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            except Exception:
                pass
            time.sleep(0.7)

    def _walk_pagination(self, page: Page) -> None:
        """Default: sayfalama/yükleme bitene kadar scroll + sayfa sonu kontrolü.

        Platform özel override'ı varsa kullanılır.
        """
        prev_len = -1
        stable_rounds = 0
        for rnd in range(60):
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            except Exception:
                pass
            time.sleep(0.6)

            try:
                cur_len = len(page.inner_text("body"))
            except Exception:
                cur_len = -1

            if cur_len != -1:
                if cur_len == prev_len:
                    stable_rounds += 1
                else:
                    stable_rounds = 0
                prev_len = cur_len

                if stable_rounds >= 3 and rnd > 8:
                    break

        # Bazı UI'larda sayfa sonunda 
        return

    def _collect_row_texts(self, page: Page) -> list[str]:
        rows: list[str] = []
        seen_rows: set[str] = set()
        seen_pages: set[str] = set()

        for page_no in range(1, FAST_MAX_PAGES + 1):
            self._scroll_current_page(page)
            row_texts = self._current_row_texts(page)
            if not row_texts:
                break

            signature = "||".join(row_texts[:2] + row_texts[-2:])
            if signature and signature in seen_pages:
                break
            if signature:
                seen_pages.add(signature)

            for text in row_texts:
                key = " ".join(text.split()).lower()
                if key in seen_rows:
                    continue
                seen_rows.add(key)
                rows.append(text)

            if not self._go_next_page(page):
                break

            logger.info(f"[{self.TOPTANCI_ADI}] Sonraki sayfa okunuyor: {page_no + 1}")
            self._wait(page, extra=1.2)

        if rows:
            return rows

        body = page.inner_text("body")
        return [line.strip() for line in body.splitlines() if line.strip()]

    def _scroll_current_page(self, page: Page) -> None:
        prev_len = -1
        stable = 0
        for _ in range(FAST_SCROLL_ROUNDS):
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                cur_len = len(page.inner_text("body"))
            except Exception:
                break
            if cur_len == prev_len:
                stable += 1
            else:
                stable = 0
            prev_len = cur_len
            if stable >= 2:
                break
            time.sleep(0.5)

    def _current_row_texts(self, page: Page) -> list[str]:
        texts: list[str] = []
        for row in page.query_selector_all(self.PRODUCT_ROW_SELECTOR):
            try:
                text = row.inner_text().strip()
            except Exception:
                continue
            if len(text) >= 12:
                texts.append(text)
        return texts

    def _go_next_page(self, page: Page) -> bool:
        selectors = [
            ".dataTables_paginate a.next:not(.disabled)",
            ".paginate_button.next:not(.disabled)",
            ".pagination .next:not(.disabled)",
            "a[rel='next']",
            "button[aria-label*='Sonraki']:not([disabled])",
            "button[aria-label*='Next']:not([disabled])",
            "button:has-text('Sonraki'):not([disabled])",
            "button:has-text('Next'):not([disabled])",
            "a:has-text('Sonraki')",
            "a:has-text('Next')",
            "button:has-text('Daha Fazla')",
            "button:has-text('Daha fazla')",
            "button:has-text('Yükle')",
            "button:has-text('Load more')",
        ]
        for selector in selectors:
            try:
                loc = page.locator(selector).last
                if loc.count() == 0 or not loc.is_visible(timeout=800):
                    continue
                loc.scroll_into_view_if_needed(timeout=2000)
                loc.click(timeout=3000)
                return True
            except Exception:
                continue
        return False

    def _parse_rows(self, rows: list[str], ebat: str, marka: str = "") -> list[LastikSonuc]:
        sonuclar: list[LastikSonuc] = []
        seen = set()
        for row in rows:
            sonuc = self._parse_text(row, ebat, marka)
            if not sonuc:
                continue
            key = (
                sonuc.toptanci.lower(),
                sonuc.marka.lower(),
                sonuc.model.lower(),
                sonuc.ebat.lower(),
                round(sonuc.fiyat, 2),
                sonuc.dot.lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            sonuclar.append(sonuc)

        if not sonuclar:
            sonuclar = self._parse_line_blocks(rows, ebat, marka)
        return sonuclar

    def _parse_line_blocks(self, lines: list[str], ebat_f: str, marka_f: str = "") -> list[LastikSonuc]:
        sonuclar: list[LastikSonuc] = []
        seen = set()
        cleaned = [" ".join((line or "").split()) for line in lines if (line or "").strip()]

        for i, line in enumerate(cleaned):
            if not _ebat_eslesir(ebat_f, line):
                continue

            block = " ".join(cleaned[i:min(i + 10, len(cleaned))])
            if marka_f and marka_f.lower() not in block.lower():
                continue

            fiyat = self._fiyat_bul(block)
            if fiyat < 100:
                continue

            ebat = self._ebat_bul(block) or ebat_f
            marka = next((m for m in MARKALAR if m.lower() in block.lower()), "Diger")
            dot = self._dot_bul(block)
            stok = self._stok_bul(block)
            mevsim = self._mevsim_bul(block)

            key = (marka.lower(), line.lower(), ebat.lower(), round(fiyat, 2), dot.lower())
            if key in seen:
                continue
            seen.add(key)

            sonuclar.append(self.sonuc_olustur(
                marka=marka,
                model=line[:220],
                ebat=ebat,
                mevsim=mevsim,
                dot=dot,
                fiyat=fiyat,
                para_birimi="TL",
                stok=stok,
                site_url=self.HOME_URL or self.LOGIN_URL,
            ))

        return sonuclar

    def _parse_text(self, text: str, ebat_f: str, marka_f: str = "") -> LastikSonuc | None:
        full = " ".join((text or "").split())
        if len(full) < 12 or not _ebat_eslesir(ebat_f, full):
            return None
        if marka_f and marka_f.lower() not in full.lower():
            return None

        fiyat = self._fiyat_bul(full)
        if fiyat < 100:
            return None

        ebat = self._ebat_bul(full) or ebat_f
        marka = next((m for m in MARKALAR if m.lower() in full.lower()), "Diger")
        dot = self._dot_bul(full)
        stok = self._stok_bul(full)
        mevsim = self._mevsim_bul(full)

        model = full[:220]
        return self.sonuc_olustur(
            marka=marka,
            model=model,
            ebat=ebat,
            mevsim=mevsim,
            dot=dot,
            fiyat=fiyat,
            para_birimi="TL",
            stok=stok,
            site_url=self.HOME_URL or self.LOGIN_URL,
        )

    @staticmethod
    def _ebat_bul(text: str) -> str:
        m = re.search(r"(\d{3}/\d{2}\s*(?:Z?R|/)?\s*\d{2,3}\s*C?)", text, re.I)
        if not m:
            return ""
        ebat = re.sub(r"\s+", "", m.group(1))
        ebat = re.sub(r"(?i)ZR", "R", ebat)
        ebat = re.sub(r"(\d{3}/\d{2})/(\d{2,3})", r"\1R\2", ebat)
        return ebat

    @staticmethod
    def _fiyat_bul(text: str) -> float:
        amount = r"(?:\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{2})?|\d{4,6}(?:[.,]\d{2})?|\d{1,3}[.,]\d{2})"
        matches = []
        for pattern in [
            rf"(?:TL|TRY|\u20ba)\s*({amount})",
            rf"({amount})\s*(?:TL|TRY|\u20ba)",
        ]:
            matches.extend(re.findall(pattern, text, re.I))
        matches.extend(re.findall(r"\b\d{1,3}(?:[.,]\d{3})*[.,]\d{2}\b", text or ""))
        values = [GenericWebScraper._fiyat_parse(m) for m in matches]
        values = [v for v in values if 100 <= v <= 250_000]
        return min(values) if values else 0.0

    @staticmethod
    def _fiyat_parse(s: str) -> float:
        try:
            s = (
                (s or "")
                .replace("TL", "")
                .replace("TRY", "")
                .replace("\u20ba", "")
                .strip()
            )
            s = re.sub(r"\s+", "", s)
            if "," in s and "." in s:
                if s.rfind(",") > s.rfind("."):
                    s = s.replace(".", "").replace(",", ".")
                else:
                    s = s.replace(",", "")
            elif "," in s:
                parts = s.split(",")
                if len(parts[-1]) == 3 and all(part.isdigit() for part in parts):
                    s = "".join(parts)
                else:
                    s = s.replace(".", "").replace(",", ".")
            elif "." in s:
                parts = s.split(".")
                if len(parts[-1]) == 3 and all(part.isdigit() for part in parts):
                    s = "".join(parts)
            m = re.search(r"\d+(?:\.\d+)?", s)
            return float(m.group()) if m else 0.0
        except Exception:
            return 0.0

    @staticmethod
    def _dot_bul(text: str) -> str:
        years = re.findall(r"\b20\d{2}\b", text)
        return "/".join(dict.fromkeys(years[:3]))

    @staticmethod
    def _stok_bul(text: str) -> str:
        stok = re.search(r"(?:stok|adet|miktar)\D{0,12}(\+?\d+)", text, re.I)
        if stok:
            return stok.group(1)
        plus = re.search(r"\b(\+?\d{1,3})\s*(?:adet|stok)?\b", text, re.I)
        return plus.group(1) if plus else "Var"

    @staticmethod
    def _mevsim_bul(text: str) -> str:
        low = text.lower()
        if any(w in low for w in ["kis", "kış", "winter", "polar", "snow", "arcterrain"]):
            return "Kis"
        if any(w in low for w in ["4 mevsim", "dortmevsim", "dörtmevsim", "all season", "allseason"]):
            return "4 Mevsim"
        return "Yaz"

    @staticmethod
    def _wait(page: Page, extra: float = 1.0) -> None:
        try:
            page.wait_for_load_state("networkidle", timeout=12_000)
        except Exception:
            try:
                page.wait_for_load_state("domcontentloaded", timeout=8_000)
            except Exception:
                pass
        time.sleep(extra)


class B2BStoreScraper(GenericWebScraper):
    SEARCH_SELECTOR = "#inputsearchh-0, input.bs-master-input-inner, input[placeholder*='Arama']"
    PRODUCT_ROW_SELECTOR = "a.bs-login-prd, .bs-login-prd"

    def ara(self, page: Page, ebat: str, marka: str = "") -> list[LastikSonuc]:
        self.SEARCH_URLS = [f"{self.HOME_URL}/tr/urunler?search={{ebat}}", f"{self.HOME_URL}/tr/urunler"]
        return super().ara(page, ebat, marka)

    def _load_all(self, page: Page) -> None:
        prev_len = 0
        for rnd in range(max(FAST_SCROLL_ROUNDS, 8)):
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            except Exception:
                pass
            time.sleep(0.45)
            try:
                cur = len(page.inner_text("body"))
            except Exception:
                cur = 0
            if cur == prev_len and rnd > 8:
                break
            prev_len = cur


class AkilliB2BScraper(GenericWebScraper):
    USER_SELECTOR = "input[name='adi'], #Kullanici_Adi, input[type='text']"
    PASS_SELECTOR = "input[name='Sifre'], #Sifre, input[type='password']"
    SUBMIT_SELECTOR = "button[type='submit'], input[type='submit'], button:has-text('Giriş')"

    def ara(self, page: Page, ebat: str, marka: str = "") -> list[LastikSonuc]:
        ebat_num = _ebat_rakam(ebat)
        self.SEARCH_URLS = [
            f"{self.HOME_URL}/Arama/Arama?arama1={ebat_num}&q={{ebat}}",
            f"{self.HOME_URL}/Urunler/Filtrele?arama1={ebat_num}&q={{ebat}}",
            f"{self.HOME_URL}/Arama?arama1={ebat_num}&q={{ebat}}",
        ]
        return super().ara(page, ebat, marka)


class ClassicAspScraper(GenericWebScraper):
    USER_SELECTOR = "input[name='USER']"
    PASS_SELECTOR = "input[name='SIFRE']"
    SUBMIT_SELECTOR = ".LoginForm, button:has-text('Giriş'), input[type='submit']"
    SEARCH_SELECTOR = "input[name='URUN1'], input[name='Kelime'], input[type='search'], input[placeholder*='Ara']"

    def ara(self, page: Page, ebat: str, marka: str = "") -> list[LastikSonuc]:
        self.SEARCH_URLS = [
            f"{self.HOME_URL}/B2B_Stoklar.asp",
            f"{self.HOME_URL}/anasayfa.asp",
            f"{self.HOME_URL}/index.asp#orta",
        ]
        return super().ara(page, ebat, marka)


class YukeScraper(GenericWebScraper):
    TOPTANCI_ADI = "Yuke"
    LOGIN_URL = "https://portal.yuke.com.tr/auth/login"
    HOME_URL = "https://portal.yuke.com.tr"
    USER_SELECTOR = "#username, input[name='username']"
    PASS_SELECTOR = "#password, input[name='password']"
    SEARCH_SELECTOR = "#search, input[name='search']"
    SEARCH_URLS = [
        "https://portal.yuke.com.tr/products/tyre?search={ebat}",
        "https://portal.yuke.com.tr/products/tyre?search={ebat_rakam}",
    ]


class DrmScraper(B2BStoreScraper):
    TOPTANCI_ADI = "DRM"
    LOGIN_URL = "https://drm.b4bstore.com/tr/giris"
    HOME_URL = "https://drm.b4bstore.com"


class UstundagScraper(AkilliB2BScraper):
    TOPTANCI_ADI = "Ustundag Lastik"
    LOGIN_URL = "https://bayi.ustundaglastik.com/Giris"
    HOME_URL = "https://bayi.ustundaglastik.com"

    def ara(self, page: Page, ebat: str, marka: str = "") -> list[LastikSonuc]:
        self.SEARCH_URLS = [
            f"{self.HOME_URL}/Arama/Arama?q={{ebat_rakam}}",
            f"{self.HOME_URL}/Arama/Arama?q={{ebat}}",
        ]
        return GenericWebScraper.ara(self, page, ebat, marka)


class MutaflarScraper(GenericWebScraper):
    TOPTANCI_ADI = "Mutaflar Otomotiv"
    LOGIN_URL = "https://bayi.mutaflarotomotiv.com/login#!/signin"
    HOME_URL = "https://bayi.mutaflarotomotiv.com"
    USER_SELECTOR = "#mail, input[name='email'], input[type='email']"
    PASS_SELECTOR = "#password, input[name='password']"
    SUBMIT_SELECTOR = "#login-btn, button[type='submit']"
    SEARCH_URLS = [
        "https://bayi.mutaflarotomotiv.com/search/detail?search={ebat}",
        "https://bayi.mutaflarotomotiv.com/search/detail?search={ebat_rakam}",
    ]


class GulerScraper(GenericWebScraper):
    TOPTANCI_ADI = "Guler Oto Lastik"
    LOGIN_URL = "https://gulerotolastik.com/#!/login"
    HOME_URL = "https://gulerotolastik.com"
    USER_SELECTOR = "input[placeholder='Kullanıcı Adı'], input[type='text']"
    PASS_SELECTOR = "input[placeholder='Şifre'], input[type='password']"
    SUBMIT_SELECTOR = "#login, button:has-text('Giriş Yap')"
    SEARCH_URLS = [
        "https://gulerotolastik.com/#!/products?searchText={ebat_rakam}",
        "https://gulerotolastik.com/#!/login?searchText={ebat_rakam}&redirect=%2Fproducts",
    ]

    def __init__(self, kullanici: str, sifre: str, pin: str = ""):
        super().__init__(kullanici, sifre)
        self.pin = pin

    def _fill_extra_login_fields(self, page: Page) -> None:
        if not self.pin:
            return
        pin_el = page.query_selector("input[placeholder='Pin']")
        if pin_el:
            pin_el.fill(self.pin)


class AykoScraper(ClassicAspScraper):
    TOPTANCI_ADI = "Ayko"
    LOGIN_URL = "https://b2b.ayko.com.tr/index.asp#orta"
    HOME_URL = "https://b2b.ayko.com.tr"

    def _fiyat_bul(self, text: str) -> float:
        fiyat = GenericWebScraper._fiyat_bul(text)
        if fiyat >= 100:
            return fiyat

        # Ayko table rows expose list/net prices as plain thousands values,
        # e.g. "... 2026 20+ 3.698 2.774 Ekle"; the last amount is net.
        matches = re.findall(r"\b\d{1,3}(?:[.,]\d{3})\b", text or "")
        values = [GenericWebScraper._fiyat_parse(m) for m in matches]
        values = [v for v in values if 100 <= v <= 250_000]
        return values[-1] if values else 0.0


class HaskarScraper(GenericWebScraper):
    TOPTANCI_ADI = "Haskar"
    LOGIN_URL = "https://b2b.haskar.com.tr/Account/Login/?ReturnUrl=%2Fanasayfa"
    HOME_URL = "https://b2b.haskar.com.tr"
    USER_SELECTOR = "#Usercode, input[name='Usercode']"
    PASS_SELECTOR = "#Pass, input[name='Pass']"
    SUBMIT_SELECTOR = "#btngirisyap, button[type='submit']"
    SEARCH_URLS = [
        "https://b2b.haskar.com.tr/Urunler?search={ebat}",
        "https://b2b.haskar.com.tr/Stok?search={ebat}",
        "https://b2b.haskar.com.tr/anasayfa?search={ebat}",
    ]


class MedLastikScraper(GenericWebScraper):
    TOPTANCI_ADI = "MedLastik"
    LOGIN_URL = "https://b2b.medlastik.com/tr/giris"
    HOME_URL = "https://b2b.medlastik.com"
    SEARCH_URLS = [
        "https://b2b.medlastik.com/tr/urunler?search={ebat}",
        "https://b2b.medlastik.com/tr/urunler",
    ]
