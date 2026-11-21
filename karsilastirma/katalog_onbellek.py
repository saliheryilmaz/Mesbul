import logging
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from functools import wraps
from threading import Lock
from time import monotonic

from django.core.cache import cache
from django.db import connections


logger = logging.getLogger(__name__)
_yenileme_havuzu = ThreadPoolExecutor(max_workers=4, thread_name_prefix="katalog")
_yenileme_araligi = 120
_yedek_katalog_kullanildi = ContextVar("yedek_katalog_kullanildi", default=False)


class ToptanciAramaHatasi(Exception):
    """Toptancı kullanılabilir bir yanıt veremedi."""


def toptanci_sorgula(ara, ebat):
    """Ürünleri ve aramanın yedek katalog kullanıp kullanmadığını döndürür."""
    token = _yedek_katalog_kullanildi.set(False)
    try:
        return ara(ebat), _yedek_katalog_kullanildi.get()
    finally:
        _yedek_katalog_kullanildi.reset(token)
        connections.close_all()


def katalog_onbellek(guncel_anahtar, yedek_anahtar):
    """Güncel katalog yoksa son kopyayı sunup yenilemeyi arka plana alır."""
    yenileme_anahtari = f"{guncel_anahtar}:yenileme"

    def dekorator(katalog_indir):
        kilit = Lock()
        yenileme = None
        tekrar_zamani = 0

        def arka_planda_yenile():
            try:
                if cache.get(guncel_anahtar) is None and cache.add(
                    yenileme_anahtari, True, timeout=_yenileme_araligi
                ):
                    katalog_indir()
            except ToptanciAramaHatasi as hata:
                logger.warning("Katalog yenilenemedi (%s): %s", guncel_anahtar, hata)
            except Exception:
                logger.exception("Katalog yenilenemedi: %s", guncel_anahtar)
            finally:
                connections.close_all()

        @wraps(katalog_indir)
        def katalog_getir():
            nonlocal yenileme, tekrar_zamani

            katalog = cache.get(guncel_anahtar)
            if katalog is not None:
                return katalog

            yedek = cache.get(yedek_anahtar)
            if yedek is None:
                return katalog_indir()

            with kilit:
                simdi = monotonic()
                if simdi >= tekrar_zamani and (yenileme is None or yenileme.done()):
                    yenileme = _yenileme_havuzu.submit(arka_planda_yenile)
                    tekrar_zamani = simdi + _yenileme_araligi
            _yedek_katalog_kullanildi.set(True)
            return yedek

        return katalog_getir

    return dekorator
