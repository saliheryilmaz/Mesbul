"""
OtoSemih XML Servisi
URL: https://www.otosemih.com.tr/outputxml/index.php?xml_service_id=4

XML yapısı:
    <urun>
        <ureticistokkodu><![CDATA[ DAYTON 11015 ]]></ureticistokkodu>
        <urunismi><![CDATA[ DAYTON 185/65R15 88H TOURING2 YAZLIK ]]></urunismi>
        <stokadedi><![CDATA[ 16 ]]></stokadedi>
        <kdvdahilfiyati><![CDATA[ 2664.00 ]]></kdvdahilfiyati>
        <urunaciklamasi><![CDATA[ ...Mevsim: Yaz... ]]></urunaciklamasi>
        <urununbulundugudepobilgisi>SAKARYA</urununbulundugudepobilgisi>
        <dottarihi><![CDATA[ ]]></dottarihi>
    </urun>

NOTLAR:
  - Marka ayrı alan yok → urunismi'nin ilk kelimesi marka
  - Mevsim ayrı alan yok → urunismi'nde YAZLIK/KISLIK veya urunaciklamasi'nda
  - Fiyat KDV dahil (kdvdahilfiyati)
"""

import re
import html
import time
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass

OTOSEMIH_XML_URL = "https://www.otosemih.com.tr/outputxml/index.php?xml_service_id=4"

# Bellek cache — 55 dk geçerliliği
_cache_data: list = []
_cache_time: float = 0.0
_CACHE_TTL = 55 * 60


@dataclass
class LastikUrun:
    toptanci:  str
    stok_kodu: str
    marka:     str
    urun_adi:  str
    fiyat:     float
    miktar:    int
    dot:       str
    mevsim:    str
    depo:      str = ""

    @property
    def fiyat_str(self) -> str:
        return f"{self.fiyat:,.2f} ₺"

    @property
    def stok_str(self) -> str:
        if self.miktar <= 0:
            return "Yok"
        if self.miktar <= 4:
            return f"Son {self.miktar} adet"
        return f"{self.miktar} adet"


# ── Yardımcı fonksiyonlar ──────────────────────────────────────────────────

def _cdata_temizle(metin: str) -> str:
    if not metin:
        return ""
    temiz = html.unescape(metin)
    temiz = re.sub(r'<[^>]+>', ' ', temiz)
    return temiz.strip()


def _marka_cikar(urun_adi: str) -> str:
    """
    Önce bilinen markalar listesinde ara, sonra ebat öncesi kelimeler.
    'DAYTON 185/65R15...' → 'Dayton'
    '195/75R16C ... DAYTON VAN' → 'Dayton'
    """
    markalar = [
        "Continental", "Michelin", "Pirelli", "Bridgestone", "Goodyear",
        "Lassa", "Petlas", "Hankook", "Dunlop", "Yokohama", "Nokian",
        "Starmaxx", "Nexen", "Kumho", "Falken", "Firestone", "Maxxis",
        "Linglong", "Triangle", "Kormoran", "BFGoodrich", "Debica", "Tigar",
        "Accelera", "Nankang", "Toyo", "Sailun", "Uniroyal", "Barum",
        "Sava", "Matador", "Semperit", "Riken", "Giti", "Leao",
        "Westlake", "Goodride", "Gripmax", "Milestone", "Minerva", "Apollo",
        "Dayton", "Fulda", "Kleber", "Vredestein", "General", "Cooper",
        "Windforce", "Wintech", "Doublestar", "Comforser",
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
    return " ".join(marka_kelimeleri).title() if marka_kelimeleri else "Diğer"


def _mevsim_cikar(urun_adi: str, aciklama: str) -> str:
    birlestir = (urun_adi + " " + aciklama).upper()
    if "4 MEVS" in birlestir or "ALL SEASON" in birlestir or "ALL-SEASON" in birlestir:
        return "4 Mevsim"
    if "KISLIK" in birlestir or "WINTER" in birlestir or "MEVSIM: KI" in birlestir:
        return "Kış"
    return "Yaz"


# ── Ana servis fonksiyonları ───────────────────────────────────────────────

def otosemih_verileri_getir() -> list[LastikUrun]:
    """OtoSemih XML'ini çekip tüm ürün listesini döner. 55 dk cache'ler."""
    global _cache_data, _cache_time

    if _cache_data and (time.time() - _cache_time) < _CACHE_TTL:
        return _cache_data

    try:
        resp = requests.get(OTOSEMIH_XML_URL, timeout=20)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except requests.RequestException as e:
        print(f"[OtoSemih] Bağlantı hatası: {e}")
        return _cache_data
    except ET.ParseError as e:
        print(f"[OtoSemih] XML parse hatası: {e}")
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

            urunler.append(LastikUrun(
                toptanci  = "OtoSemih",
                stok_kodu = stok_kodu,
                marka     = _marka_cikar(urun_adi),
                urun_adi  = urun_adi,
                fiyat     = fiyat,
                miktar    = miktar,
                dot       = dot,
                mevsim    = _mevsim_cikar(urun_adi, aciklama),
                depo      = depo,
            ))
        except (ValueError, TypeError):
            continue

    _cache_data = urunler
    _cache_time = time.time()
    return urunler


def otosemih_ara(ebat: str, marka: str = "", mevsim: str = "") -> list[LastikUrun]:
    """
    OtoSemih verilerini filtreler.
    ebat:   "205/55R16" → urunismi içinde arar
    marka:  "Continental" → marka alanında arar
    mevsim: "Yaz" / "Kış" / "4 Mevsim"
    """
    tum_urunler = otosemih_verileri_getir()

    ebat_upper   = ebat.strip().upper().replace(" ", "")
    marka_upper  = marka.strip().upper()
    mevsim_temiz = mevsim.strip().lower()

    sonuclar = []
    for u in tum_urunler:
        urun_upper = u.urun_adi.upper().replace(" ", "")

        # Ebat eşleşmesi
        if ebat_upper and ebat_upper not in urun_upper:
            continue

        # Marka filtresi — marka alanında VEYA ürün adında ara
        if marka_upper and (marka_upper not in u.marka.upper() and marka_upper not in u.urun_adi.upper()):
            continue

        # Mevsim filtresi
        if mevsim_temiz and mevsim_temiz not in u.mevsim.lower():
            continue

        sonuclar.append(u)

    sonuclar.sort(key=lambda x: x.fiyat)
    return sonuclar
