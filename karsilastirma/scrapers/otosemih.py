"""
OtoSemih XML Scraper
Site: https://www.otosemih.com.tr
Yöntem: XML API (login gerektirmez)

XML URL: https://www.otosemih.com.tr/outputxml/index.php?xml_service_id=4
XML yapısı:
  <urun>
    <ureticistokkodu><![CDATA[ DAYTON 11015 ]]></ureticistokkodu>
    <urunismi><![CDATA[ DAYTON 185/65R15 88H TOURING2 YAZLIK ]]></urunismi>
    <stokadedi><![CDATA[ 16 ]]></stokadedi>
    <kdvdahilfiyati><![CDATA[ 2664.00 ]]></kdvdahilfiyati>
    <urunaciklamasi><![CDATA[ ...Mevsim: Yaz... ]]></urunaciklamasi>
    <urununbulundugudepobilgisi>SAKARYA</urununbulundugudepobilgisi>
    <dottarihi><![CDATA[ ]]></dottarihi>
    <ureticikodu><![CDATA[ D11015 ]]></ureticikodu>
  </urun>

NOTLAR:
  - Marka ayrı alan yok → urunismi'nin ilk kelimesi marka
  - Mevsim ayrı alan yok → urunismi'nde YAZLIK/KISLIK veya urunaciklamasi'nda
  - Fiyat KDV dahil (kdvdahilfiyati)
"""
import re
import html
import time
import logging
import requests
import xml.etree.ElementTree as ET

from .base import BaseScraper, LastikSonuc, _ebat_eslesir

logger = logging.getLogger(__name__)

OTOSEMIH_XML_URL  = "https://www.otosemih.com.tr/outputxml/index.php?xml_service_id=4"
OTOSEMIH_SITE_URL = "https://www.otosemih.com.tr"

# Bellek cache — 55 dk geçerliliği
_cache_data: list = []
_cache_time: float = 0.0
_CACHE_TTL = 55 * 60


def _cdata_temizle(metin: str) -> str:
    """CDATA ve HTML entity'lerini temizler."""
    if not metin:
        return ""
    temiz = html.unescape(metin)
    temiz = re.sub(r'<[^>]+>', ' ', temiz)
    return temiz.strip()


def _marka_cikar(urun_adi: str) -> str:
    """
    Marka tespiti — iki format desteklenir:
      'DAYTON 185/65R15 88H TOURING2 YAZLIK' → ebat öncesi → 'Dayton'
      '195/75R16C 107/105R DAYTON VAN'       → ebat sonrası → 'Dayton'
    """
    # Önce bilinen markalar listesinde ara (en güvenilir yöntem)
    markalar = [
        "Continental", "Michelin", "Pirelli", "Bridgestone", "Goodyear",
        "Lassa", "Petlas", "Hankook", "Dunlop", "Yokohama", "Nokian",
        "Starmaxx", "Nexen", "Kumho", "Falken", "Firestone", "Maxxis",
        "Linglong", "Triangle", "Kormoran", "BFGoodrich", "Debica", "Tigar",
        "Accelera", "Nankang", "Toyo", "Sailun", "Uniroyal", "Barum",
        "Sava", "Matador", "Semperit", "Riken", "Giti", "Leao",
        "Westlake", "Goodride", "Gripmax", "Milestone", "Minerva", "Apollo",
        "Dayton", "Fulda", "Kleber", "Vredestein", "General", "Cooper",
        "Windforce", "Wintech", "Leao", "Doublestar", "Comforser",
    ]
    low = urun_adi.lower()
    found = next((m for m in markalar if m.lower() in low), None)
    if found:
        return found

    # Fallback: ebat öncesi kelimeler
    kelimeler = urun_adi.split()
    marka_kelimeleri = []
    for kelime in kelimeler:
        if re.match(r'^\d', kelime):
            break
        marka_kelimeleri.append(kelime)
    if marka_kelimeleri:
        return " ".join(marka_kelimeleri).title()

    return "Diğer"


def _mevsim_cikar(urun_adi: str, aciklama: str) -> str:
    birlestir = (urun_adi + " " + aciklama).upper()
    if "4 MEVS" in birlestir or "ALL SEASON" in birlestir or "ALL-SEASON" in birlestir:
        return "4 Mevsim"
    if "KISLIK" in birlestir or "WINTER" in birlestir or "MEVSIM: KI" in birlestir:
        return "Kış"
    return "Yaz"


