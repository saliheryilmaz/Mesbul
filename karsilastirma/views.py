import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator

from .uspa_servis      import uspa_ara
from .keskin_servis    import keskin_ara
from .otosemih_servis  import otosemih_ara
from .netlastik_servis import netlastik_ara
from .lastsis_servis   import lastsis_ara
from .dincbay_servis   import dincbay_ara
from .models import AramaGecmisi, Abonelik, Odeme


class AbonelikGerekli(LoginRequiredMixin):
    """
    Giriş yapılmamış kullanıcıları ana sayfaya (modal ile) yönlendirir.
    Giriş yapılmış ama aboneliği olmayan veya süresi dolmuş
    kullanıcıları bilgilendirme sayfasına yönlendirir.
    """
    login_url = '/'
    redirect_field_name = 'next'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if not request.user.is_staff:
            try:
                abonelik = request.user.abonelik
                if not abonelik.erisim_var_mi:
                    return render(request, "karsilastirma/abonelik_bitti.html", {
                        "bitis": abonelik.bitis,
                        "plan":  abonelik.plan,
                    }, status=403)
            except Abonelik.DoesNotExist:
                return render(request, "karsilastirma/abonelik_bitti.html", {
                    "bitis": None,
                    "plan":  None,
                }, status=403)

        return super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)

# ── Marka normalize ──────────────────────────────────────────────────────────

# Bilinen yazım varyantlarını canonical forma eşle
# Anahtar: küçük harf + boşluk normalize edilmiş → Değer: gösterilecek isim
MARKA_ESLESME = {
    # ── Continental ──
    "continental":       "Continental",
    "continenta":        "Continental",
    "contintental":      "Continental",
    "continetal":        "Continental",
    "contiental":        "Continental",

    # ── Bridgestone ──
    "bridgestone":       "Bridgestone",
    "bridgeston":        "Bridgestone",
    "bridgstonne":       "Bridgestone",
    "brigdestone":       "Bridgestone",

    # ── Michelin ──
    "michelin":          "Michelin",
    "michellin":         "Michelin",
    "michlin":           "Michelin",

    # ── Pirelli ──
    "pirelli":           "Pirelli",
    "pirrelli":          "Pirelli",
    "pireli":            "Pirelli",

    # ── Goodyear ──
    "goodyear":          "Goodyear",
    "good year":         "Goodyear",
    "goodyear dunlop":   "Goodyear",

    # ── Dunlop ──
    "dunlop":            "Dunlop",

    # ── Hankook ──
    "hankook":           "Hankook",
    "han kook":          "Hankook",
    "hankuk":            "Hankook",

    # ── Yokohama ──
    "yokohama":          "Yokohama",
    "yokahoma":          "Yokohama",

    # ── Falken ──
    "falken":            "Falken",

    # ── Kumho ──
    "kumho":             "Kumho",

    # ── Lassa ──
    "lassa":             "Lassa",

    # ── Petlas ──
    "petlas":            "Petlas",

    # ── Maxxis ──
    "maxxis":            "Maxxis",

    # ── Toyo ──
    "toyo":              "Toyo",
    "toyo tires":        "Toyo",

    # ── Uniroyal ──
    "uniroyal":          "Uniroyal",

    # ── Nokian ──
    "nokian":            "Nokian",
    "nokian tyres":      "Nokian",

    # ── BFGoodrich ──
    "bfgoodrich":        "BFGoodrich",
    "bf goodrich":       "BFGoodrich",
    "bf-goodrich":       "BFGoodrich",

    # ── Apollo ──
    "apollo":            "Apollo",

    # ── Debica / Dębica ──
    "debica":            "Debica",
    "dębica":            "Debica",
    "debıca":            "Debica",

    # ── Dayton ──
    "dayton":            "Dayton",

    # ── Barum ──
    "barum":             "Barum",

    # ── Firestone ──
    "firestone":         "Firestone",

    # ── Nexen ──
    "nexen":             "Nexen",

    # ── Starmaxx ──
    "starmaxx":          "Starmaxx",

    # ── Linglong ──
    "linglong":          "Linglong",
    "ling long":         "Linglong",

    # ── Triangle ──
    "triangle":          "Triangle",

    # ── Kormoran ──
    "kormoran":          "Kormoran",

    # ── Tigar ──
    "tigar":             "Tigar",

    # ── Fulda ──
    "fulda":             "Fulda",

    # ── Kleber ──
    "kleber":            "Kleber",

    # ── Vredestein ──
    "vredestein":        "Vredestein",

    # ── General ──
    "general":           "General",
    "general tire":      "General",

    # ── Cooper ──
    "cooper":            "Cooper",

    # ── Sailun ──
    "sailun":            "Sailun",

    # ── Sava ──
    "sava":              "Sava",

    # ── Matador ──
    "matador":           "Matador",

    # ── Semperit ──
    "semperit":          "Semperit",

    # ── Riken ──
    "riken":             "Riken",

    # ── Giti ──
    "giti":              "Giti",

    # ── Leao ──
    "leao":              "Leao",

    # ── Westlake ──
    "westlake":          "Westlake",

    # ── Goodride ──
    "goodride":          "Goodride",

    # ── Nankang ──
    "nankang":           "Nankang",

    # ── Accelera ──
    "accelera":          "Accelera",

    # ── Gripmax ──
    "gripmax":           "Gripmax",

    # ── Milestone ──
    "milestone":         "Milestone",

    # ── Minerva ──
    "minerva":           "Minerva",

    # ── Windforce ──
    "windforce":         "Windforce",

    # ── Wintech ──
    "wintech":           "Wintech",

    # ── Doublestar ──
    "doublestar":        "Doublestar",

    # ── Comforser ──
    "comforser":         "Comforser",

    # ── Laufenn ──
    "laufenn":           "Laufenn",

    # ── Zeetex ──
    "zeetex":            "Zeetex",

    # ── Mazzini ──
    "mazzini":           "Mazzini",

    # ── Torque ──
    "torque":            "Torque",

    # ── Haida ──
    "haida":             "Haida",

    # ── Austone ──
    "austone":           "Austone",

    # ── Aplus ──
    "aplus":             "Aplus",

    # ── Cachland ──
    "cachland":          "Cachland",
}

