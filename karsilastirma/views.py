import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin

from .uspa_servis      import uspa_ara
from .keskin_servis    import keskin_ara
from .otosemih_servis  import otosemih_ara
from .netlastik_servis import netlastik_ara
from .models import AramaGecmisi

# Toptancı B2B portal linkleri
B2B_LINKLER = {
    "USPA Lastik":    "https://www.uspalastik.com",
    "Keskin Lastik":  "https://keskinlastik.com",
    "OtoSemih":       "https://www.otosemih.com.tr",
    "NetLastik":      "https://www.netlastik.com",
}


def _tum_toptancilarda_ara(ebat: str, marka: str, mevsim: str) -> list:
    """
    Tüm XML toptancılarını paralel çalıştırır.
    Yeni toptancı eklenince GOREVLER listesine 1 satır ekle.
    """
    GOREVLER = [
        uspa_ara,
        keskin_ara,
        otosemih_ara,
        netlastik_ara,
    ]

    tum_sonuclar = []
    with ThreadPoolExecutor(max_workers=len(GOREVLER)) as executor:
        futures = {
            executor.submit(fn, ebat, marka, mevsim): fn.__module__
            for fn in GOREVLER
        }
        for future in as_completed(futures):
            modul = futures[future]
            try:
                tum_sonuclar.extend(future.result())
            except Exception as e:
                print(f"[{modul}] Hata: {e}")

    tum_sonuclar.sort(key=lambda x: x.fiyat)
    return tum_sonuclar


class AramaView(LoginRequiredMixin, View):
    template_name = "karsilastirma/arama.html"

    def get(self, request):
        gecmis = AramaGecmisi.objects.all()[:8]
        return render(request, self.template_name, {"gecmis": gecmis})


class SonuclarView(LoginRequiredMixin, View):
    template_name = "karsilastirma/sonuclar.html"

    def post(self, request):
        ebat    = request.POST.get("ebat",    "").strip()
        marka   = request.POST.get("marka",   "").strip()
        mevsim  = request.POST.get("mevsim",  "").strip()
        min_dot = request.POST.get("min_dot", "").strip()

        if not ebat:
            return render(request, "karsilastirma/arama.html",
                          {"hata": "Lütfen lastik ebatını girin."})

        sonuclar = _tum_toptancilarda_ara(ebat, marka, mevsim)

        # Marka filtresi (case-insensitive)
        if marka:
            marka_lower = marka.lower()
            sonuclar = [u for u in sonuclar if marka_lower in u.marka.lower()]

        # DOT filtresi
        if min_dot:
            try:
                min_dot_int = int(min_dot)
                def dot_gecerli(u):
                    dot = str(u.dot).strip()
                    if not dot or dot == "0":
                        return True
                    m = re.search(r'20\d{2}', dot)
                    if m:
                        return int(m.group()) >= min_dot_int
                    return True
                sonuclar = [u for u in sonuclar if dot_gecerli(u)]
            except ValueError:
                pass

        AramaGecmisi.objects.create(
            ebat=ebat,
            marka=marka,
            mevsim=mevsim,
            sonuc_sayisi=len(sonuclar),
        )

        en_ucuz_fiyat = sonuclar[0].fiyat if sonuclar else None

        toptanci_sayilari = dict(Counter(s.toptanci for s in sonuclar))
        marka_listesi = sorted(set(
            s.marka for s in sonuclar
            if s.marka and s.marka not in ("—", "Diğer", "Diger", "")
        ))

        return render(request, self.template_name, {
            "sonuclar":          sonuclar,
            "ebat":              ebat,
            "marka":             marka,
            "mevsim":            mevsim,
            "min_dot":           min_dot,
            "en_ucuz_fiyat":     en_ucuz_fiyat,
            "sonuc_sayisi":      len(sonuclar),
            "toptanci_sayilari": toptanci_sayilari,
            "marka_listesi":     marka_listesi,
            "b2b_linkler":       B2B_LINKLER,
        })


class GirisView(View):
    template_name = "karsilastirma/giris.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('arama')
        return render(request, self.template_name)

    def post(self, request):
        kullanici_adi = request.POST.get("kullanici_adi", "").strip()
        sifre         = request.POST.get("sifre", "").strip()

        kullanici = authenticate(request, username=kullanici_adi, password=sifre)
        if kullanici is not None:
            login(request, kullanici)
            next_url = request.GET.get('next', '/')
            return redirect(next_url)
        else:
            return render(request, self.template_name, {
                "hata": "Kullanıcı adı veya şifre hatalı."
            })


class CikisView(View):
    def get(self, request):
        logout(request)
        return redirect('giris')
