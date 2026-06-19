"""
TekOturumMiddleware
───────────────────
Admin (is_staff) kullanıcılar hariç, her kullanıcının yalnızca
bir aktif oturumu olabilir.

Nasıl çalışır:
  - Giriş sırasında (GirisView.post) abonelik kaydına güncel
    session_key yazılır, eski session silinir.
  - Bu middleware her istekte:
      1. Kullanıcı giriş yapmış mı?
      2. Staff değil mi?
      3. Aboneliği var mı?
      4. Mevcut session_key, kayıtlı key ile eşleşiyor mu?
    Eşleşmiyorsa oturumu sonlandırıp giriş sayfasına yönlendirir.
"""

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.db import connection


class TekOturumMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and not request.user.is_staff
        ):
            try:
                from karsilastirma.models import Abonelik

                # DB'den taze oku — ORM cache'ini atla
                abonelik = Abonelik.objects.get(kullanici_id=request.user.pk)

                # Demo kullanıcılar tek oturum kısıtından muaf
                if abonelik.plan == "demo":
                    return self.get_response(request)

                kayitli_key = abonelik.session_key or ""
                mevcut_key  = request.session.session_key or ""

                if kayitli_key and mevcut_key and kayitli_key != mevcut_key:
                    logout(request)
                    return redirect("/?login_hata=oturum&u=")
            except Exception:
                pass

        return self.get_response(request)