def _normalize_marka(marka: str) -> str:
    """Marka adını normalize eder: whitespace temizle, küçük harfe çevir, eşleşme tablosuna bak."""
    if not marka:
        return marka
    temiz = " ".join(marka.strip().split())  # çoklu boşlukları tek yap
    anahtar = temiz.lower()
    if anahtar in MARKA_ESLESME:
        return MARKA_ESLESME[anahtar]
    # Eşleşme yoksa: İlk harf büyük, geri kalanı küçük (CONTINENTAL → Continental)
    # title() yerine capitalize() — çok kelimeli markalarda her kelime büyük
    return " ".join(w.capitalize() for w in temiz.split())


# Toptancı B2B portal linkleri ve logo bilgileri
B2B_LINKLER = {
    "USPA Lastik":   {"url": "https://www.uspalastik.com",  "logo": "toptancilar/uspa1.png"},
    "Keskin Lastik": {"url": "https://keskinlastik.com",    "logo": "toptancilar/keskin0.png"},
    "OtoSemih":      {"url": "https://www.otosemih.com.tr", "logo": "toptancilar/otosemih.png"},
    "NetLastik":     {"url": "https://www.netlastik.com",   "logo": "toptancilar/eksililogo.avif"},
    "Lastsis":       {"url": "https://panel.lastsis.com",   "logo": "toptancilar/yocar0.png"},
    "Dinçbay":       {"url": "http://95.13.23.154:9015",    "logo": "toptancilar/dincbaylogo.png"},
}


