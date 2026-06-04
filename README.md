# Mesbul

<p align="center">
  <strong>Toptancı B2B portallarındaki lastik fiyatlarını tek ekranda karşılaştıran Django uygulaması.</strong>
</p>

<p align="center">
  <a href="https://www.python.org/"><img alt="Python" src="https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white"></a>
  <a href="https://www.djangoproject.com/"><img alt="Django" src="https://img.shields.io/badge/Django-Web%20Framework-092E20?style=for-the-badge&logo=django&logoColor=white"></a>
  <a href="https://github.com/saliheryilmaz/Mesbul"><img alt="Status" src="https://img.shields.io/badge/Status-Active-success?style=for-the-badge"></a>
</p>

## Genel Bakış

Mesbul, lastik bayilerinin farklı toptancı portallarındaki fiyatları tek tek kontrol etme ihtiyacını azaltmak için geliştirilmiş bir fiyat karşılaştırma uygulamasıdır. Kullanıcı; lastik ebatı, marka, mevsim ve minimum DOT bilgisiyle arama yapar. Sistem desteklenen toptancılardan verileri toplar, sonuçları fiyat bazlı sıralar ve en uygun seçenekleri tek ekranda gösterir.

Proje Django tabanlıdır ve varsayılan olarak SQLite ile çalışabilir. Ortam değişkenleri sağlandığında MySQL veritabanıyla da çalışacak şekilde yapılandırılmıştır.

## Özellikler

- Toptancı B2B portallarında tek ekrandan fiyat arama
- Paralel arama yapısı ile daha hızlı sonuç toplama
- Lastik ebadı, marka, mevsim ve minimum DOT filtreleri
- En ucuz fiyat bilgisini öne çıkarma
- Sonuçları fiyat sırasına göre listeleme
- Toptancı bazlı sonuç sayısı gösterimi
- Arama geçmişi kaydı
- Kullanıcı girişi ile korunan arama ve sonuç ekranları
- `.env` tabanlı güvenli kimlik bilgisi yönetimi
- SQLite veya MySQL ile çalışabilen veritabanı yapısı

## Teknolojiler

- Python
- Django
- Django Authentication
- SQLite / MySQL
- python-dotenv
- Requests
- BeautifulSoup tabanlı veri ayrıştırma yapıları
- HTML templates
- ThreadPoolExecutor ile paralel işleme


## Geliştirici

**Salih Eryılmaz**  
GitHub: [@saliheryilmaz](https://github.com/saliheryilmaz)
