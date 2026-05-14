import re
import logging
from collections import Counter
from django.shortcuts import render
from django.views import View

from .scrapers.motor import fiyat_topla
from .models import AramaGecmisi

logger = logging.getLogger(__name__)


def _normalize_filter_text(value: str) -> str:
    """Make filters tolerant to Turkish/ascii/mojibake variants."""
    text = (value or "").strip().lower()
    replacements = {
        "ı": "i",
        "İ": "i",
        "ş": "s",
        "Ş": "s",
        "ğ": "g",
        "Ğ": "g",
        "ü": "u",
        "Ü": "u",
        "ö": "o",
        "Ö": "o",
        "ç": "c",
        "Ç": "c",
        "Ä±": "i",
        "Ä°": "i",
        "ÅŸ": "s",
        "Å": "s",
        "ÄŸ": "g",
        "Ä": "g",
        "Ã¼": "u",
        "Ãœ": "u",
        "Ã¶": "o",
        "Ã–": "o",
        "Ã§": "c",
        "Ã‡": "c",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _mevsim_eslesir(secili: str, sonuc_mevsim: str) -> bool:
    selected = _normalize_filter_text(secili)
    actual = _normalize_filter_text(sonuc_mevsim)

    if not selected or selected in {"tumu", "tum", "all"}:
        return True
    if selected in {"kis", "winter"}:
        return any(token in actual for token in ["kis", "winter", "snow", "polar"])
    if selected in {"yaz", "summer"}:
        return any(token in actual for token in ["yaz", "summer"])
    if "4" in selected or "dort" in selected or "all season" in selected:
        return any(token in actual for token in ["4", "dort", "all season", "allseason"])
    return selected in actual


class AramaView(View):
    """Ana sayfa — arama formu."""
    template_name = "karsilastirma/arama.html"

    def get(self, request):
        gecmis = AramaGecmisi.objects.all()[:10]
        return render(request, self.template_name, {"gecmis": gecmis})


class SonuclarView(View):
    """Arama sonuçları — karşılaştırma tablosu."""
    template_name = "karsilastirma/sonuclar.html"

    def post(self, request):
        ebat   = request.POST.get("ebat", "").strip()
        marka  = request.POST.get("marka", "").strip()
        mevsim = request.POST.get("mevsim", "").strip()

        if not ebat:
            return render(request, "karsilastirma/arama.html",
                          {"hata": "Lütfen lastik ebatını girin."})

        # Ebat formatını normalize et
        ebat = ebat.strip()
        ebat = re.sub(r'\s+', '', ebat)  # boşlukları kaldır

        # 2055516 → 205/55R16 (7 veya 8 rakam)
        m = re.match(r'^(\d{3})(\d{2})(\d{2,3})$', ebat)
        if m:
            ebat = f"{m.group(1)}/{m.group(2)}R{m.group(3)}"

        # 205/55/16 → 205/55R16
        ebat = re.sub(r'(\d{3}/\d{2})/(\d{2,3})', r'\1R\2', ebat)

        # 205/55r16 → 205/55R16
        ebat = re.sub(r'r(\d)', lambda m: 'R' + m.group(1), ebat, flags=re.IGNORECASE)

        # Scraperları çalıştır — marka filtresi burada uygulanacak, scraper tüm ürünleri getirir
        hata_mesaji = None
        try:
            sonuclar = fiyat_topla(ebat=ebat, marka=marka)
        except Exception as e:
            logger.error(f"Scraper hatası: {e}")
            sonuclar = []
            hata_mesaji = f"Scraper hatası oluştu: {e}"

        logger.info(f"Toplam {len(sonuclar)} ham sonuç geldi (filtre öncesi)")

        # Tüm sonuçlardan toptancı ve marka listelerini çıkar (filtre öncesi)
        toptanci_sayilari = Counter(s.toptanci for s in sonuclar)
        marka_listesi = sorted(set(s.marka for s in sonuclar if s.marka and s.marka not in ("—", "Diğer", "Diger")))

        # Toplam ürün sayısı (filtre öncesi)
        toplam_urun = len(sonuclar)

        # Marka filtresi (opsiyonel)
        if marka:
            marka_lower = marka.lower()
            sonuclar = [s for s in sonuclar
                        if marka_lower in s.marka.lower()
                        or marka_lower in s.model.lower()]

        # Mevsim filtresi (opsiyonel)
        if mevsim and _normalize_filter_text(mevsim) not in {"tumu", "tum"}:
            sonuclar = [s for s in sonuclar if _mevsim_eslesir(mevsim, s.mevsim)]

        # Aramayı kaydet
        AramaGecmisi.objects.create(
            ebat=ebat,
            marka=marka,
            mevsim=mevsim,
            sonuc_sayisi=len(sonuclar),
        )

        # En ucuz vurgulama için
        en_ucuz_fiyat = sonuclar[0].fiyat if sonuclar else None

        # Toptancı bazlı istatistik (filtre sonrası)
        toptanci_filtreli = Counter(s.toptanci for s in sonuclar)

        return render(request, self.template_name, {
            "sonuclar":            sonuclar,
            "ebat":                ebat,
            "marka":               marka,
            "mevsim":              mevsim,
            "en_ucuz_fiyat":       en_ucuz_fiyat,
            "sonuc_sayisi":        len(sonuclar),
            "toplam_urun":         toplam_urun,
            "toptanci_sayilari":   dict(toptanci_sayilari),
            "toptanci_filtreli":   dict(toptanci_filtreli),
            "marka_listesi":       marka_listesi,
            "hata_mesaji":         hata_mesaji,
        })
