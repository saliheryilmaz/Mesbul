"""
Keskin Lastik XML Servisi
URL: https://keskinlastik.com/genel/xml/DC25E3A7-7AEE-4B89-B980-7E8B7446B390

XML 60 dakikada bir çekilebilir.
Django DB cache kullanılır — tüm worker'lar aynı cache'i paylaşır,
process restart'tan etkilenmez.
"""

import re
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from django.core.cache import cache

KESKIN_XML_URL = (
    "https://keskinlastik.com/genel/xml/"
    "DC25E3A7-7AEE-4B89-B980-7E8B7446B390"
)

CACHE_KEY       = "keskin_tum_urunler"
CACHE_KEY_STALE = "keskin_tum_urunler_stale"
CACHE_TTL       = 55 * 60       # 55 dakika (rate limit 60 dk)
CACHE_TTL_STALE = 24 * 60 * 60  # 24 saat — rate limit fallback

SUBE_ALANLARI = [
    "MERKEZ_ADET", "MASLAK_ADET", "BOSTANCI_ADET", "LEVENT_ADET",
    "ANKARA_ADET", "BURSA_ADET", "SEYRANTEPE_ADET", "İZMİR_ADET",
    "HADIMKOY_ADET", "SEKERPINAR_ADET",
]


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
    kategori:  str = ""

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


def _ebat_normalize(ebat: str) -> tuple[str, str]:
    """
    "205/55R16" → ("205/55/16", "2055516")
    "205/55/16" → ("205/55/16", "2055516")
    """
    temiz = ebat.strip().upper()
    slash = re.sub(r'R(\d)', r'/\1', temiz)
    rakam = re.sub(r'[^0-9]', '', slash)
    return slash, rakam


def keskin_verileri_getir() -> list[LastikUrun]:
    """
    Keskin XML'ini çekip tüm ürün listesini döner.
    Django DB cache'e yazar — tüm worker'lar aynı cache'i paylaşır.
    """
    # Ana cache geçerliyse direkt döndür (XML çekilmez)
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    try:
        resp = requests.get(KESKIN_XML_URL, timeout=20)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except requests.RequestException as e:
        print(f"[Keskin Lastik] Bağlantı hatası: {e}")
        return cache.get(CACHE_KEY_STALE) or []
    except ET.ParseError as e:
        print(f"[Keskin Lastik] XML parse hatası: {e}")
        return cache.get(CACHE_KEY_STALE) or []

    # Rate limit yanıtı kontrolü
    if root.tag == "Hata" or root.find(".//HataMi") is not None:
        mesaj   = root.findtext(".//HataMesaj", "")
        sonraki = root.findtext(".//SonrakiXmlTarihi", "")
        print(f"[Keskin Lastik] Rate limit: {mesaj} — Sonraki: {sonraki}")
        # Stale cache varsa onu döndür (eski veri göster, hata verme)
        return cache.get(CACHE_KEY_STALE) or []

    urunler = []
    for stok in root.findall("Stok"):
        try:
            fiyat = float(stok.findtext("BAYI", "0") or "0")
            if fiyat == 0:
                continue

            toplam = 0
            for sube in SUBE_ALANLARI:
                try:
                    val = (stok.findtext(sube, "0") or "0").replace("+", "").strip()
                    toplam += float(val)
                except ValueError:
                    pass

            urunler.append(LastikUrun(
                toptanci  = "Keskin Lastik",
                stok_kodu = stok.findtext("PrcCode", ""),
                marka     = stok.findtext("Brand", ""),
                urun_adi  = stok.findtext("ACIKLAMA", ""),
                fiyat     = fiyat,
                miktar    = int(toplam),
                dot       = stok.findtext("DOT", ""),
                mevsim    = _mevsim_duzenle(stok.findtext("MEVSIM", "YAZ")),
                kategori  = stok.findtext("KATEGORİ", ""),
            ))
        except (ValueError, TypeError):
            continue

    # Ana cache (55 dk) + stale cache (24 saat)
    cache.set(CACHE_KEY, urunler, CACHE_TTL)
    cache.set(CACHE_KEY_STALE, urunler, CACHE_TTL_STALE)
    print(f"[Keskin Lastik] {len(urunler)} ürün DB cache'e yazıldı ({CACHE_TTL // 60} dk)")
    return urunler


def keskin_ara(ebat: str, marka: str = "", mevsim: str = "") -> list[LastikUrun]:
    tum_urunler = keskin_verileri_getir()

    ebat_slash, ebat_rakam = _ebat_normalize(ebat)
    marka_upper  = marka.strip().upper()
    mevsim_temiz = mevsim.strip().lower()

    sonuclar = []
    for u in tum_urunler:
        urun_upper = u.urun_adi.upper()

        if ebat.strip():
            eslesti = (
                ebat_slash in urun_upper or
                ebat_rakam in urun_upper.replace("/", "").replace("R", "")
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


def _mevsim_duzenle(ham: str) -> str:
    ham = ham.strip().upper()
    if "4" in ham or "ALL" in ham:
        return "4 Mevsim"
    if "KI" in ham:
        return "Kış"
    return "Yaz"
