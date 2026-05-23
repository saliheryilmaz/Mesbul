"""
USPA Lastik XML Scraper
Site: https://www.uspalastik.com
Yöntem: XML API (login gerektirmez)

XML URL: https://www.uspalastik.com/index.php?url=xml_export/uspa4
XML yapısı:
  <Urun>
    <StokKodu>CON-3523990000-18</StokKodu>
    <Marka>Continental</Marka>
    <Miktar>1</Miktar>
    <UrunAdi>275/45R18 103W FR SportContact 5 MO</UrunAdi>
    <Fiyat>2900.0000</Fiyat>
    <Dot>2018</Dot>
    <Mevsim>Yaz</Mevsim>
  </Urun>

Ebat UrunAdi içinde geçiyor → "205/55R16" aratınca UrunAdi'nde arar.
"""
import re
import time
import logging
import requests
import xml.etree.ElementTree as ET

from .base import BaseScraper, LastikSonuc, _ebat_eslesir

logger = logging.getLogger(__name__)

USPA_XML_URL  = "https://www.uspalastik.com/index.php?url=xml_export/uspa4"
USPA_SITE_URL = "https://www.uspalastik.com"

# Bellek cache
_cache_data: list = []
_cache_time: float = 0.0
_CACHE_TTL = 55 * 60


class UspaScraper(BaseScraper):
    """
    USPA Lastik XML tabanlı scraper.
    xml_only = True → motor.py Playwright açmadan ara() metodunu çağırır.
    """
    TOPTANCI_ADI = "USPA Lastik"
    xml_only = True

    def login(self, page) -> bool:
        logger.info(f"[{self.TOPTANCI_ADI}] XML modu — login atlandı")
        return True

    def ara(self, page, ebat: str, marka: str = "") -> list[LastikSonuc]:
        tum_urunler = self._xml_getir()
        if not tum_urunler:
            return []

        ebat_temiz  = re.sub(r"\s+", "", ebat.strip()).upper()
        marka_temiz = marka.strip().upper()

        sonuclar = []
        for u in tum_urunler:
            if ebat_temiz and not _ebat_eslesir(ebat_temiz, u["urun_adi"]):
                continue
            if marka_temiz and marka_temiz not in u["marka"].upper():
                continue
            s = self._sonuc_olustur(u, ebat)
            if s:
                sonuclar.append(s)

        sonuclar.sort(key=lambda x: x.fiyat)
        logger.info(f"[{self.TOPTANCI_ADI}] {len(sonuclar)} ürün döndürüldü (ebat={ebat})")
        return sonuclar

    def _xml_getir(self) -> list[dict]:
        global _cache_data, _cache_time

        # Bellek cache geçerliyse direkt döndür
        if _cache_data and (time.time() - _cache_time) < _CACHE_TTL:
            return _cache_data

        # Önce dosya cache'ini dene
        from .xml_cache import uspa_xml_oku
        content = uspa_xml_oku()

        # Dosya cache yoksa canlı çek
        if content is None:
            try:
                resp = requests.get(USPA_XML_URL, timeout=20)
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
        for urun in root.findall("Urun"):
            try:
                fiyat  = float(urun.findtext("Fiyat",  "0") or "0")
                miktar = int(urun.findtext("Miktar", "0") or "0")
                urunler.append({
                    "stok_kodu": urun.findtext("StokKodu", ""),
                    "marka":     urun.findtext("Marka",    ""),
                    "urun_adi":  urun.findtext("UrunAdi",  ""),
                    "fiyat":     fiyat,
                    "miktar":    miktar,
                    "dot":       urun.findtext("Dot",      ""),
                    "mevsim":    urun.findtext("Mevsim",   "Yaz"),
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
        marka    = u["marka"] or self._marka_tahmin(urun_adi)

        ebat_match = re.search(r"(\d{3}/\d{2}\s*R?\s*\d{2,3})", urun_adi)
        ebat = ebat_match.group(1).replace(" ", "") if ebat_match else ebat_f

        mevsim = self._mevsim_normalize(u["mevsim"], urun_adi)

        miktar = u["miktar"]
        if miktar <= 0:
            stok = "Yok"
        elif miktar <= 4:
            stok = f"Son {miktar} adet"
        else:
            stok = f"{miktar} adet"

        return self.sonuc_olustur(
            marka=marka, model=urun_adi, ebat=ebat, mevsim=mevsim,
            dot=u["dot"], fiyat=fiyat, para_birimi="TL",
            stok=stok, site_url=USPA_SITE_URL,
        )

    @staticmethod
    def _marka_tahmin(urun_adi: str) -> str:
        markalar = [
            "Continental", "Michelin", "Pirelli", "Bridgestone", "Goodyear",
            "Lassa", "Petlas", "Hankook", "Dunlop", "Yokohama", "Nokian",
            "Starmaxx", "Nexen", "Kumho", "Falken", "Firestone", "Maxxis",
            "Linglong", "Triangle", "Kormoran", "BFGoodrich", "Debica", "Tigar",
            "Accelera", "Nankang", "Toyo", "Sailun", "Uniroyal", "Barum",
            "Sava", "Matador", "Semperit", "Riken", "Giti", "Leao",
            "Westlake", "Goodride", "Gripmax", "Milestone", "Minerva",
        ]
        low = urun_adi.lower()
        return next((m for m in markalar if m.lower() in low), "Diğer")

    @staticmethod
    def _mevsim_normalize(mevsim_xml: str, urun_adi: str) -> str:
        kaynak = (mevsim_xml + " " + urun_adi).lower()
        if "kış" in kaynak or "kis" in kaynak or "winter" in kaynak or "snow" in kaynak:
            return "Kış"
        if "4 mevsim" in kaynak or "all season" in kaynak or "allseason" in kaynak:
            return "4 Mevsim"
        return "Yaz"