def _tum_toptancilarda_ara(ebat: str, marka: str, mevsim: str) -> tuple[list, list]:
    """
    Tüm XML toptancılarını paralel çalıştırır.
    Döner: (sonuclar, hatali_toptancilar)
    Hatalı toptancı listesi kullanıcıya gösterilir.
    """
    GOREVLER = [
        uspa_ara,
        keskin_ara,
        otosemih_ara,
        netlastik_ara,
        lastsis_ara,
        dincbay_ara,
    ]

    # Modül adı → görünen toptancı adı
    MODUL_ISIM = {
        "karsilastirma.uspa_servis":      "USPA Lastik",
        "karsilastirma.keskin_servis":    "Keskin Lastik",
        "karsilastirma.otosemih_servis":  "OtoSemih",
        "karsilastirma.netlastik_servis": "NetLastik",
        "karsilastirma.lastsis_servis":   "Lastsis",
        "karsilastirma.dincbay_servis":   "Dinçbay",
    }

    tum_sonuclar = []
    hatali_toptancilar = []

    with ThreadPoolExecutor(max_workers=len(GOREVLER)) as executor:
        futures = {
            executor.submit(fn, ebat, marka, mevsim): fn.__module__
            for fn in GOREVLER
        }
        for future in as_completed(futures):
            modul = futures[future]
            try:
                sonuc = future.result()
                tum_sonuclar.extend(sonuc)
            except Exception as e:
                isim = MODUL_ISIM.get(modul, modul)
                print(f"[{isim}] Hata: {e}")
                hatali_toptancilar.append(isim)

    tum_sonuclar.sort(key=lambda x: x.fiyat)
    return tum_sonuclar, hatali_toptancilar


class AramaView(View):
    """
    Giriş yapılmamış kullanıcıya sayfayı göster ama giriş modali otomatik açık gelsin.
    Giriş yapılmış ama aboneliği bitmiş kullanıcıya abonelik_bitti sayfası göster.
    """
    template_name = "karsilastirma/arama.html"

    def get(self, request):
        # Abonelik kontrolü (sadece giriş yapılmışsa)
        if request.user.is_authenticated and not request.user.is_staff:
            try:
                abonelik = request.user.abonelik
                if not abonelik.erisim_var_mi:
                    return render(request, "karsilastirma/abonelik_bitti.html", {
                        "bitis": abonelik.bitis,
                        "plan":  abonelik.plan,
                    }, status=403)
            except Abonelik.DoesNotExist:
                return render(request, "karsilastirma/abonelik_bitti.html", {
                    "bitis": None,
                    "plan":  None,
                }, status=403)

        gecmis = AramaGecmisi.objects.filter(kullanici=request.user)[:8] if request.user.is_authenticated else []

        # Giriş hatası varsa (modal açık dönecek) veya giriş yapılmamışsa modal_acik=True
        login_hata = request.GET.get("login_hata", "")
        modal_acik = not request.user.is_authenticated or bool(login_hata)

        return render(request, self.template_name, {
            "gecmis":      gecmis,
            "b2b_linkler": B2B_LINKLER,
            "modal_acik":  modal_acik,
            "login_hata":  login_hata,
            "login_u":     request.GET.get("u", ""),
        })


class SonuclarView(AbonelikGerekli, View):
    template_name = "karsilastirma/sonuclar.html"

    def post(self, request):
        ebat    = request.POST.get("ebat",    "").strip()
        marka   = request.POST.get("marka",   "").strip()
        mevsim  = request.POST.get("mevsim",  "").strip()
        min_dot = request.POST.get("min_dot", "").strip()

        if not ebat:
            return render(request, "karsilastirma/arama.html",
                          {"hata": "Lütfen lastik ebatını girin."})

        # Tüm mevsimleri çek — filtreleme tamamen frontend'de (sidebar) yapılır
        sonuclar, hatali_toptancilar = _tum_toptancilarda_ara(ebat, marka, "")

        # Marka adlarını normalize et (CONTINENTAL, Continenta → Continental)
        for u in sonuclar:
            u.marka = _normalize_marka(u.marka)

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
            kullanici=request.user if request.user.is_authenticated else None,
            ebat=ebat,
            marka=marka,
            mevsim=mevsim,
            sonuc_sayisi=len(sonuclar),
        )

        en_ucuz_fiyat = sonuclar[0].fiyat if sonuclar else None

        toptanci_sayilari = dict(Counter(s.toptanci for s in sonuclar))

        # Marka listesi: normalize edilmiş, case-insensitive unique, sıralı
        # lower() → canonical form dict ile duplicate'ları kesin engelle
        _marka_dict: dict[str, str] = {}
        for s in sonuclar:
            if s.marka and s.marka not in ("—", "Diğer", "Diger", ""):
                key = s.marka.lower().strip()
                if key not in _marka_dict:
                    _marka_dict[key] = s.marka
        marka_listesi = sorted(_marka_dict.values())

        return render(request, self.template_name, {
            "sonuclar":           sonuclar,
            "ebat":               ebat,
            "marka":              marka,
            "mevsim":             mevsim,
            "min_dot":            min_dot,
            "en_ucuz_fiyat":      en_ucuz_fiyat,
            "sonuc_sayisi":       len(sonuclar),
            "toptanci_sayilari":  toptanci_sayilari,
            "marka_listesi":      marka_listesi,
            "b2b_linkler":        B2B_LINKLER,
            "hatali_toptancilar": hatali_toptancilar,
        })


