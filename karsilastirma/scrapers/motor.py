"""
Tüm scraperları çalıştıran motor.
Django view'ından şu şekilde çağrılır:

    from karsilastirma.scrapers.motor import fiyat_topla
    sonuclar = fiyat_topla(ebat="205/55R16", marka="Continental")
"""
import os
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from .keskin     import KeskinLastikScraper
from .koc        import KocOtomotivScraper
from .otosemih   import OtoSemihScraper
from .cakiroglu  import CakirogluScraper
from .tiryakiler import TiryakilerScraper
from .mollaoglu  import MollaogluScraper
from .netlastik  import NetLastikScraper
from .uspa       import UspaScraper
from .lastsis    import LastSisScraper
from .lastikpark import LastikParkScraper
from .ek_toptancilar import (
    AykoScraper,
    DrmScraper,
    GulerScraper,
    HaskarScraper,
    MedLastikScraper,
    MutaflarScraper,
    UstundagScraper,
    YukeScraper,
)
from .base       import LastikSonuc

# Proje kökündeki .env (cwd'den bağımsız — LastikPark vb. kimlikler her zaman okunur)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))


def _cred(key: str) -> str:
    return (os.getenv(key) or "").strip()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Screenshot klasörü
SCREENSHOT_DIR = os.path.join(_PROJECT_ROOT, "debug_screenshots")
DEFAULT_PAGE_TIMEOUT_MS = int(os.getenv("SCRAPER_PAGE_TIMEOUT_MS", "45000"))
MAX_WORKERS = int(os.getenv("SCRAPER_MAX_WORKERS", "6"))
GLOBAL_TIMEOUT_SECONDS = int(os.getenv("SCRAPER_GLOBAL_TIMEOUT_SECONDS", "360"))


