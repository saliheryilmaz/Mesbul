import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import logging
logging.basicConfig(level=logging.INFO)

from karsilastirma.scrapers.tiryakiler import TiryakilerScraper
from karsilastirma.scrapers.mollaoglu import MollaogluScraper
from playwright.sync_api import sync_playwright

print('Testing Tiryakiler')
scraper = TiryakilerScraper('info@meslas.com', '12345')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    print('Tiryakiler Login denemesi...')
    res = scraper.login(page)
    print('Tiryakiler Login:', res)
    
    if res:
        print('Tiryakiler Arama denemesi...')
        sonuclar = scraper.ara(page, '205/55R16')
        print(f'Tiryakiler Arama sonucu: {len(sonuclar)} ürün')
        for s in sonuclar[:2]:
            print(s)
            
    browser.close()
