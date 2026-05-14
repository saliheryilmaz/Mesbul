import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from karsilastirma.scrapers.motor import fiyat_topla

if __name__ == '__main__':
    print("Testing fiyat_topla...")
    try:
        sonuclar = fiyat_topla(ebat="205/55R16")
        print(f"Total results: {len(sonuclar)}")
    except Exception as e:
        print(f"Error: {e}")
