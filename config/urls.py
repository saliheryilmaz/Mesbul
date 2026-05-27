from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from karsilastirma.views import GirisView, CikisView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('giris/', GirisView.as_view(), name='giris'),
    path('cikis/', CikisView.as_view(), name='cikis'),
    path('', include('karsilastirma.urls')),
]
