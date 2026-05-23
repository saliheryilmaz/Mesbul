"""
Keskin Lastik XML Servisi
URL: https://keskinlastik.com/genel/xml/DC25E3A7-7AEE-4B89-B980-7E8B7446B390

XML yapısı:
    <Stok>
        <PrcCode>APOLLO-16005</PrcCode>
        <ACIKLAMA>215/55/16 93V PREMIUM LIFE ALNAC 4G</ACIKLAMA>
        <Brand>APOLLO</Brand>
        <KATEGORİ>BİNEK</KATEGORİ>
        <MEVSIM>YAZ</MEVSIM>
        <DOT>2025</DOT>
        <BAYI>3250</BAYI>           ← bayi fiyatı
        <ADET>1.00</ADET>           ← toplam stok
        <MERKEZ_ADET>1.00</MERKEZ_ADET>
        <SEARCHKEYWORDS>215/55/16,2155516</SEARCHKEYWORDS>
    </Stok>

NOT: Keskin ebat formatı "215/55/16" şeklinde (R yok).
     Kullanıcı "205/55R16" yazsa da "205/55/16" formatına normalize edip ararız.
     XML 60 dakikada bir çekilebilir — cache ile gereksiz istek önlenir.
"""

import os
import re
import time
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass

KESKIN_XML_URL = (
    "https://keskinlastik.com/genel/xml/"
    "DC25E3A7-7AEE-4B89-B980-7E8B7446B390"
)

# Cache: 55 dakika geçerliliği (rate limit 60 dk, biraz pay bırakıyoruz)
_CACHE_TTL = 55 * 60  # saniye
_cache_data: list = []
_cache_time: float = 0.0

KESKIN_XML_URL = (
    "https://keskinlastik.com/genel/xml/"
    "DC25E3A7-7AEE-4B89-B980-7E8B7446B390"
)

# Şube adları — toplam stok hesabında hepsini toplarız
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
    Kullanıcının yazdığı ebatı iki formata çevirir:
      "205/55R16" → ("205/55/16", "2055516")
      "205/55/16" → ("205/55/16", "2055516")
    Dönen tuple: (slash_format, rakam_format)
    """
    temiz = ebat.strip().upper()
    # R harfini / ile değiştir: "205/55R16" → "205/55/16"
    slash = re.sub(r'R(\d)', r'/\1', temiz)
    # Sadece rakamları al: "2055516"
    rakam = re.sub(r'[^0-9]', '', slash)
    return slash, rakam


def keskin_verileri_getir() -> list[LastikUrun]:
    """Keskin XML'ini çekip tüm ürün listesini döner. Sonucu 55 dk cache'ler."""
    global _cache_data, _cache_time

    # Cache geçerliyse direkt döndür
    if _cache_data and (time.time() - _cache_time) < _CACHE_TTL:
        return _cache_data

    try:
        resp = requests.get(KESKIN_XML_URL, timeout=20)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except requests.RequestException as e:
        print(f"[Keskin Lastik] Bağlantı hatası: {e}")
        return _cache_data  # eski cache varsa onu döndür
    except ET.ParseError as e:
        print(f"[Keskin Lastik] XML parse hatası: {e}")
        return _cache_data

    # Rate limit kontrolü
    if root.tag == "Hata" or root.find(".//HataMi") is not None:
        mesaj   = root.findtext(".//HataMesaj", "")
        sonraki = root.findtext(".//SonrakiXmlTarihi", "")
        print(f"[Keskin Lastik] Rate limit: {mesaj} — Sonraki: {sonraki}")
        return _cache_data  # eski cache varsa onu döndür

    urunler = []
    for stok in root.findall("Stok"):
        try:
            # Fiyat — BAYI alanını kullan, 0 ise listeye alma
            fiyat = float(stok.findtext("BAYI", "0") or "0")
            if fiyat == 0:
                continue

            # Toplam stok — tüm şubelerin toplamı
            # "20+" gibi değerleri de destekle: sadece rakam kısmını al
            toplam = 0
            for sube in SUBE_ALANLARI:
                try:
                    val = (stok.findtext(sube, "0") or "0").replace("+", "").strip()
                    toplam += float(val)
                except ValueError:
                    pass

            mevsim_ham = stok.findtext("MEVSIM", "YAZ")
            mevsim = _mevsim_duzenle(mevsim_ham)

            urunler.append(LastikUrun(
                toptanci  = "Keskin Lastik",
                stok_kodu = stok.findtext("PrcCode", ""),
                marka     = stok.findtext("Brand", ""),
                urun_adi  = stok.findtext("ACIKLAMA", ""),
                fiyat     = fiyat,
                miktar    = int(toplam),
                dot       = stok.findtext("DOT", ""),
                mevsim    = mevsim,
                kategori  = stok.findtext("KATEGORİ", ""),
            ))
        except (ValueError, TypeError):
            continue

    # Cache'e yaz
    _cache_data = urunler
    _cache_time = time.time()
    return urunler


def keskin_ara(ebat: str, marka: str = "", mevsim: str = "") -> list[LastikUrun]:
    """
    Keskin verilerini filtreler.
    ebat:   "205/55R16" veya "205/55/16" — her iki formatta da arar
    marka:  "Continental" → Brand alanında arar
    mevsim: "Yaz" / "Kış" / "4 Mevsim"
    """
    tum_urunler = keskin_verileri_getir()

    ebat_slash, ebat_rakam = _ebat_normalize(ebat)
    marka_upper  = marka.strip().upper()
    mevsim_temiz = mevsim.strip().lower()

    sonuclar = []
    for u in tum_urunler:
        urun_upper = u.urun_adi.upper()

        # Ebat eşleşmesi — slash format VEYA rakam format
        if ebat.strip():
            eslesti = (
                ebat_slash  in urun_upper or
                ebat_rakam  in urun_upper.replace("/", "").replace("R", "")
            )
            if not eslesti:
                continue

        # Marka filtresi — Brand alanında VEYA ürün adında ara
        if marka_upper and (marka_upper not in u.marka.upper() and marka_upper not in u.urun_adi.upper()):
            continue

        # Mevsim filtresi
        if mevsim_temiz and mevsim_temiz not in u.mevsim.lower():
            continue

        sonuclar.append(u)

    sonuclar.sort(key=lambda x: x.fiyat)
    return sonuclar


def _mevsim_duzenle(ham: str) -> str:
    """'YAZ' → 'Yaz', 'KIS' → 'Kış', '4 MEVSIM' → '4 Mevsim'"""
    ham = ham.strip().upper()
    if "4" in ham or "ALL" in ham:
        return "4 Mevsim"
    if "KI" in ham:
        return "Kış"
    return "Yaz"
