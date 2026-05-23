import sys; sys.path.insert(0,'.')
from karsilastirma.scrapers.otosemih import OtoSemihScraper
s = OtoSemihScraper('','')
r = s.ara(None, '205/55R16')
print(f"Toplam: {len(r)}")
for x in r:
    print(f"  mevsim={x.mevsim} | {x.model[:60]}")