class OtoSemihScraper(BaseScraper):
    """
    OtoSemih XML tabanlı scraper.
    xml_only = True → motor.py Playwright açmadan ara() metodunu çağırır.
    """
    TOPTANCI_ADI = "OtoSemih"
    xml_only = True

    def login(self, page) -> bool:
        logger.info(f"[{self.TOPTANCI_ADI}] XML modu — login atlandı")
        return True

    def ara(self, page, ebat: str, marka: str = "") -> list[LastikSonuc]:
        tum_urunler = self._xml_getir()
        if not tum_urunler:
            return []

        ebat_upper  = ebat.strip().upper().replace(" ", "")
        marka_upper = marka.strip().upper()

        sonuclar = []
        for u in tum_urunler:
            # Ebat filtresi — _ebat_eslesir ile kontrol
            if ebat_upper and not _ebat_eslesir(ebat_upper, u["urun_adi"]):
                continue

            # Marka filtresi
            if marka_upper and marka_upper not in u["marka"].upper():
                continue

            s = self._sonuc_olustur(u, ebat)
            if s:
                sonuclar.append(s)

        sonuclar.sort(key=lambda x: x.fiyat)
        logger.info(f"[{self.TOPTANCI_ADI}] {len(sonuclar)} ürün döndürüldü (ebat={ebat})")
        return sonuclar

    # ------------------------------------------------------------------
    # İç yardımcılar
    # ------------------------------------------------------------------

    def _xml_getir(self) -> list[dict]:
        global _cache_data, _cache_time

        # Bellek cache geçerliyse direkt döndür
        if _cache_data and (time.time() - _cache_time) < _CACHE_TTL:
            logger.info(f"[{self.TOPTANCI_ADI}] Bellek cache'den {len(_cache_data)} ürün döndürüldü")
            return _cache_data

        # Dosya cache'ini dene
        from .xml_cache import otosemih_xml_oku
        content = otosemih_xml_oku()

        # Dosya cache yoksa canlı çek
        if content is None:
            logger.info(f"[{self.TOPTANCI_ADI}] Dosya cache yok, canlı çekiliyor...")
            try:
                resp = requests.get(OTOSEMIH_XML_URL, timeout=30)
                resp.raise_for_status()
                content = resp.content
            except requests.RequestException as e:
                logger.error(f"[{self.TOPTANCI_ADI}] Bağlantı hatası: {e}")
                return _cache_data

        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            logger.error(f"[{self.TOPTANCI_ADI}] XML parse hatası: {e}")
            return _cache_data

        urunler = []
        for urun in root.findall("urun"):
            try:
                fiyat_str = _cdata_temizle(urun.findtext("kdvdahilfiyati", "0"))
                fiyat     = float(fiyat_str or "0")
                if fiyat == 0:
                    continue

                miktar_str = _cdata_temizle(urun.findtext("stokadedi", "0"))
                miktar     = int(float(miktar_str or "0"))

                urun_adi  = _cdata_temizle(urun.findtext("urunismi",          ""))
                aciklama  = _cdata_temizle(urun.findtext("urunaciklamasi",     ""))
                dot       = _cdata_temizle(urun.findtext("dottarihi",          ""))
                stok_kodu = _cdata_temizle(urun.findtext("ureticistokkodu",    ""))
                depo      = (urun.findtext("urununbulundugudepobilgisi") or "").strip()

                urunler.append({
                    "stok_kodu": stok_kodu,
                    "marka":     _marka_cikar(urun_adi),
                    "urun_adi":  urun_adi,
                    "fiyat":     fiyat,
                    "miktar":    miktar,
                    "dot":       dot,
                    "mevsim":    _mevsim_cikar(urun_adi, aciklama),
                    "depo":      depo,
                })
            except (ValueError, TypeError):
                continue

        _cache_data = urunler
        _cache_time = time.time()
        logger.info(f"[{self.TOPTANCI_ADI}] XML'den {len(urunler)} ürün okundu")
        return urunler

    def _sonuc_olustur(self, u: dict, ebat_f: str) -> LastikSonuc | None:
        fiyat = u["fiyat"]
        if fiyat < 100:
            return None

        urun_adi = u["urun_adi"]
        marka    = u["marka"] or "Diğer"

        # Ebatı urunismi'nden çıkar
        ebat_match = re.search(r"(\d{3}/\d{2}\s*(?:Z?R)?\s*\d{2,3}\s*C?)", urun_adi, re.IGNORECASE)
        if ebat_match:
            ebat = re.sub(r"\s+", "", ebat_match.group(1))
            ebat = re.sub(r"(?i)ZR", "R", ebat)
        else:
            ebat = ebat_f

        miktar = u["miktar"]
        if miktar <= 0:
            stok = "Yok"
        elif miktar <= 4:
            stok = f"Son {miktar} adet"
        else:
            stok = f"{miktar} adet"

        # Depo bilgisini model'e ekle
        model = urun_adi
        if u["depo"]:
            model = f"{urun_adi} [{u['depo']}]"

        return self.sonuc_olustur(
            marka=marka,
            model=model,
            ebat=ebat,
            mevsim=u["mevsim"],
            dot=u["dot"],
            fiyat=fiyat,
            para_birimi="TL",
            stok=stok,
            site_url=OTOSEMIH_SITE_URL,
        )
