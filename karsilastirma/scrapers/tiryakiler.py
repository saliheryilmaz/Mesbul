import re
import time
import logging
from playwright.sync_api import Page
from .base import BaseScraper, LastikSonuc

logger = logging.getLogger(__name__)

LOGIN_URL = "https://bayi.tiryakilerotomotiv.com/tr/giris"
HOME_URL  = "https://bayi.tiryakilerotomotiv.com"


class TiryakilerScraper(BaseScraper):
    TOPTANCI_ADI = "Tiryakiler"

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
                logger.error(f"[{self.TOPTANCI_ADI}] Login inputlari bulunamadi")
                return False

            user_el.fill(self.kullanici)
            pass_el.fill(self.sifre)

            btn = page.query_selector("button.btn-login, button[type=\"submit\"]")
            if btn:
                btn.click()
            else:
                page.keyboard.press("Enter")

            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass
            time.sleep(4)

            body = page.inner_text("body")[:600].lower()

            if any(w in body for w in ["cikis", "sepetim", "erhan", "meslas",
                                        "urunler", "hesabim", "siparisler", "bakiye"]):
                logger.info(f"[{self.TOPTANCI_ADI}] Login basarili")
                return True

            logger.warning(f"[{self.TOPTANCI_ADI}] Login basarisiz - URL: {page.url}")
            return False
        except Exception as e:
            logger.error(f"[{self.TOPTANCI_ADI}] Login hatasi: {e}")
            return False

    def ara(self, page: Page, ebat: str, marka: str = "") -> list:
        try:
            page.goto(f"{HOME_URL}/tr/urunler", timeout=30_000)
            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass
            time.sleep(4)

            search_el = page.query_selector(
                "#inputsearchh-0, input[id*=\"search\"], input[placeholder*=\"Arama\"]"
            )
            if search_el:
                search_el.fill(ebat)
                search_el.press("Enter")
                logger.info(f"[{self.TOPTANCI_ADI}] Arama: {ebat}")
                try:
                    page.wait_for_load_state("networkidle", timeout=10_000)
                except Exception:
                    pass
                time.sleep(5)
            else:
                logger.warning(f"[{self.TOPTANCI_ADI}] Arama inputu bulunamadi")

            # Tum urunleri yuklemek icin agresif scroll
            prev_len = 0
            for _ in range(10):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.5)
                cur_len = len(page.inner_text("body"))
                if cur_len == prev_len:
                    break
                prev_len = cur_len

            body_text = page.inner_text("body")
            logger.info(f"[{self.TOPTANCI_ADI}] Body uzunlugu: {len(body_text)}")

            return self._parse(body_text, ebat, marka)

        except Exception as e:
            logger.error(f"[{self.TOPTANCI_ADI}] Arama hatasi: {e}")
            return []

    def _parse(self, body: str, ebat_f: str, marka_f: str) -> list:
        sonuclar = []
        lines = [l.strip() for l in body.split("\n") if l.strip()]

        i = 0
        while i < len(lines):
            line = lines[i]

            ebat_match = re.search(r"(\d{3}/\d{2}\s*R?\s*\d{2,3}[A-Z]?)", line)
            if not ebat_match:
                i += 1
                continue

            if re.match(r"^[A-Z]{1,4}\d{2}-", line):
                i += 1
                continue

            ebat_raw  = re.sub(r"\s", "", ebat_match.group(1))
            ebat_norm = re.sub(r"(\d{2,3})C$", r"\1", ebat_raw)
            urun_adi  = line

            if ebat_f:
                from .base import _ebat_eslesir
                if not _ebat_eslesir(ebat_f, ebat_norm):
                    i += 1
                    continue

            if marka_f and marka_f.lower() not in urun_adi.lower():
                i += 1
                continue

            dot   = ""
            fiyat = 0.0
            stok  = "Var"

            for j in range(i + 1, min(i + 15, len(lines))):
                l = lines[j]

                if re.match(r"^20\d{2}$", l) and not dot:
                    dot = l
                    continue

                fiyat_match = re.search(r"([\d]{1,3}(?:\.[\d]{3})*,[\d]{2})\s*TL", l)
                if fiyat_match:
                    f = self._fiyat_parse(fiyat_match.group(1))
                    if f > 100:
                        fiyat = f
                        stok_match = re.search(r"(\+?\d+)\s*$", l)
                        if stok_match:
                            stok = stok_match.group(1)
                        break

                if re.search(r"\d{3}/\d{2}", l) and l != line:
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
                "Kelly", "Warrior", "Addo", "Riken", "Gripmax"
            ]
            marka_text = next(
                (m for m in markalar if m.lower() in urun_adi.lower()), "Diger"
            )

            mevsim = "Yaz"
            low = urun_adi.lower()
            if any(w in low for w in ["kis", "winter", "blizzak", "snovanis",
                                       "polaris", "wintech", "nordman"]):
                mevsim = "Kis"
            elif any(w in low for w in ["4 season", "all season", "allseason",
                                         "quartaris", "multiways", "crossclimate"]):
                mevsim = "4 Mevsim"

            sonuclar.append(self.sonuc_olustur(
                marka=marka_text,
                model=urun_adi,
                ebat=ebat_norm,
                mevsim=mevsim,
                dot=dot,
                fiyat=fiyat,
                para_birimi="TL",
                stok=stok,
                site_url=HOME_URL,
            ))

            i += 1

        logger.info(f"[{self.TOPTANCI_ADI}] {len(sonuclar)} urun parse edildi")
        return sonuclar

    @staticmethod
    def _fiyat_parse(s: str) -> float:
        try:
            t = s.replace("TL", "").replace(".", "").replace(",", ".").strip()
            m = re.search(r"[\d]+\.?\d*", t)
            return float(m.group()) if m else 0.0
        except Exception:
            return 0.0
