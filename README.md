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


## Coolify / Hetzner production

Railpack build pack seçin, uygulama portunu **8000** olarak ayarlayın ve HTTPS domaininizi bağlayın. `railpack.json` aşağıdaki başlangıç komutunu tanımlar; Coolify'da Start Command override kullanıyorsanız aynı değeri girin:

```sh
python manage.py migrate && python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

### mysqlclient native sistem bağımlılıkları

`railpack.json`, build aşamasında `build-essential`, `pkg-config`, `libmariadb-dev` ve `libmariadb-dev-compat` kurar. Bu paketler mysqlclient'ın C uzantısı için derleyici, MariaDB başlıkları ve MySQL uyumlu bağlantı dosyalarını sağlar. Python 3.13 ortamını Railpack yönetmeye devam eder.

Final production image ayrıca `deploy.aptPackages` üzerinden **`libmariadb3`** kurar; bu paket `libmariadb.so.3` dosyasını sistem kütüphane dizinine yerleştirir. Yalnızca build aşamasına kurmak yeterli değildir: build ve runtime katmanları ayrıdır. `...` girdileri Railpack'in otomatik eklediği paketleri korur.

Bu değişikliği deploy ederken yeni image build edin; yalnızca eski container'ı yeniden başlatmak yeterli değildir. Coolify'da `RAILPACK_BUILD_APT_PACKAGES` veya `RAILPACK_DEPLOY_APT_PACKAGES` override'ları varsa bu paket listeleriyle uyumlu olduklarını kontrol edin. Runtime container terminalinde veritabanına bağlanmadan doğrulayabilirsiniz:

```sh
python -c "import ctypes; ctypes.CDLL('libmariadb.so.3'); import MySQLdb; print('MariaDB runtime ve MySQLdb OK')"
```

Kaynaklar: [Railpack build/runtime Apt paketleri](https://railpack.com/guides/installing-packages), [libmariadb3 dosya listesi](https://packages.debian.org/bookworm/amd64/libmariadb3/filelist).

### Coolify runtime ortam değişkenleri

- `SECRET_KEY`: güçlü, benzersiz ve deploy'lar arasında sabit bir değer.
- `DEBUG=False`, `ALLOWED_HOSTS=example.com,www.example.com`.
- `CSRF_TRUSTED_ORIGINS=https://example.com,https://www.example.com`.
- `DJANGO_BEHIND_PROXY=True`: yalnızca Coolify proxy'si arkasında kullanın; proxy gelen `X-Forwarded-Proto` başlığını güvenilir şekilde ayarlamalı ve port 8000 internete doğrudan açılmamalıdır.
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`: kalıcı MySQL sunucusunun bilgileri (port 3306). Mevcut veritabanı seçim davranışı korunur: `DB_PASSWORD` boşsa SQLite kullanılır. Production için MySQL kullanın; SQLite seçilirse `db.sqlite3` dosyasının container yenilenmesinde kaybolmaması için kalıcı depolama gerekir.
- Mevcut XML URL değişkenlerinizi ve e-posta ayarlarınızı da Coolify'a taşıyın; `.env` dosyasını repoya eklemeyin.

`migrate`, XML servislerinin kullandığı `django_cache` tablosunu da oluşturur; mevcut tabloya ve verilere dokunmaz. `collectstatic`, dosyaları `staticfiles/` altında toplar ve WhiteNoise bunları Gunicorn üzerinden sunar. XML servis kodları değiştirilmemiştir. Gunicorn timeout değeri, 40 saniyeye kadar bekleyebilen XML servisleri için 120 saniyedir.

Playwright production bağımlılığı değildir. Eski keşif betikleri için `pip install -r requirements-dev.txt` ve `python -m playwright install chromium` kullanabilirsiniz.

Kaynaklar: [Railpack yapılandırması](https://railpack.com/config/file), [Django ile WhiteNoise](https://whitenoise.readthedocs.io/en/stable/django.html).

## Geliştirici

**Salih Eryılmaz**  
GitHub: [@saliheryilmaz](https://github.com/saliheryilmaz)