class GirisView(View):
    template_name = "karsilastirma/giris.html"

    def get(self, request):
        # Artık bu sayfa sadece fallback — modal olan ana sayfaya yönlendir
        if request.user.is_authenticated:
            if not request.user.is_staff:
                try:
                    abonelik = request.user.abonelik
                    if not abonelik.erisim_var_mi:
                        return render(request, "karsilastirma/abonelik_bitti.html", {
                            "bitis": abonelik.bitis,
                            "plan":  abonelik.plan,
                        }, status=403)
                except Abonelik.DoesNotExist:
                    return render(request, "karsilastirma/abonelik_bitti.html", {
                        "bitis": None,
                        "plan":  None,
                    }, status=403)
            return redirect('arama')
        return redirect('arama')  # Giriş modali ana sayfada açılacak

    def post(self, request):
        kullanici_adi = request.POST.get("kullanici_adi", "").strip()
        sifre         = request.POST.get("sifre", "").strip()
        next_url      = request.POST.get("next", "/").strip() or "/"

        kullanici = authenticate(request, username=kullanici_adi, password=sifre)
        if kullanici is not None:
            login(request, kullanici)

            # Abonelik kontrolü: süresi dolmuşsa bilgilendirme sayfası
            if not kullanici.is_staff:
                try:
                    abonelik = kullanici.abonelik
                    if not abonelik.erisim_var_mi:
                        return render(request, "karsilastirma/abonelik_bitti.html", {
                            "bitis": abonelik.bitis,
                            "plan":  abonelik.plan,
                        }, status=403)
                except Abonelik.DoesNotExist:
                    return render(request, "karsilastirma/abonelik_bitti.html", {
                        "bitis": None,
                        "plan":  None,
                    }, status=403)

            return redirect(next_url)
        else:
            # Hatalı giriş → ana sayfaya dön, modal hata ile açık gelsin
            return redirect(f'/?login_hata=1&u={kullanici_adi}')


@method_decorator(staff_member_required(login_url='giris'), name='dispatch')
class KullaniciEkleView(View):
    """Yeni kullanıcı oluştur + abonelik ata. Sadece staff."""

    def post(self, request):
        from .models import Abonelik
        from datetime import date

        username = request.POST.get("username", "").strip()
        email    = request.POST.get("email", "").strip()
        sifre    = request.POST.get("sifre", "").strip()
        plan     = request.POST.get("plan", "demo")
        bitis    = request.POST.get("bitis", "")

        hata = None

        if not username or not sifre or not bitis:
            hata = "Kullanıcı adı, şifre ve bitiş tarihi zorunludur."
        elif User.objects.filter(username=username).exists():
            hata = f'"{username}" kullanıcı adı zaten kullanımda.'
        else:
            try:
                bitis_tarihi = date.fromisoformat(bitis)
            except ValueError:
                hata = "Geçersiz tarih formatı."

        if hata:
            kullanicilar = User.objects.filter(is_staff=False).prefetch_related('abonelik').order_by('username')
            from django.utils import timezone
            return render(request, "karsilastirma/abonelik_yonetim.html", {
                "kullanicilar": kullanicilar,
                "bugun":        timezone.localdate(),
                "form_hata":    hata,
                "form_data":    request.POST,
            })

        yeni = User.objects.create_user(username=username, email=email, password=sifre)
        Abonelik.objects.create(kullanici=yeni, plan=plan, bitis=bitis_tarihi, aktif=True)
        return redirect('abonelik_yonetim')


