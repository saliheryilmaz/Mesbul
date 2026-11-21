from gzip import decompress
from threading import Event
from unittest.mock import Mock, patch

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache, caches
from django.test import SimpleTestCase, TestCase, override_settings

from . import netlastik_servis, uspa_servis, views
from .katalog_onbellek import ToptanciAramaHatasi, katalog_onbellek
from .models import AramaGecmisi


@override_settings(CACHES={
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "katalog-testleri",
    },
})
class KatalogOnbellekTestleri(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_guncel_bos_katalog_yeniden_indirilmez(self):
        cache.set("guncel", [])
        indir = Mock()
        getir = katalog_onbellek("guncel", "yedek")(indir)

        self.assertEqual(getir(), [])
        indir.assert_not_called()

    def test_onbellek_bosken_ilk_katalog_beklenir(self):
        indir = Mock(return_value=["ilk katalog"])
        getir = katalog_onbellek("guncel", "yedek")(indir)

        self.assertEqual(getir(), ["ilk katalog"])
        indir.assert_called_once_with()

    def test_yedek_katalog_yenileme_beklenmeden_kullanilir(self):
        basladi = Event()
        devam_et = Event()
        tamamlandi = Event()
        cache.set("yedek", ["eski katalog"])

        def indir():
            basladi.set()
            if devam_et.wait(5):
                cache.set("guncel", ["yeni katalog"])
            tamamlandi.set()

        indirme = Mock(side_effect=indir)
        getir = katalog_onbellek("guncel", "yedek")(indirme)

        try:
            self.assertEqual(getir(), ["eski katalog"])
            self.assertTrue(basladi.wait(5))
            self.assertEqual(getir(), ["eski katalog"])
            indirme.assert_called_once_with()
        finally:
            devam_et.set()
            self.assertTrue(tamamlandi.wait(5))

        self.assertEqual(getir(), ["yeni katalog"])

    def test_katalog_indirme_hatasi_bos_sonuc_sayilmaz(self):
        with patch.object(uspa_servis.requests, "get", side_effect=requests.Timeout):
            with self.assertRaises(ToptanciAramaHatasi):
                uspa_servis.uspa_ara("205/55R16")

    def test_netlastik_hatasi_bos_sonuc_sayilmaz(self):
        response = requests.Response()
        response.status_code = 429
        with patch.object(netlastik_servis, "NETLASTIK_API_KEY", "test"):
            with patch.object(netlastik_servis.requests, "get", return_value=response):
                with self.assertRaises(ToptanciAramaHatasi):
                    netlastik_servis.netlastik_ara("205/55R16")


class AramaSonuclariTestleri(TestCase):
    def setUp(self):
        caches["arama_sonuclari"].clear()
        self.client.force_login(get_user_model().objects.create_user(username="arama-test", is_staff=True))

    def ara(self, **filtreler):
        return self.client.post("/sonuclar/", {"ebat": "205/55R16", **filtreler})

    def test_ayni_ebatta_filtreler_ve_hatali_toptancinin_tekrar_denenmesi(self):
        yaz = uspa_servis.LastikUrun("USPA Lastik", "1", "Continental", "Yaz Modeli", 1800, 4, "2026", "Yaz")
        kis = uspa_servis.LastikUrun("USPA Lastik", "2", "Michelin", "Kış Modeli", 2200, 2, "2024", "Kış")
        uspa = Mock(return_value=[yaz, kis])
        bos = Mock(return_value=[])
        gecici_hata = Mock(side_effect=[ToptanciAramaHatasi("zaman aşımı"), []])
        kaynaklar = {"USPA Lastik": uspa, "Keskin Lastik": bos, "NetLastik": gecici_hata}

        with patch.dict(views.TOPTANCI_ARAMALARI, kaynaklar, clear=True):
            ilk = self.ara(marka="Continental", min_dot="2026")
            self.assertContains(ilk, "Yaz Modeli")
            self.assertNotContains(ilk, "Kış Modeli")
            self.assertEqual(ilk.context["hatali_toptancilar"], ["NetLastik"])

            ikinci = self.ara(marka="Michelin", mevsim="Kış", min_dot="2024")
            self.assertContains(ikinci, "Kış Modeli")
            self.assertEqual(ikinci.context["hatali_toptancilar"], [])
            self.assertEqual(ikinci.context["mevsim"], "Kış")
            self.assertContains(self.ara(), "Yaz Modeli")
            self.assertEqual(AramaGecmisi.objects.count(), 3)

        uspa.assert_called_once_with("205/55R16")
        bos.assert_called_once_with("205/55R16")
        self.assertEqual(gecici_hata.call_count, 2)

    @override_settings(CACHES={
        "arama_sonuclari": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "arama-suresi-testleri",
        },
    })
    def test_kaynaklar_iki_dakika_saklanir_ve_tekrar_deneme_sureyi_uzatmaz(self):
        zaman = 1000
        ilk = Mock(return_value=[])
        ikinci = Mock(side_effect=[ToptanciAramaHatasi("zaman aşımı"), []])
        kaynaklar = {"USPA Lastik": ilk, "NetLastik": ikinci}

        with patch.dict(views.TOPTANCI_ARAMALARI, kaynaklar, clear=True):
            with patch("django.core.cache.backends.locmem.time.time", side_effect=lambda: zaman):
                views._tum_toptancilarda_ara("205/55R16")
                zaman = 1060
                views._tum_toptancilarda_ara("205/55R16")
                zaman = 1119
                views._tum_toptancilarda_ara("205/55R16")
                self.assertEqual(ilk.call_count, 1)
                zaman = 1120
                views._tum_toptancilarda_ara("205/55R16")

        self.assertEqual(ilk.call_count, 2)
        self.assertEqual(ikinci.call_count, 2)

    def test_170_urunluk_sonuc_sayfasi_gzip_ile_gonderilebilir(self):
        urunler = [
            uspa_servis.LastikUrun(
                "USPA Lastik", str(i), "Continental", f"Continental 205/55R16 Test Modeli {i:03}",
                1700 + i, 8, "2026", "4 Mevsim",
            )
            for i in range(170)
        ]
        uspa = Mock(return_value=urunler)
        with patch.dict(views.TOPTANCI_ARAMALARI, {"USPA Lastik": uspa}, clear=True):
            duz = self.client.post("/sonuclar/", {"ebat": "205/55R16"})
            gzip = self.client.post("/sonuclar/", {"ebat": "205/55R16"}, HTTP_ACCEPT_ENCODING="gzip")

        self.assertEqual(duz.status_code, 200)
        self.assertNotIn("Content-Encoding", duz.headers)
        self.assertEqual(gzip.headers["Content-Encoding"], "gzip")
        self.assertIn("Accept-Encoding", gzip.headers["Vary"])
        self.assertEqual(decompress(gzip.content).count(b'class="data-row'), 170)
        self.assertLess(len(gzip.content), len(duz.content) // 4)
        uspa.assert_called_once_with("205/55R16")
