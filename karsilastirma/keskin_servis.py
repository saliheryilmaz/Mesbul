"""
Keskin Lastik XML Servisi
URL: https://keskinlastik.com/genel/xml/1F3821F1-D8E4-452A-9E4B-9EFA312C6202

XML 60 dakikada bir çekilebilir (rate limit).
Django DB cache kullanılır — tüm worker'lar aynı cache'i paylaşır.

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
        <ADET>1.00</ADET>           ← veya "20+"
        <MERKEZ_ADET>1.00</MERKEZ_ADET>
        ...şube adetleri...
        <SEARCHKEYWORDS>215/55/16,2155516</SEARCHKEYWORDS>
      </Stok>
    </Stoklar>

Ebat formatı: "215/55/16" (R yok, eğik çizgili)
Stok: ADET alanı, "20+" gelirse 20 olarak alınır
"""

import re
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from django.core.cache import cache

KESKIN_XML_URL = (
    "https://keskinlastik.com/genel/xml/"
    "1F3821F1-D8E4-452A-9E4B-9EFA312C6202"
)

CACHE_KEY       = "keskin_tum_urunler"
CACHE_KEY_STALE = "keskin_tum_urunler_stale"
CACHE_TTL       = 55 * 60       # 55 dakika (rate limit 60 dk)
CACHE_TTL_STALE = 24 * 60 * 60  # 24 saat fallback

SUBE_ALANLARI = [
    "MERKEZ_ADET", "MASLAK_ADET", "BOSTANCI_ADET", "LEVENT_ADET",
    "ANKARA_ADET", "BURSA_ADET", "SEYRANTEPE_ADET", "İZMİR_ADET",
    "HADIMKOY_ADET", "SEKERPINAR_ADET",
]


@dataclass
class LastikUrun:
    toptanci:       str
    stok_kodu:      str
    marka:          str
    urun_adi:       str
    fiyat:          float
    miktar:         int
    dot:            str
    mevsim:         str
    kategori:       str = ""
    searchkeywords: str = ""

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


def _adet_parse(deger: str) -> float:
    """'20+', '1.00', '0.00' → float. '+' işaretini temizler."""
    return float((deger or "0").replace("+", "").strip() or "0")


def _mevsim_duzenle(ham: str) -> str:
    ham = ham.strip().upper()
    if "4" in ham or "ALL" in ham or "MEVSİM" in ham or "MEVSIM" in ham:
        # "4 MEVSİM" kontrolü
        if "4" in ham:
            return "4 Mevsim"
    if "KI" in ham or "WIN" in ham:
        return "Kış"
    if "4" in ham:
        return "4 Mevsim"
    return "Yaz"


def _ebat_normalize(ebat: str) -> tuple[str, str]:
    """
    "205/55R16" → slash="205/55/16", rakam="2055516"
    "205/55/16" → slash="205/55/16", rakam="2055516"
    """
    temiz = ebat.strip().upper()
    slash = re.sub(r'R(\d)', r'/\1', temiz)   # R→/
    rakam = re.sub(r'[^0-9]', '', slash)       # sadece rakamlar
    return slash, rakam


def keskin_verileri_getir() -> list[LastikUrun]:
    """
    Keskin XML'ini çekip tüm ürün listesini döner.
    Django DB cache'e yazar — rate limit nedeniyle 55 dk cache'lenir.
    """
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    try:
        resp = requests.get(KESKIN_XML_URL, timeout=25)
        resp.raise_for_status()
        content = resp.content.lstrip(b'\xef\xbb\xbf')  # BOM temizle
        root = ET.fromstring(content)
    except requests.RequestException as e:
        print(f"[Keskin Lastik] Bağlantı hatası: {e}")
        return cache.get(CACHE_KEY_STALE) or []
    except ET.ParseError as e:
        print(f"[Keskin Lastik] XML parse hatası: {e}")
        return cache.get(CACHE_KEY_STALE) or []

    # Rate limit yanıtı kontrolü
    if root.tag != "Stoklar":
        mesaj   = root.findtext(".//HataMesaj", "") or root.text or ""
        sonraki = root.findtext(".//SonrakiXmlTarihi", "")
        print(f"[Keskin Lastik] Rate limit: {mesaj} — Sonraki: {sonraki}")
        return cache.get(CACHE_KEY_STALE) or []

    urunler = []
    for stok in root.findall("Stok"):
        try:
            fiyat = float(stok.findtext("BAYI", "0") or "0")
            if fiyat < 100:
                continue

            # Önce ADET, 0 ise şubeleri topla
            adet = _adet_parse(stok.findtext("ADET", "0") or "0")
            if adet <= 0:
                for sube in SUBE_ALANLARI:
                    adet += _adet_parse(stok.findtext(sube, "0") or "0")

            if adet <= 0:
                continue

            urunler.append(LastikUrun(
                toptanci       = "Keskin Lastik",
                stok_kodu      = (stok.findtext("PrcCode", "") or "").strip(),
                marka          = (stok.findtext("Brand", "") or "").strip(),
                urun_adi       = (stok.findtext("ACIKLAMA", "") or "").strip(),
                fiyat          = fiyat,
                miktar         = int(adet),
                dot            = (stok.findtext("DOT", "") or "").strip(),
                mevsim         = _mevsim_duzenle(stok.findtext("MEVSIM", "YAZ") or "YAZ"),
                kategori       = (stok.findtext("KATEGORİ", "") or "").strip(),
                searchkeywords = (stok.findtext("SEARCHKEYWORDS", "") or "").upper(),
            ))
        except (ValueError, TypeError):
            continue

    cache.set(CACHE_KEY, urunler, CACHE_TTL)
    cache.set(CACHE_KEY_STALE, urunler, CACHE_TTL_STALE)
    print(f"[Keskin Lastik] {len(urunler)} ürün DB cache'e yazıldı ({CACHE_TTL // 60} dk)")
    return urunler


def keskin_ara(ebat: str, marka: str = "", mevsim: str = "") -> list[LastikUrun]:
    """
    Keskin verilerini filtreler.

    ebat:   "205/55R16" → ACIKLAMA ve SEARCHKEYWORDS içinde arar
    marka:  "Apollo"    → Brand alanında arar
    mevsim: "Yaz" / "Kış" / "4 Mevsim"
    """
    tum_urunler = keskin_verileri_getir()

    ebat_slash, ebat_rakam = _ebat_normalize(ebat)
    marka_upper  = marka.strip().upper()
    mevsim_temiz = mevsim.strip().lower()

    sonuclar = []
    for u in tum_urunler:
        if ebat.strip():
            urun_upper     = u.urun_adi.upper()
            urun_no_slash  = urun_upper.replace("/", "").replace(" ", "")

            eslesti = (
                ebat_slash  in urun_upper      or   # "205/55/16" in ACIKLAMA
                ebat_rakam  in urun_no_slash   or   # "2055516" in ACIKLAMA (slash yok)
                ebat_rakam  in u.searchkeywords     # "2055516" in SEARCHKEYWORDS
            )
            if not eslesti:
                continue

        if marka_upper and (marka_upper not in u.marka.upper() and marka_upper not in u.urun_adi.upper()):
            continue

        if mevsim_temiz and mevsim_temiz not in u.mevsim.lower():
            continue

        sonuclar.append(u)

    sonuclar.sort(key=lambda x: x.fiyat)
    return sonuclar
