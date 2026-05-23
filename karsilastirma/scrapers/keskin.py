"""
Keskin Lastik XML Scraper
Site: https://keskinlastik.com
Yöntem: XML API (login gerektirmez)

XML URL: https://keskinlastik.com/genel/xml/DC25E3A7-7AEE-4B89-B980-7E8B7446B390
XML yapısı:
  <Stoklar>
    <Stok>
      <PrcCode>APOLLO-16005</PrcCode>
      <ACIKLAMA>215/55/16 93V PREMIUM LIFE ALNAC 4G</ACIKLAMA>
      <Brand>APOLLO</Brand>
      <KATEGORİ>BİNEK</KATEGORİ>
      <MEVSIM>YAZ</MEVSIM>
      <DOT>2025</DOT>
      <BAYI>3250</BAYI>
      <ADET>1.00</ADET>
      <MERKEZ_ADET>1.00</MERKEZ_ADET>
      ...şube adetleri...
      <SEARCHKEYWORDS>215/55/16,2155516</SEARCHKEYWORDS>
    </Stok>
  </Stoklar>

NOT: Ebat formatı "215/55/16" (R yok). Kullanıcı "205/55R16" yazsa da
     "205/55/16" formatına normalize edip ACIKLAMA + SEARCHKEYWORDS'de aranır.
     XML 60 dakikada bir çekilebilir (rate limit).
"""
import re
import time
import logging
import requests
import xml.etree.ElementTree as ET

from .base import BaseScraper, LastikSonuc

logger = logging.getLogger(__name__)

KESKIN_XML_URL = (
    "https://keskinlastik.com/genel/xml/"
    "DC25E3A7-7AEE-4B89-B980-7E8B7446B390"
)
KESKIN_SITE_URL = "https://keskinlastik.com"

# Bellek cache — 55 dk geçerliliği (rate limit 60 dk)
_cache_data: list = []
_cache_time: float = 0.0
_CACHE_TTL = 55 * 60

SUBE_ALANLARI = [
    "MERKEZ_ADET", "MASLAK_ADET", "BOSTANCI_ADET", "LEVENT_ADET",
    "ANKARA_ADET", "BURSA_ADET", "SEYRANTEPE_ADET", "İZMİR_ADET",
    "HADIMKOY_ADET", "SEKERPINAR_ADET",
]


def _ebat_normalize(ebat: str) -> tuple[str, str]:
    """
    "205/55R16" → ("205/55/16", "2055516")
    "205/55/16" → ("205/55/16", "2055516")
    """
    temiz = ebat.strip().upper()
    slash = re.sub(r'R(\d)', r'/\1', temiz)
    rakam = re.sub(r'[^0-9]', '', slash)
    return slash, rakam


def _mevsim_duzenle(ham: str) -> str:
    ham = ham.strip().upper()
    if "4" in ham or "ALL" in ham:
        return "4 Mevsim"
    if "KI" in ham:
        return "Kış"
    return "Yaz"


class KeskinLastikScraper(BaseScraper):
    """
    Keskin Lastik XML tabanlı scraper.
    xml_only = True → motor.py Playwright açmadan ara() metodunu çağırır.
    """
    TOPTANCI_ADI = "Keskin Lastik"
    xml_only = True

    def login(self, page) -> bool:
        logger.info(f"[{self.TOPTANCI_ADI}] XML modu — login atlandı")
        return True

    def ara(self, page, ebat: str, marka: str = "") -> list[LastikSonuc]:
        tum_urunler = self._xml_getir()
        if not tum_urunler:
            return []

        ebat_slash, ebat_rakam = _ebat_normalize(ebat)
        marka_upper = marka.strip().upper()

        sonuclar = []
        for u in tum_urunler:
            if ebat.strip():
                urun_upper = u["urun_adi"].upper()
                kw = u["keywords"].upper().replace("/", "").replace("R", "")
                eslesti = (
                    ebat_slash in urun_upper or
                    ebat_rakam in urun_upper.replace("/", "").replace("R", "") or
                    ebat_rakam in kw
                )
                if not eslesti:
                    continue

            if marka_upper and marka_upper not in u["marka"].upper():
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
            logger.info(f"[{self.TOPTANCI_ADI}] Bellek cache'den {len(_cache_data)} ürün döndürüldü")
            return _cache_data

        # Önce dosya cache'ini dene (PythonAnywhere scheduled task tarafından doldurulur)
        from .xml_cache import keskin_xml_oku, xml_indir, KESKIN_CACHE_FILE, KESKIN_XML_URL
        content = keskin_xml_oku()

        # Dosya cache yoksa canlı çek
        if content is None:
            logger.info(f"[{self.TOPTANCI_ADI}] Dosya cache yok, canlı çekiliyor...")
            try:
                resp = requests.get(KESKIN_XML_URL, timeout=20)
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

        # Rate limit kontrolü
        if root.tag == "Hata" or root.find(".//HataMi") is not None:
            mesaj   = root.findtext(".//HataMesaj", "")
            sonraki = root.findtext(".//SonrakiXmlTarihi", "")
            logger.warning(f"[{self.TOPTANCI_ADI}] Rate limit: {mesaj} — Sonraki: {sonraki}")
            return _cache_data

        urunler = []
        for stok in root.findall("Stok"):
            try:
                fiyat = float(stok.findtext("BAYI", "0") or "0")
                if fiyat == 0:
                    continue

                toplam = 0.0
                for sube in SUBE_ALANLARI:
                    try:
                        val = (stok.findtext(sube, "0") or "0").replace("+", "").strip()
                        toplam += float(val)
                    except ValueError:
                        pass

                urunler.append({
                    "stok_kodu": stok.findtext("PrcCode",        ""),
                    "marka":     stok.findtext("Brand",          ""),
                    "urun_adi":  stok.findtext("ACIKLAMA",       ""),
                    "fiyat":     fiyat,
                    "miktar":    int(toplam),
                    "dot":       stok.findtext("DOT",            ""),
                    "mevsim":    stok.findtext("MEVSIM",         "YAZ"),
                    "keywords":  stok.findtext("SEARCHKEYWORDS", ""),
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

        ebat_match = re.search(r"(\d{3}/\d{2}[/R]\d{2,3})", urun_adi, re.IGNORECASE)
        if ebat_match:
            ebat = re.sub(r"(\d{3}/\d{2})/(\d{2,3})", r"\1R\2", ebat_match.group(1))
        else:
            ebat = ebat_f

        mevsim = _mevsim_duzenle(u["mevsim"])

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
            stok=stok, site_url=KESKIN_SITE_URL,
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
            "Westlake", "Goodride", "Gripmax", "Milestone", "Minerva", "Apollo",
        ]
        low = urun_adi.lower()
        return next((m for m in markalar if m.lower() in low), "Diğer")
