# TODO - Lastik Ebat Birleştirici Proje

## 1) Analiz / Tespit
- [x] Repoirdekü scraper akışını okudum: `views.py`, `motor.py`, `base.py`, `otosemih.py`, `ek_toptancilar.py`.
- [x] Hangi toptancılarda 0 sonuç döndüğünü motor loglarında yakalamaya başladım.

## 2) Kod Düzeltmeleri (öncelik)
- [x] `motor.py` içine debug özet: credential eksik atlanan toptancılar + 0 sonuç dönenler.
- [x] `base.py` içine ebat matcher normalizasyonu ekledim (`_normalize_ebat_for_match`).
- [x] `ek_toptancilar.py` içinde `GenericWebScraper` default pagination/scroll davranışını iyileştirdim.

## 3) Test
- [ ] Tek bir ebat ile (örn 205/55R16) local test koş.
- [ ] Loglardan eksik kalan toptancıları tespit et.
- [ ] Gerekirse sadece o toptancıların selector/pagination logic’ini düzelt.

