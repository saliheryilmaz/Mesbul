"""
Keskin Lastik B2B Scraper
Site: https://keskinlastik.com
Altyapı: Akıllı B2B
"""
import re
import time
import logging
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
from .base import BaseScraper, LastikSonuc

logger = logging.getLogger(__name__)

LOGIN_URL = "https://keskinlastik.com/Giris"
SEARCH_URL = "https://keskinlastik.com/Urunler/Filtrele"

class KeskinLastikScraper(BaseScraper):
    TOPTANCI_ADI = "Keskin Lastik"

    def login(self, page: Page) -> bool:
        try:
            page.goto(LOGIN_URL, timeout=30_000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(2)

            # Keskin Lastik formu: name="adi" ve name="Sifre"
            filled = False
            try:
                user_el = page.query_selector('input[name="adi"]')
                pass_el = page.query_selector('input[name="Sifre"]')
                if user_el and pass_el:
                    user_el.fill(self.kullanici)
                    pass_el.fill(self.sifre)
                    filled = True
                    logger.info(f"[{self.TOPTANCI_ADI}] Form name='adi'/'Sifre' ile dolduruldu")
            except Exception:
                pass

            if not filled:
                # Fallback — placeholder ile dene
                inputs = page.query_selector_all("input")
                user_input = next(
                    (el for el in inputs if (el.get_attribute("placeholder") or "").lower() in ("müşteri kodunuz", "kullanici", "username", "email")),
                    None
                )
                pass_input = next((el for el in inputs if el.get_attribute("type") == "password"), None)

                if not user_input:
                    user_input = next((el for el in inputs if el.get_attribute("type") in ("text", "email")), None)

                if user_input and pass_input:
                    user_input.fill(self.kullanici)
                    pass_input.fill(self.sifre)
                    filled = True
                else:
                    logger.error(f"[{self.TOPTANCI_ADI}] Login inputları bulunamadı")
                    return False

            # Submit
            submit_btn = page.query_selector(
                'button[type="submit"], input[type="submit"], '
                '.btn-login, button:has-text("Giriş"), input[value*="Giriş"]'
            )
            if submit_btn:
                submit_btn.click()
            else:
                page.keyboard.press("Enter")

            page.wait_for_load_state("domcontentloaded", timeout=20_000)
            time.sleep(3)

            # Login kontrol
            current_url = page.url.lower()
            body = page.inner_text("body")[:800].lower()

            if "giris" not in current_url and "login" not in current_url:
                logger.info(f"[{self.TOPTANCI_ADI}] Login başarılı! URL: {page.url}")
                return True

            if any(w in body for w in ["çıkış", "sepet", "ürün", "hoş geldin", "stok", "filtrele"]):
                logger.info(f"[{self.TOPTANCI_ADI}] Login başarılı (body check)")
                return True

            logger.warning(f"[{self.TOPTANCI_ADI}] Login başarısız — URL: {page.url}")
            return False
        except Exception as e:
            logger.error(f"[{self.TOPTANCI_ADI}] Login hatası: {e}")
            return False

    def ara(self, page: Page, ebat: str, marka: str = "") -> list[LastikSonuc]:
        try:
            current_url = page.url
            logger.info(f"[{self.TOPTANCI_ADI}] Mevcut URL: {current_url}")

            # Ebatı URL parametrelerine çevir: 205/55R16 → arama1=2055516&q=205%2F55R16
            ebat_rakam = re.sub(r'[^0-9]', '', ebat)  # 2055516
            from urllib.parse import quote
            ebat_encoded = quote(ebat, safe='')         # 205%2F55R16

            arama_url = f"https://keskinlastik.com/Arama/Arama?arama1={ebat_rakam}&q={ebat_encoded}"
            logger.info(f"[{self.TOPTANCI_ADI}] Arama URL: {arama_url}")

            page.goto(arama_url, timeout=30_000)
            page.wait_for_load_state("domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass
            time.sleep(4)

            # Liste uzun; içerik inner_text ile geliyor — kaydırarak boyut sabitlenene kadar bekle
            prev_len = 0
            for rnd in range(120):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.5)
                cur = len(page.inner_text("body"))
                if cur == prev_len and rnd > 10:
                    break
                prev_len = cur
            time.sleep(1.2)

            body_text = page.inner_text("body")
            logger.info(f"[{self.TOPTANCI_ADI}] Body uzunluğu: {len(body_text)}")

            if len(body_text) < 2000:
                logger.warning(f"[{self.TOPTANCI_ADI}] Body çok kısa, sonuç yok")
                return []

            return self._keskin_body_parse(body_text, ebat, marka)

        except Exception as e:
            logger.error(f"[{self.TOPTANCI_ADI}] Arama hatası: {e}")
            return []

    def _keskin_body_parse(self, body: str, ebat_f: str, marka_f: str) -> list[LastikSonuc]:
        """
        Keskin body text formatı:
        205/55/16 91V PREMIUM CONTACT 7   ← ürün adı (ebat/yanak/cap format)
        0313035 25                          ← stok kodu + depo
        2025                               ← DOT
        -                                  ← etiket
        +20                                ← stok
        4.435,00 TL                        ← fiyat
        """
        sonuclar = []
        lines = [l.strip() for l in body.split('\n') if l.strip()]

        i = 0
        while i < len(lines):
            line = lines[i]

            # Ürün satırı: 205/55/16 veya 205/55R16
            ebat_match = re.match(r"^(\d{3}/\d{2}(?:/|R|r)\d{2,3})\s+(.+)$", line, re.I)
            if not ebat_match:
                i += 1
                continue

            ebat_raw = re.sub(r"(?i)R", "/", ebat_match.group(1))  # 205/55R16 → 205/55/16
            urun_adi = line.strip()

            # Ebat filtresi — rakamları karşılaştır
            if ebat_f:
                from .base import _ebat_eslesir
                if not _ebat_eslesir(ebat_f, ebat_raw):
                    i += 1
                    continue

            # Sonraki satırlarda fiyat ara (max 15 satır ilerle)
            dot  = ""
            stok = "Var"
            fiyat = 0.0

            # Ürün kartı ~21 satır; fiyat genelde +7. Önceki 15 satır penceresi eksik kalabiliyordu.
            for j in range(i + 1, min(i + 32, len(lines))):
                l = lines[j]

                # DOT: 4 haneli yıl
                if re.match(r"^20\d{2}$", l) and not dot:
                    dot = l

                # Stok: +20 veya saf rakam (1–4 hane; yılı DOT ile ayır)
                if re.match(r"^\+?\d{1,4}$", l) and l != dot and not re.match(r"^20\d{2}$", l):
                    stok = l

                # Fiyat: "4.435,00 TL" — bazen 0,00 TL önce gelir, geçerli fiyatı bul
                fm = re.match(r"^([\d.,]+)\s*TL\s*$", l) or re.search(
                    r"\b([\d]{1,3}(?:\.\d{3})*,\d{2})\s*TL\b", l
                )
                if fm:
                    cand = self._fiyat_parse(fm.group(1))
                    if cand > 100:
                        fiyat = cand
                        break

            if fiyat < 100:
                i += 1
                continue

            # Marka filtresi
            if marka_f and marka_f.lower() not in urun_adi.lower():
                i += 1
                continue

            # Ebatı normalize et: 205/55/16 → 205/55R16
            ebat_norm = re.sub(r'(\d{3}/\d{2})/(\d{2,3})', r'\1R\2', ebat_raw)

            # Marka tespiti — önce bilinen markalar, sonra ürün adından çıkar
            markalar = ["Continental", "Michelin", "Pirelli", "Bridgestone", "Goodyear",
                        "Lassa", "Petlas", "Hankook", "Dunlop", "Yokohama", "Nokian",
                        "Starmaxx", "Nexen", "Kumho", "Falken", "Firestone", "Maxxis",
                        "Linglong", "Triangle", "Kormoran", "BFGoodrich", "Debica", "Tigar",
                        "Nankang", "Toyo", "Accelera", "Sailun", "Windforce", "Wintech",
                        "Uniroyal", "Barum", "Sava", "Matador", "Semperit", "Riken", "Giti",
                        "Leao", "Protech", "Ultracontact", "Premiumcontact", "Gripmax",
                        "Milestone", "Minerva", "Westlake", "Goodride", "Nankang"]
            marka_text = next((m for m in markalar if m.lower() in urun_adi.lower()), "")

            # Bilinen marka bulunamazsa ürün adının son kelimesini al (model adı genellikle sonda)
            if not marka_text:
                marka_text = "Diğer"

            # Mevsim
            mevsim = "Yaz"
            low = urun_adi.lower()
            if "kış" in low or "winter" in low or "wintech" in low or "kis" in low:
                mevsim = "Kış"
            elif "4 mevsim" in low or "all season" in low or "allseason" in low:
                mevsim = "4 Mevsim"

            model_goster = urun_adi
            if dot or (stok and stok != "Var"):
                ek = []
                if dot:
                    ek.append(f"DOT {dot}")
                if stok and stok != "Var":
                    ek.append(f"Stok {stok}")
                if ek:
                    model_goster = f"{urun_adi} · " + " · ".join(ek)

            sonuclar.append(self.sonuc_olustur(
                marka=marka_text,
                model=model_goster,
                ebat=ebat_norm,
                mevsim=mevsim,
                dot=dot,
                fiyat=fiyat,
                para_birimi="TL",
                stok=stok,
                site_url=SEARCH_URL,
            ))

            i += 1

        logger.info(f"[{self.TOPTANCI_ADI}] {len(sonuclar)} ürün parse edildi")
        return sonuclar

    def _urun_parse(self, urun, ebat_filtre: str, marka_filtre: str) -> LastikSonuc | None:
        try:
            # Tablo satırı mı, kart mı?
            cells = urun.query_selector_all("td")
            if cells and len(cells) >= 8:
                # Akıllı B2B tablo: 0=İNCELE 1=KOD 2=MARKA 3=ÜRÜN 4=DOT 5=MEVSİM 6=ETİKET 7=ÖZELLİK 8=FİYAT 9=STOK
                texts = [c.inner_text().strip() for c in cells]
                marka_text = texts[2] if len(texts) > 2 else ""
                urun_adi   = texts[3] if len(texts) > 3 else ""
                dot        = texts[4] if len(texts) > 4 else ""
                mevsim_raw = texts[5] if len(texts) > 5 else ""
                fiyat_str  = texts[8] if len(texts) > 8 else ""
                stok       = texts[9] if len(texts) > 9 else "Var"
                full = " ".join(texts).lower()
            else:
                text = urun.inner_text().strip()
                if not text or len(text) < 5:
                    return None
                full = text.lower()
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                urun_adi   = lines[0] if lines else ""
                marka_text = ""
                dot        = ""
                mevsim_raw = ""
                stok       = "Var"
                fm = re.search(r'([\d.,]+)\s*(?:TL|₺)', text)
                fiyat_str  = fm.group(1) if fm else ""

            if not urun_adi:
                return None

            # Ebat filtresi
            if ebat_filtre:
                from .base import _ebat_eslesir
                if not _ebat_eslesir(ebat_filtre, full):
                    return None

            # Marka filtresi
            if marka_filtre and marka_filtre.lower() not in full:
                return None

            # Ebat
            ebat_match = re.search(r'(\d{3}/\d{2}\s*R?\d{2,3})', urun_adi)
            ebat = ebat_match.group(1) if ebat_match else ebat_filtre

            # Marka (tablo sütunundan veya ürün adından)
            if not marka_text:
                markalar = ["Continental","Michelin","Pirelli","Bridgestone","Goodyear",
                            "Lassa","Petlas","Hankook","Dunlop","Yokohama","Nokian",
                            "Starmaxx","Nexen","Kumho","Falken","Firestone","Maxxis",
                            "Linglong","Triangle","Kormoran","Nankang","Toyo"]
                marka_text = next((m for m in markalar if m.lower() in full), "Diğer")

            # Mevsim
            mevsim = "Yaz"
            mv = (mevsim_raw + " " + urun_adi).lower()
            if "kış" in mv or "winter" in mv or "kis" in mv:
                mevsim = "Kış"
            elif "4 mevsim" in mv or "all season" in mv:
                mevsim = "4 Mevsim"

            fiyat = self._fiyat_parse(fiyat_str)
            if fiyat < 100:
                return None

            return self.sonuc_olustur(
                marka=marka_text,
                model=urun_adi,
                ebat=ebat or urun_adi[:20],
                mevsim=mevsim,
                dot=dot,
                fiyat=fiyat,
                para_birimi="TL",
                stok=stok or "Var",
                site_url=SEARCH_URL
            )
        except Exception:
            return None

    def _body_text_parse(self, body_text: str, ebat_filtre: str, marka_filtre: str) -> list[LastikSonuc]:
        """Body text'inden fiyat bilgisi çıkarmayı dener."""
        sonuclar = []
        fiyat_pattern = re.finditer(r'(.{0,80})([\d.,]+)\s*(?:TL|₺)', body_text)
        for match in fiyat_pattern:
            context = match.group(1)
            fiyat = self._fiyat_parse(match.group(2))
            if fiyat < 100 or fiyat > 50000:
                continue
            
            ebat_match = re.search(r'(\d{3}/\d{2}\s*R?\d{2,3})', context)
            if not ebat_match:
                continue
                
            markalar = ["Continental", "Michelin", "Pirelli", "Bridgestone", "Goodyear",
                        "Lassa", "Petlas", "Hankook", "Dunlop"]
            marka = next((m for m in markalar if m.lower() in context.lower()), "Diğer")
            
            sonuclar.append(self.sonuc_olustur(
                marka=marka,
                model=context.strip()[:60],
                ebat=ebat_match.group(1),
                mevsim="Yaz",
                dot="",
                fiyat=fiyat,
                para_birimi="TL",
                stok="Var",
                site_url=SEARCH_URL
            ))
        return sonuclar

    @staticmethod
    def _fiyat_parse(fiyat_str: str) -> float:
        try:
            temiz = fiyat_str.replace("₺", "").replace("TL", "").replace(".", "").replace(",", ".").strip()
            match = re.search(r'[\d]+\.?\d*', temiz)
            return float(match.group()) if match else 0.0
        except (ValueError, AttributeError):
            return 0.0