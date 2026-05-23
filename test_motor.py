import sys, logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
sys.path.insert(0, '.')

from karsilastirma.scrapers.motor import fiyat_topla

print("=== fiyat_topla testi ===")
sonuclar = fiyat_topla("205/55R16")

from collections import Counter
toptancilar = Counter(s.toptanci for s in sonuclar)
print(f"\nToplam: {len(sonuclar)} ürün")
print("Toptancı bazlı:")
for t, n in sorted(toptancilar.items(), key=lambda x: -x[1]):
    print(f"  {t}: {n}")