def _scraper_calistir(scraper_cls, kullanici, sifre, ebat, marka, ekstra="") -> list[LastikSonuc]:
    """Tek bir scraper'ı çalıştırır.
    xml_only=True olan scraper'lar Playwright açmadan doğrudan ara() çağırır.
    """
    try:
        import inspect
        sig = inspect.signature(scraper_cls.__init__)
        if "sirket" in sig.parameters:
            scraper = scraper_cls(kullanici, sifre, ekstra)
        elif "pin" in sig.parameters:
            scraper = scraper_cls(kullanici, sifre, ekstra)
        else:
            scraper = scraper_cls(kullanici, sifre)
    except Exception:
        scraper = scraper_cls(kullanici, sifre)

    sonuclar = []
    logger.info(f"[{scraper.TOPTANCI_ADI}] Başlatılıyor...")

    # XML tabanlı scraper'lar Playwright gerektirmez
    if getattr(scraper_cls, "xml_only", False):
        try:
            sonuclar = scraper.ara(None, ebat, "")
            logger.info(f"[{scraper.TOPTANCI_ADI}] ✅ {len(sonuclar)} ürün bulundu (XML)")
        except Exception as e:
            logger.error(f"[{scraper.TOPTANCI_ADI}] ❌ XML scraper hatası: {e}")
            traceback.print_exc()
        return sonuclar

    # Playwright tabanlı scraper'lar
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled']
            )
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale='tr-TR',
                timezone_id='Europe/Istanbul'
            )
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """)
            page = context.new_page()
            page.set_default_timeout(DEFAULT_PAGE_TIMEOUT_MS)

            try:
                login_success = scraper.login(page)
                if login_success:
                    logger.info(f"[{scraper.TOPTANCI_ADI}] ✅ Login başarılı, arama yapılıyor...")
                    sonuclar = scraper.ara(page, ebat, "")
                    logger.info(f"[{scraper.TOPTANCI_ADI}] ✅ {len(sonuclar)} ürün bulundu")
                    if not sonuclar:
                        logger.warning(f"[{scraper.TOPTANCI_ADI}] ⚠️ Login başarılı ama sonuç yok")
                        _save_screenshot(page, scraper.TOPTANCI_ADI, "arama_bos")
                else:
                    logger.warning(f"[{scraper.TOPTANCI_ADI}] ❌ Login başarısız, atlandı")
                    _save_screenshot(page, scraper.TOPTANCI_ADI, "login_basarisiz")
            except Exception as e:
                logger.error(f"[{scraper.TOPTANCI_ADI}] ❌ Scraper hatası: {e}")
                _save_screenshot(page, scraper.TOPTANCI_ADI, "hata")
                traceback.print_exc()
            finally:
                browser.close()
    except Exception as e:
        logger.error(f"[{scraper.TOPTANCI_ADI}] ❌ Playwright başlatma hatası: {e}")
        traceback.print_exc()

    return sonuclar


def _save_screenshot(page, toptanci_adi: str, durum: str):
    """Debug için screenshot kaydeder."""
    try:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        safe_name = toptanci_adi.replace(" ", "_").replace("ö", "o").replace("ü", "u").replace("ı", "i").replace("ç", "c").replace("ğ", "g").replace("ş", "s")
        path = os.path.join(SCREENSHOT_DIR, f"{safe_name}_{durum}.png")
        page.screenshot(path=path, full_page=True)
        logger.info(f"[{toptanci_adi}] Screenshot kaydedildi: {path}")
    except Exception as e:
        logger.warning(f"[{toptanci_adi}] Screenshot kaydedilemedi: {e}")


def fiyat_topla(ebat: str, marka: str = "") -> list[LastikSonuc]:
    """
    Tüm aktif scraperları paralel olarak çalıştırır.
    Sonuçları fiyata göre sıralı döner.
    """
    # .env'den bilgileri al
    SCRAPERLAR = [
        {"cls": KeskinLastikScraper,
         "kullanici": "",   # XML API — credential gerektirmez
         "sifre": ""},
        {"cls": KocOtomotivScraper,
         "kullanici": _cred("KOC_KULLANICI"),
         "sifre": _cred("KOC_SIFRE")},
        {"cls": OtoSemihScraper,
         "kullanici": "",   # XML API — credential gerektirmez
         "sifre": ""},
        {"cls": CakirogluScraper,
         "kullanici": _cred("CAKIROGLU_KULLANICI"),
         "sifre": _cred("CAKIROGLU_SIFRE")},
        {"cls": TiryakilerScraper,
         "kullanici": _cred("TIRYAKILER_KULLANICI"),
         "sifre": _cred("TIRYAKILER_SIFRE")},
        {"cls": MollaogluScraper,
         "kullanici": _cred("MOLLAOGLU_KULLANICI"),
         "sifre": _cred("MOLLAOGLU_SIFRE")},
        {"cls": NetLastikScraper,
         "kullanici": _cred("NETLASTIK_KULLANICI"),
         "sifre": _cred("NETLASTIK_SIFRE")},
        {"cls": UspaScraper,
         "kullanici": "",   # XML API — credential gerektirmez
         "sifre": ""},
        {"cls": LastSisScraper,
         "kullanici": "",   # Site 404 — devre dışı
         "sifre": ""},
        # LastikPark bayi portalı (Tatko girişi): LASTIKPARK_KULLANICI, LASTIKPARK_SIFRE, isteğe bağlı LASTIKPARK_SIRKET
        {"cls": LastikParkScraper,
         "kullanici": _cred("LASTIKPARK_KULLANICI"),
         "sifre": _cred("LASTIKPARK_SIFRE"),
         "sirket": _cred("LASTIKPARK_SIRKET")},
        {"cls": YukeScraper,
         "kullanici": _cred("YUKE_KULLANICI"),
         "sifre": _cred("YUKE_SIFRE")},
        {"cls": DrmScraper,
         "kullanici": _cred("DRM_KULLANICI"),
         "sifre": _cred("DRM_SIFRE")},
        {"cls": UstundagScraper,
         "kullanici": _cred("USTUNDAG_KULLANICI"),
         "sifre": _cred("USTUNDAG_SIFRE")},
        {"cls": MutaflarScraper,
         "kullanici": _cred("MUTAFLAR_KULLANICI"),
         "sifre": _cred("MUTAFLAR_SIFRE")},
        {"cls": GulerScraper,
         "kullanici": _cred("GULER_KULLANICI"),
         "sifre": _cred("GULER_SIFRE"),
         "pin": _cred("GULER_PIN")},
        {"cls": AykoScraper,
         "kullanici": _cred("AYKO_KULLANICI"),
         "sifre": _cred("AYKO_SIFRE")},
        {"cls": HaskarScraper,
         "kullanici": _cred("HASKAR_KULLANICI"),
         "sifre": _cred("HASKAR_SIFRE")},
        {"cls": MedLastikScraper,
         "kullanici": _cred("MEDLASTIK_KULLANICI"),
         "sifre": _cred("MEDLASTIK_SIFRE")},
    ]

    # Eksik credential'ları filtrele (xml_only scraper'lar muaf)
    aktif_scraperlar = []
    atlananlar: list[str] = []
    for s in SCRAPERLAR:
        if getattr(s["cls"], "xml_only", False):
            aktif_scraperlar.append(s)  # XML scraper'lar credential gerektirmez
        elif not s["kullanici"] or not s["sifre"]:
            msg = f"[{s['cls'].TOPTANCI_ADI}] Kullanıcı bilgileri eksik, atlanıyor"
            logger.warning(msg)
            atlananlar.append(s["cls"].TOPTANCI_ADI)
        else:
            aktif_scraperlar.append(s)


    logger.info(f"Arama başlıyor: ebat='{ebat}' marka='{marka}' — {len(aktif_scraperlar)} toptancı")
    if atlananlar:
        logger.info(f"Kullanıcı/şifre eksik atlananlar: {', '.join(atlananlar)}")


    tum_sonuclar: list[LastikSonuc] = []
    sonuc_durumu: dict[str, int] = {}  # toptancı -> sonuç sayısı
    login_basarisi: dict[str, str] = {}  # (opsiyonel) debug amaçlı


    # Paralel çalıştır. Varsayılan 8 işçi canlı aramayı belirgin hızlandırır.
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(
                _scraper_calistir,
                s["cls"], s["kullanici"], s["sifre"], ebat, marka,
                s.get("sirket") or s.get("pin", "")
            ): s["cls"].TOPTANCI_ADI
            for s in aktif_scraperlar
        }

        try:
            # Global timeout'u sınırlı tutup tamamlanan sonuçları hızlı döndür.
            for future in as_completed(futures, timeout=GLOBAL_TIMEOUT_SECONDS):
                toptanci_adi = futures[future]
                try:
                    # as_completed sadece tamamlanan future döndürür, ek timeout gerekmiyor.
                    sonuclar = future.result()
                    tum_sonuclar.extend(sonuclar)
                    sonuc_durumu[toptanci_adi] = len(sonuclar)
                    logger.info(f"[{toptanci_adi}] ✅ {len(sonuclar)} sonuç eklendi")

                except Exception as e:
                    logger.error(f"[{toptanci_adi}] ❌ HATA: {e}")
                    traceback.print_exc()
        except TimeoutError:
            logger.error(f"Bazı toptancılar genel süreyi aştı ({GLOBAL_TIMEOUT_SECONDS}sn). Tamamlanan sonuçlar döndürülüyor.")
            for future, toptanci_adi in futures.items():
                if not future.done():
                    future.cancel()
                    logger.error(f"[{toptanci_adi}] ⏱️ Süre aşıldı, bu toptancı atlandı")

    # Fiyata göre sırala (en ucuz üstte)
    tum_sonuclar.sort(key=lambda x: x.fiyat)

    # Debug özet
    if sonuc_durumu:
        sifirlar = [k for k,v in sonuc_durumu.items() if v == 0]
        if sifirlar:
            logger.warning(f"0 sonuç dönenler: {', '.join(sifirlar)}")

        en_az = sorted(sonuc_durumu.items(), key=lambda kv: kv[1])[:5]
        logger.info("En düşük sonuçlu ilk 5:")
        for k, v in en_az:
            logger.info(f"- {k}: {v}")

    logger.info(f"TOPLAM: {len(tum_sonuclar)} ürün bulundu")
    return tum_sonuclar
