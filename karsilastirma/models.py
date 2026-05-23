from django.db import models


class AramaGecmisi(models.Model):
    ebat          = models.CharField(max_length=30)
    marka         = models.CharField(max_length=50, blank=True)
    mevsim        = models.CharField(max_length=20, blank=True)
    sonuc_sayisi  = models.IntegerField(default=0)
    arama_zamani  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-arama_zamani"]

    def __str__(self):
        return f"{self.ebat} {self.marka} ({self.arama_zamani:%d.%m.%Y %H:%M})"
