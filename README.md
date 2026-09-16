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

`railpack.json`, Railpack **v0.23.0** için build aşamasında yalnızca `build-essential`, `default-libmysqlclient-dev` ve `pkg-config` ister. Debian Bookworm'da `default-libmysqlclient-dev`, gereken MariaDB geliştirme paketlerini bağımlılık olarak getirir; ayrıca `libmariadb-dev` veya `libmariadb-dev-compat` listelenmez. Python 3.13 ve ona ait başlık dosyalarını Railpack'in Python kurulumu sağlar; ayrıca sistem Python'u kurulmaz.

Final production image `deploy.aptPackages: ["libmariadb3"]` üzerinden yalnızca gereken MariaDB runtime paketini ister; bu paket `libmariadb.so.3` dosyasını sistem kütüphane dizinine yerleştirir. Yalnızca build aşamasına kurmak yeterli değildir: build ve runtime katmanları ayrıdır. Her iki listede de `...` kullanılmaz. Runtime listesi otomatik `default-mysql-client` seçimini değiştirir; mysqlclient için MySQL komut satırı istemcisinin kurulması gerekmez. Apt, bu paketlerin zorunlu bağımlılıklarını kendisi çözer.

Bu değişikliği deploy ederken yeni image build edin; yalnızca eski container'ı yeniden başlatmak yeterli değildir. Coolify'da eski `RAILPACK_BUILD_APT_PACKAGES` veya `RAILPACK_DEPLOY_APT_PACKAGES` override'larını kaldırıp repodaki yapılandırmayı kullanın. Build logunda `build-essential default-libmysqlclient-dev pkg-config`, runtime paket adımında `libmariadb3` beklenir. Runtime container terminalinde veritabanına bağlanmadan doğrulayabilirsiniz:

```sh
python -c "import ctypes; ctypes.CDLL('libmariadb.so.3'); import MySQLdb; print('MariaDB runtime ve MySQLdb OK')"
```

Kaynaklar: [Railpack v0.23.0 runtime yapılandırması](https://github.com/railwayapp/railpack/blob/v0.23.0/core/generate/context.go), [Debian Bookworm geliştirme paketi](https://packages.debian.org/bookworm/default-libmysqlclient-dev), [libmariadb3 dosya listesi](https://packages.debian.org/bookworm/amd64/libmariadb3/filelist).

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
