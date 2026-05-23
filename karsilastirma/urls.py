from django.urls import path
from .views import AramaView, SonuclarView

urlpatterns = [
    path("",          AramaView.as_view(),    name="arama"),
    path("sonuclar/", SonuclarView.as_view(), name="sonuclar"),
]
