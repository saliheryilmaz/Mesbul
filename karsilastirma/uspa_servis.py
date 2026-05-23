"""
USPA Lastik XML Servisi
URL: https://www.uspalastik.com/index.php?url=xml_export/uspa4

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

import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass

USPA_XML_URL = "https://www.uspalastik.com/index.php?url=xml_export/uspa4"


@dataclass
class LastikUrun:
    toptanci:    str
    stok_kodu:   str
    marka:       str
    urun_adi:    str   # tam ürün adı (ebat + model buradan okunur)
    fiyat:       float
    miktar:      int
    dot:         str
    mevsim:      str

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


def uspa_verileri_getir() -> list[LastikUrun]:
    """
    USPA XML'ini çekip tüm ürün listesini döner.
    Hata durumunda boş liste döner.
    """
    try:
        resp = requests.get(USPA_XML_URL, timeout=20)
        resp.raise_for_status()
        # XML encoding bazen sorun çıkarır, content ile parse et
        root = ET.fromstring(resp.content)
    except requests.RequestException as e:
        print(f"[USPA] Bağlantı hatası: {e}")
        return []
    except ET.ParseError as e:
        print(f"[USPA] XML parse hatası: {e}")
        return []

    urunler = []
    for urun in root.findall("Urun"):
        try:
            fiyat_str = urun.findtext("Fiyat", "0")
            fiyat     = float(fiyat_str)
            miktar    = int(urun.findtext("Miktar", "0"))

            urunler.append(LastikUrun(
                toptanci  = "USPA Lastik",
                stok_kodu = urun.findtext("StokKodu", ""),
                marka     = urun.findtext("Marka", ""),
                urun_adi  = urun.findtext("UrunAdi", ""),
                fiyat     = fiyat,
                miktar    = miktar,
                dot       = urun.findtext("Dot", ""),
                mevsim    = urun.findtext("Mevsim", "Yaz"),
            ))
        except (ValueError, TypeError):
            continue  # bozuk satırı atla

    return urunler


def uspa_ara(ebat: str, marka: str = "", mevsim: str = "") -> list[LastikUrun]:
    """
    USPA verilerini filtreler.

    ebat:   "205/55R16"  → UrunAdi içinde arar (büyük/küçük harf yok sayılır)
    marka:  "Continental" → Marka alanında arar
    mevsim: "Yaz" / "Kış" / "4 Mevsim" → boşsa hepsi gelir
    """
    tum_urunler = uspa_verileri_getir()

    ebat_temiz   = ebat.strip().upper().replace(" ", "")
    marka_temiz  = marka.strip().upper()
    mevsim_temiz = mevsim.strip()

    sonuclar = []
    for u in tum_urunler:
        urun_adi_upper = u.urun_adi.upper().replace(" ", "")

        # Ebat eşleşmesi — UrunAdi içinde geçiyor mu?
        if ebat_temiz and ebat_temiz not in urun_adi_upper:
            continue

        # Marka filtresi — Marka alanında VEYA ürün adında ara
        if marka_temiz and (marka_temiz not in u.marka.upper() and marka_temiz not in u.urun_adi.upper()):
            continue

        # Mevsim filtresi
        if mevsim_temiz and mevsim_temiz.lower() not in u.mevsim.lower():
            continue

        sonuclar.append(u)

    # Fiyata göre sırala — en ucuz üstte
    sonuclar.sort(key=lambda x: x.fiyat)
    return sonuclar
