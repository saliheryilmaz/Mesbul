from django.urls import path
from .views import (AramaView, SonuclarView, GirisView, CikisView,
                    AbonelikYonetimView, AbonelikKaydetView,
                    KullaniciEkleView, OdemeGecmisiView, OdemeEkleView,
                    NotlarView, NotEkleView, NotSilView, UyelikTalepView,
                    IskontoYonetimView)

urlpatterns = [
    path("",                              AramaView.as_view(),           name="arama"),
    path("sonuclar/",                     SonuclarView.as_view(),        name="sonuclar"),
    path("giris/",                        GirisView.as_view(),           name="giris"),
    path("cikis/",                        CikisView.as_view(),           name="cikis"),
    path("abonelikler/",                  AbonelikYonetimView.as_view(), name="abonelik_yonetim"),
    path("abonelikler/<int:kullanici_id>/kaydet/", AbonelikKaydetView.as_view(), name="abonelik_kaydet"),
    path("abonelikler/kullanici-ekle/",   KullaniciEkleView.as_view(),   name="kullanici_ekle"),
    path("abonelikler/odeme-ekle/",       OdemeEkleView.as_view(),       name="odeme_ekle"),
    path("odeme-gecmisim/",               OdemeGecmisiView.as_view(),    name="odeme_gecmisi"),
    # Notlar
    path("notlar/",                       NotlarView.as_view(),          name="notlar"),
    path("notlar/ekle/",                  NotEkleView.as_view(),         name="not_ekle"),
    path("notlar/<int:not_id>/sil/",      NotSilView.as_view(),          name="not_sil"),
    # Üyelik talebi
    path("uyelik-talep/",                 UyelikTalepView.as_view(),     name="uyelik_talep"),
    # İskonto yönetimi
    path("iskonto/",                      IskontoYonetimView.as_view(),  name="iskonto_yonetim"),
]