@method_decorator(staff_member_required(login_url='giris'), name='dispatch')
class OdemeEkleView(View):
    """Admin tarafından kullanıcıya ödeme kaydı ekler."""

    def post(self, request):
        from datetime import date
        kullanici_id = request.POST.get("kullanici_id")
        tutar        = request.POST.get("tutar", "").strip()
        tarih        = request.POST.get("tarih", "").strip()
        yontem       = request.POST.get("yontem", "havale")
        aciklama     = request.POST.get("aciklama", "").strip()

        kullanici = get_object_or_404(User, pk=kullanici_id, is_staff=False)

        try:
            tutar_dec   = float(tutar.replace(",", "."))
            tarih_obj   = date.fromisoformat(tarih)
        except (ValueError, TypeError):
            return redirect('abonelik_yonetim')

        Odeme.objects.create(
            kullanici = kullanici,
            tutar     = tutar_dec,
            tarih     = tarih_obj,
            yontem    = yontem,
            aciklama  = aciklama,
        )
        return redirect('abonelik_yonetim')


class OdemeGecmisiView(AbonelikGerekli, View):
    """Kullanıcının kendi ödeme geçmişini görür."""
    template_name = "karsilastirma/odeme_gecmisi.html"

    def get(self, request):
        odemeler = Odeme.objects.filter(kullanici=request.user).order_by("-tarih")
        toplam   = sum(o.tutar for o in odemeler)
        return render(request, self.template_name, {
            "odemeler": odemeler,
            "toplam":   toplam,
        })


class CikisView(View):
    def get(self, request):
        logout(request)
        return redirect('arama')  # Ana sayfa — modal otomatik açılacak


@method_decorator(staff_member_required(login_url='giris'), name='dispatch')
class AbonelikYonetimView(View):
    """Sadece staff kullanıcılar erişebilir. Tüm kullanıcıları ve abonelik durumlarını listeler."""
    template_name = "karsilastirma/abonelik_yonetim.html"

    def get(self, request):
        from django.utils import timezone
        from datetime import timedelta
        from .models import Abonelik

        bugun = timezone.localdate()
        hafta_sonu = bugun + timedelta(days=7)

        kullanicilar = User.objects.filter(is_staff=False).prefetch_related('abonelik').order_by('username')

        aktif_sayisi = sum(1 for u in kullanicilar if hasattr(u, 'abonelik') and u.abonelik.erisim_var_mi)
        bu_hafta_biten = Abonelik.objects.filter(bitis__gte=bugun, bitis__lte=hafta_sonu, aktif=True).count()

        return render(request, self.template_name, {
            "kullanicilar":    kullanicilar,
            "bugun":           bugun,
            "aktif_sayisi":    aktif_sayisi,
            "bu_hafta_biten":  bu_hafta_biten,
        })


@method_decorator(staff_member_required(login_url='giris'), name='dispatch')
class AbonelikKaydetView(View):
    """Yeni abonelik ekle veya mevcut aboneliği güncelle."""

    def post(self, request, kullanici_id):
        from datetime import date
        from .models import Abonelik

        kullanici = get_object_or_404(User, pk=kullanici_id, is_staff=False)

        plan    = request.POST.get("plan", "demo")
        bitis   = request.POST.get("bitis", "")
        aktif   = request.POST.get("aktif") == "on"

        if not bitis:
            return redirect('abonelik_yonetim')

        try:
            bitis_tarihi = date.fromisoformat(bitis)
        except ValueError:
            return redirect('abonelik_yonetim')

        Abonelik.objects.update_or_create(
            kullanici=kullanici,
            defaults={
                "plan":   plan,
                "bitis":  bitis_tarihi,
                "aktif":  aktif,
            }
        )
        return redirect('abonelik_yonetim')
