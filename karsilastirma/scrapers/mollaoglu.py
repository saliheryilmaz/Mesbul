"""
Mollaoğlu Otomotiv B2B Scraper
Site: https://bayi.mollaoglu.com.tr
Altyapı: Nuxt.js / B2B Store (Tiryakiler ile aynı platform)

Öncelik: ürün kartları DOM (a.bs-login-prd) — body satır parse'ı tam ürünleri kaçırabiliyordu.
"""
import re
import time
import logging
from urllib.parse import quote

from playwright.sync_api import Page

from .base import BaseScraper, LastikSonuc, _ebat_eslesir

logger = logging.getLogger(__name__)

LOGIN_URL = "https://bayi.mollaoglu.com.tr/tr/giris"
HOME_URL = "https://bayi.mollaoglu.com.tr"


class MollaogluScraper(BaseScraper):
    TOPTANCI_ADI = "Mollaoğlu"

    def login(self, page: Page) -> bool:
        try:
            page.goto(LOGIN_URL, timeout=30_000)
            try:
                page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass
            time.sleep(2)

            user_el = page.query_selector("#userName")
            pass_el = page.query_selector("#password")

            if not (user_el and pass_el):
                logger.error(f"[{self.TOPTANCI_ADI}] Login inputları bulunamadı")
                return False

            user_el.fill(self.kullanici)
            pass_el.fill(self.sifre)

            btn = page.query_selector("button.btn-login, button[type='submit']")
            if btn:
                btn.click()
            else:
                page.keyboard.press("Enter")

            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass
            time.sleep(4)

            body = page.inner_text("body")[:600]

            if any(
                w in body
                for w in [
                    "Çıkış",
                    "Sepetim",
                    "ERHAN",
                    "MESLAS",
                    "Ürünler",
                    "Hesabım",
                ]
            ):
                logger.info(f"[{self.TOPTANCI_ADI}] ✅ Login başarılı")
                return True

            logger.warning(f"[{self.TOPTANCI_ADI}] ❌ Login başarısız — URL: {page.url}")
            return False
        except Exception as e:
            logger.error(f"[{self.TOPTANCI_ADI}] Login hatasi: {e}")
            return False

    def ara(self, page: Page, ebat: str, marka: str = "") -> list[LastikSonuc]:
        try:
            page.goto(f"{HOME_URL}/tr/urunler", timeout=30_000)
            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass
            time.sleep(2.5)

            # Açılış banner / WhatsApp modal aramayı engelleyebilir
            for _ in range(4):
                try:
                    page.keyboard.press("Escape")
                    ov = page.query_selector(
                        ".bs-modal-overlay, [name='modal-fade'] .bs-modal-overlay"
                    )
                    if ov and ov.is_visible():
                        ov.click(timeout=2000)
                except Exception:
                    pass
                time.sleep(0.4)

            loc = page.locator(
                "#inputsearchh-0, input.bs-master-input-inner, "
                'input[placeholder*="Arama" i]'
            ).first
            if loc.count() > 0:
                loc.fill(ebat, force=True, timeout=15_000)
                loc.press("Enter")
                logger.info(f"[{self.TOPTANCI_ADI}] Arama kutusu: {ebat}")
                try:
                    page.wait_for_load_state("networkidle", timeout=18_000)
                except Exception:
                    pass
                time.sleep(4)
            else:
                search_url = f"{HOME_URL}/tr/urunler?search={quote(ebat)}"
                logger.warning(f"[{self.TOPTANCI_ADI}] Arama alanı yok, URL ile: {search_url}")
                page.goto(search_url, timeout=30_000)
                try:
                    page.wait_for_load_state("networkidle", timeout=15_000)
                except Exception:
                    pass
                time.sleep(5)

            prev_len = 0
            for rnd in range(120):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.5)
                cur = len(page.inner_text("body"))
                if cur == prev_len and rnd > 10:
                    break
                prev_len = cur
            time.sleep(1.2)

            dom_sonuc = self._parse_dom(page, ebat, marka)
            if dom_sonuc:
                logger.info(f"[{self.TOPTANCI_ADI}] DOM: {len(dom_sonuc)} ürün")
                return dom_sonuc

            body_text = page.inner_text("body")
            logger.info(f"[{self.TOPTANCI_ADI}] DOM boş, body parse ({len(body_text)} char)")
            return self._parse(body_text, ebat, marka)

        except Exception as e:
            logger.error(f"[{self.TOPTANCI_ADI}] Arama hatası: {e}")
            return []

    def _parse_dom(self, page: Page, ebat_f: str, marka_f: str) -> list[LastikSonuc]:
        sonuclar: list[LastikSonuc] = []
        rows = page.query_selector_all("a.bs-login-prd")
        for row in rows:
            try:
                rid = row.get_attribute("id") or ""
                if not rid.startswith("ProductID_"):
                    continue
                blob = row.inner_text()
                if len(blob) < 12:
                    continue

                title_el = row.query_selector("aside.name-id .name-id-inner, .name-id-inner[title]")
                title = (title_el.get_attribute("title") or title_el.inner_text() or "").strip() if title_el else ""
                if not title:
                    link_el = row.query_selector(".name-id-link")
                    title = (link_el.inner_text() if link_el else "").strip()
                if not title:
                    title = blob.split("\n")[0][:200]

                img_el = row.query_selector("nav.img-id img[alt], img.bs-img[alt]")
                alt_txt = (img_el.get_attribute("alt") or "").strip() if img_el else ""
                full = f"{title} {alt_txt} {blob}".strip()
                if not re.search(r"\d{3}/\d{2}", full, re.I):
                    continue

                em = re.search(
                    r"(\d{3}/\d{2}\s*R\s*\d{2,3}[Cc]?|\d{3}/\d{2}/\d{2,3}[Cc]?)",
                    full,
                    re.I,
                )
                if not em:
                    continue
                ebat_raw = re.sub(r"\s+", "", em.group(1), flags=re.I)
                ebat_norm = re.sub(
                    r"(\d{3}/\d{2})/(\d{2,3})",
                    lambda m: f"{m.group(1)}R{m.group(2)}",
                    ebat_raw,
                    flags=re.I,
                )
                ebat_norm = re.sub(r"(\d{2,3})C$", r"\1", ebat_norm, flags=re.I)

                if ebat_f and not _ebat_eslesir(ebat_f, ebat_norm):
                    continue
                if marka_f and marka_f.lower() not in full.lower():
                    continue

                prices = re.findall(
                    r"([\d]{1,3}(?:\.\d{3})*,\d{2})\s*TL",
                    blob.replace("\xa0", " "),
                )
                fiyat = 0.0
                if prices:
                    vals = [self._fiyat_parse(p) for p in prices]
                    vals = [v for v in vals if v > 100]
                    if vals:
                        fiyat = min(vals)
                if fiyat < 100:
                    continue

                dot = ""
                dm = re.search(r"\b(20\d{2})\b", full)
                if dm:
                    dot = dm.group(1)

                stok = "Var"
                st_el = row.query_selector(
                    ".bs-depot-stock .bs-stocktext, span.bs-stocktext, .bs-stocktext-exists"
                )
                if st_el:
                    tx = st_el.inner_text().strip()
                    if tx.isdigit() or (tx.startswith("+") and tx[1:].isdigit()):
                        stok = tx

                brand_el = row.query_selector(
                    'article[data-title="Marka"], article.brand-id, .brand-id.Cell, .brand-id'
                )
                brand_txt = re.sub(r"\s+", " ", brand_el.inner_text().strip()) if brand_el else ""

                markalar = [
                    "Continental", "Michelin", "Pirelli", "Bridgestone", "Goodyear",
                    "Lassa", "Petlas", "Hankook", "Dunlop", "Yokohama", "Nokian",
                    "Starmaxx", "Nexen", "Kumho", "Falken", "Firestone", "Maxxis",
                    "Linglong", "Triangle", "Kormoran", "BFGoodrich", "Debica", "Tigar",
                    "Nankang", "Toyo", "Accelera", "Barum", "Sava", "Matador",
                    "Semperit", "Uniroyal", "Giti", "Leao", "Minerva", "Milestone",
                    "Kelly", "Warrior", "Addo", "Riken", "Gripmax",
                ]
                marka_text = brand_txt if brand_txt else next(
                    (m for m in markalar if m.lower() in full.lower()),
                    "Diğer",
                )

                mevsim = "Yaz"
                low = full.lower()
                if any(
                    w in low
                    for w in [
                        "kış",
                        "winter",
                        "blizzak",
                        "snovanis",
                        "polaris",
                        "wintech",
                        "nordman",
                    ]
                ):
                    mevsim = "Kış"
                elif any(
                    w in low
                    for w in [
                        "4 season",
                        "all season",
                        "allseason",
                        "4 mevsim",
                        "quartaris",
                        "multiways",
                        "crossclimate",
                    ]
                ):
                    mevsim = "4 Mevsim"

                model = title if title else full[:220]
                sonuclar.append(
                    self.sonuc_olustur(
                        marka=marka_text,
                        model=model,
                        ebat=ebat_norm,
                        mevsim=mevsim,
                        dot=dot,
                        fiyat=fiyat,
                        para_birimi="TL",
                        stok=stok,
                        site_url=HOME_URL,
                    )
                )
            except Exception:
                continue

        sonuclar.sort(key=lambda x: x.fiyat)
        logger.info(f"[{self.TOPTANCI_ADI}] {len(sonuclar)} ürün DOM ile")
        return sonuclar

    def _parse(self, body: str, ebat_f: str, marka_f: str) -> list[LastikSonuc]:
        """Yedek: gövde metni (Net / TL blokları)."""
        sonuclar = []
        lines = [l.strip() for l in body.split("\n") if l.strip()]

        i = 0
        while i < len(lines):
            line = lines[i]

            ebat_match = re.search(
                r"(\d{3}/\d{2}\s*R\s*\d{2,3}[A-Za-z]?|\d{3}/\d{2}/\d{2,3}[A-Za-z]?)",
                line,
                re.I,
            )
            if not ebat_match:
                i += 1
                continue

            if re.match(r"^[A-Z0-9]+-[A-Z0-9]+-", line):
                i += 1
                continue

            ebat_raw = re.sub(r"\s", "", ebat_match.group(1), flags=re.I)
            ebat_norm = re.sub(
                r"(\d{3}/\d{2})/(\d{2,3})",
                lambda m: f"{m.group(1)}R{m.group(2)}",
                ebat_raw,
                flags=re.I,
            )
            ebat_norm = re.sub(r"(\d{2,3})C$", r"\1", ebat_norm, flags=re.I)
            urun_adi = line

            if ebat_f and not _ebat_eslesir(ebat_f, ebat_norm):
                i += 1
                continue

            if marka_f and marka_f.lower() not in urun_adi.lower():
                i += 1
                continue

            dot = ""
            fiyat = 0.0
            stok = "Var"
            net_goruldu = False

            for j in range(i + 1, min(i + 40, len(lines))):
                l = lines[j]

                if re.match(r"^20\d{2}$", l) and not dot:
                    dot = l
                    continue

                if l.strip() == "Net":
                    net_goruldu = True
                    continue

                if net_goruldu:
                    fm = re.match(r"^([\d.,]+)\s*(?:TL|₺)?\s*$", l)
                    if fm:
                        cand = self._fiyat_parse(fm.group(1))
                        if cand > 100:
                            fiyat = cand
                            if j + 1 < len(lines):
                                stok_line = lines[j + 1]
                                if re.match(r"^\+?\d+", stok_line):
                                    stok = stok_line.split()[0]
                            break
                        continue

                fiyat_match = re.search(
                    r"([\d]{1,3}(?:\.[\d]{3})*,[\d]{2})\s*TL",
                    l,
                )
                if fiyat_match and not net_goruldu:
                    cand = self._fiyat_parse(fiyat_match.group(1))
                    if cand > 100:
                        fiyat = cand
                        stok_m = re.search(r"(\+?\d+)\s*$", l)
                        if stok_m:
                            stok = stok_m.group(1)
                        break

            if fiyat < 100:
                i += 1
                continue

            markalar = [
                "Continental", "Michelin", "Pirelli", "Bridgestone", "Goodyear",
                "Lassa", "Petlas", "Hankook", "Dunlop", "Yokohama", "Nokian",
                "Starmaxx", "Nexen", "Kumho", "Falken", "Firestone", "Maxxis",
                "Linglong", "Triangle", "Kormoran", "BFGoodrich", "Debica", "Tigar",
                "Nankang", "Toyo", "Accelera", "Barum", "Sava", "Matador",
                "Semperit", "Uniroyal", "Giti", "Leao", "Minerva", "Milestone",
                "Kelly", "Warrior", "Addo", "Riken", "Gripmax",
            ]
            marka_text = next(
                (m for m in markalar if m.lower() in urun_adi.lower()),
                "Diğer",
            )

            mevsim = "Yaz"
            low = urun_adi.lower()
            if any(
                w in low
                for w in [
                    "kış",
                    "winter",
                    "blizzak",
                    "snovanis",
                    "polaris",
                    "wintech",
                    "nordman",
                    "w651",
                    "w660",
                ]
            ):
                mevsim = "Kış"
            elif any(
                w in low
                for w in [
                    "4 season",
                    "all season",
                    "allseason",
                    "4 mevsim",
                    "quartaris",
                    "multiways",
                    "crossclimate",
                ]
            ):
                mevsim = "4 Mevsim"

            sonuclar.append(
                self.sonuc_olustur(
                    marka=marka_text,
                    model=urun_adi,
                    ebat=ebat_norm,
                    mevsim=mevsim,
                    dot=dot,
                    fiyat=fiyat,
                    para_birimi="TL",
                    stok=stok,
                    site_url=HOME_URL,
                )
            )

            i += 1

        logger.info(f"[{self.TOPTANCI_ADI}] {len(sonuclar)} ürün body ile")
        return sonuclar

    @staticmethod
    def _fiyat_parse(s: str) -> float:
        try:
            t = (
                s.replace("₺", "")
                .replace("TL", "")
                .replace(".", "")
                .replace(",", ".")
                .strip()
            )
            m = re.search(r"[\d]+\.?\d*", t)
            return float(m.group()) if m else 0.0
        except Exception:
            return 0.0
