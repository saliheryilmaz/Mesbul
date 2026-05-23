"""
XML Cache Yöneticisi
Keskin ve USPA XML'lerini dosyaya kaydeder.
PythonAnywhere Scheduled Task ile 50 dakikada bir çalıştırılır:
    python /home/<kullanici>/lastik_sistemi/karsilastirma/scrapers/xml_cache.py

Scraper'lar bu dosyaları okur — kullanıcı araması hiç rate limit yemez.
"""
import os
import time
import logging
import requests

logger = logging.getLogger(__name__)

# Cache dosyaları proje kökünde saklanır
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
KESKIN_CACHE_FILE   = os.path.join(_BASE_DIR, "keskin_xml_cache.xml")
USPA_CACHE_FILE     = os.path.join(_BASE_DIR, "uspa_xml_cache.xml")
OTOSEMIH_CACHE_FILE = os.path.join(_BASE_DIR, "otosemih_xml_cache.xml")

KESKIN_XML_URL = (
    "https://keskinlastik.com/genel/xml/"
    "DC25E3A7-7AEE-4B89-B980-7E8B7446B390"
)
USPA_XML_URL     = "https://www.uspalastik.com/index.php?url=xml_export/uspa4"
OTOSEMIH_XML_URL = "https://www.otosemih.com.tr/outputxml/index.php?xml_service_id=4"

# Cache dosyası bu süreden eskiyse yenile (saniye)
CACHE_MAX_AGE = 50 * 60  # 50 dakika


def cache_guncelle_mi(dosya: str) -> bool:
    """Dosya yoksa veya CACHE_MAX_AGE'den eskiyse True döner."""
    if not os.path.exists(dosya):
        return True
    return (time.time() - os.path.getmtime(dosya)) > CACHE_MAX_AGE


def xml_indir(url: str, dosya: str, isim: str) -> bool:
    """URL'den XML indirir, dosyaya kaydeder. Başarılıysa True döner."""
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()

        # Rate limit kontrolü — hata XML'i kaydetme
        if b"HataMi" in resp.content and b"True" in resp.content:
            logger.warning(f"[{isim}] Rate limit — cache güncellenmedi")
            return False

        with open(dosya, "wb") as f:
            f.write(resp.content)
        logger.info(f"[{isim}] Cache güncellendi: {dosya} ({len(resp.content)} byte)")
        return True
    except Exception as e:
        logger.error(f"[{isim}] İndirme hatası: {e}")
        return False


def guncelle(force: bool = False):
    """Gerekiyorsa tüm XML'leri günceller."""
    if force or cache_guncelle_mi(KESKIN_CACHE_FILE):
        xml_indir(KESKIN_XML_URL, KESKIN_CACHE_FILE, "Keskin Lastik")
    else:
        logger.info(f"[Keskin Lastik] Cache güncel, atlandı")

    if force or cache_guncelle_mi(USPA_CACHE_FILE):
        xml_indir(USPA_XML_URL, USPA_CACHE_FILE, "USPA Lastik")
    else:
        logger.info(f"[USPA Lastik] Cache güncel, atlandı")

    if force or cache_guncelle_mi(OTOSEMIH_CACHE_FILE):
        xml_indir(OTOSEMIH_XML_URL, OTOSEMIH_CACHE_FILE, "OtoSemih")
    else:
        logger.info(f"[OtoSemih] Cache güncel, atlandı")


def keskin_xml_oku() -> bytes | None:
    """Keskin cache dosyasını okur. Yoksa None döner."""
    if os.path.exists(KESKIN_CACHE_FILE):
        with open(KESKIN_CACHE_FILE, "rb") as f:
            return f.read()
    return None


def uspa_xml_oku() -> bytes | None:
    """USPA cache dosyasını okur. Yoksa None döner."""
    if os.path.exists(USPA_CACHE_FILE):
        with open(USPA_CACHE_FILE, "rb") as f:
            return f.read()
    return None


def otosemih_xml_oku() -> bytes | None:
    """OtoSemih cache dosyasını okur. Yoksa None döner."""
    if os.path.exists(OTOSEMIH_CACHE_FILE):
        with open(OTOSEMIH_CACHE_FILE, "rb") as f:
            return f.read()
    return None


if __name__ == "__main__":
    # Scheduled task olarak çalıştırıldığında
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logger.info("XML cache güncelleme başlıyor...")
    guncelle(force=True)
    logger.info("Tamamlandı.")
