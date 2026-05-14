import os
import django
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import logging
logging.basicConfig(level=logging.INFO)

from karsilastirma.scrapers.cakiroglu import CakirogluScraper
from karsilastirma.scrapers.tiryakiler import TiryakilerScraper
from karsilastirma.scrapers.mollaoglu import MollaogluScraper
from karsilastirma.scrapers.netlastik import NetLastikScraper
from karsilastirma.scrapers.uspa import UspaScraper
from karsilastirma.scrapers.lastsis import LastSisScraper

from playwright.sync_api import sync_playwright

SCRAPERS = [
    (CakirogluScraper, os.getenv("CAKIROGLU_KULLANICI", ""), os.getenv("CAKIROGLU_SIFRE", "")),
    (TiryakilerScraper, os.getenv("TIRYAKILER_KULLANICI", ""), os.getenv("TIRYAKILER_SIFRE", "")),
    (MollaogluScraper, os.getenv("MOLLAOGLU_KULLANICI", ""), os.getenv("MOLLAOGLU_SIFRE", "")),
    (NetLastikScraper, os.getenv("NETLASTIK_KULLANICI", ""), os.getenv("NETLASTIK_SIFRE", "")),
    (UspaScraper, os.getenv("USPA_KULLANICI", ""), os.getenv("USPA_SIFRE", "")),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    
    for scraper_cls, kullanici, sifre in SCRAPERS:
        print(f"\n--- Testing {scraper_cls.TOPTANCI_ADI} ---")
        if not kullanici or not sifre:
            print(f"Skipping {scraper_cls.TOPTANCI_ADI} due to missing credentials.")
            continue
            
        scraper = scraper_cls(kullanici, sifre)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            res = scraper.login(page)
            print(f"[{scraper.TOPTANCI_ADI}] Login result: {res}")
            if res:
                sonuclar = scraper.ara(page, '205/55R16')
                print(f"[{scraper.TOPTANCI_ADI}] Search found {len(sonuclar)} results")
        except Exception as e:
            print(f"[{scraper.TOPTANCI_ADI}] Exception: {e}")
        finally:
            context.close()
            
    browser.close()
