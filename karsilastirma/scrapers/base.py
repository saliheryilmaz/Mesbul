from dataclasses import dataclass
import re

__all__ = ["LastikSonuc", "BaseScraper", "_ebat_eslesir"]



def _ebat_parcala(ebat: str) -> tuple[str, str, str] | None:
    """Return width, aspect and rim parts from a passenger tyre size."""
    m = re.search(r"(\d{3})\D*(\d{2})\D*(\d{2,3})", ebat or "")
    if m:
        return m.group(1), m.group(2), m.group(3)

    digits = re.sub(r"[^0-9]", "", ebat or "")
    if len(digits) >= 7:
        cap = digits[5:7]
        if len(digits) >= 8 and digits[5] in "123":
            cap = digits[5:8]
        return digits[:3], digits[3:5], cap

    return None


def _normalize_ebat_for_match(ebat: str) -> str:
    """Matcher içindeki varyasyonları azaltmak için ebat formatını normalize eder."""
    if not ebat:
        return ""

    e = ebat.strip()
    e = re.sub(r"\s+", "", e)

    # 205/55r16 -> 205/55R16
    e = re.sub(r"(?i)r(\d)", r"R\1", e)

    # 2055516 -> 205/55R16 (7-8 rakam olasılığı)
    m = re.match(r"^(\d{3})(\d{2})(\d{2,3})$", e)
    if m:
        e = f"{m.group(1)}/{m.group(2)}R{m.group(3)}"

    return e


def _ebat_eslesir(ebat_f: str, urun_metni: str) -> bool:
    """Check whether a product row contains the requested tyre size.

    Accepts common supplier variants such as:
    205/55R16, 205/55 R16, 205/55ZR16, 205/55/16,
    205 55 16 and 2055516.
    """


    ebat_f = _normalize_ebat_for_match(ebat_f)

    if not ebat_f:
        return True

    parts = _ebat_parcala(ebat_f)
    if not parts:
        ebat_rakam = re.sub(r"[^0-9]", "", ebat_f)
        urun_rakam = re.sub(r"[^0-9]", "", urun_metni or "")
        return bool(ebat_rakam and ebat_rakam in urun_rakam)

    genislik, yanak, cap = parts
    text = urun_metni or ""
    ebat_rakam = f"{genislik}{yanak}{cap}"

    patterns = [
        # 205/55R16, 205/55 R16, 205/55ZR16, 205/55/16, 205/55 16
        rf"(?<!\d){genislik}\s*[/\\-]\s*{yanak}\s*(?:[/\\-]?\s*(?:Z?R)?\s*){cap}\s*[Cc]?(?![\d.,])",
        # 205 55 R16, 205 55R16, 205 55 16
        rf"(?<!\d){genislik}\s+{yanak}\s*(?:Z?R\s*)?{cap}\s*[Cc]?(?![\d.,])",
        # 2055516, 2055516C, 205551691V
        rf"(?<!\d){ebat_rakam}(?:[Cc]|(?=\d{{2,3}}[A-Z]?\b)|\b)",
    ]
    if any(re.search(pat, text, re.IGNORECASE) for pat in patterns):
        return True

    # Last fallback for supplier stock codes that encode the exact size.
    urun_rakam = re.sub(r"[^0-9]", "", text)
    return bool(ebat_rakam and ebat_rakam in urun_rakam)


@dataclass
class LastikSonuc:
    toptanci: str
    marka: str
    model: str
    ebat: str
    mevsim: str
    dot: str
    fiyat: float
    para_birimi: str
    stok: str
    site_url: str

    @property
    def fiyat_str(self) -> str:
        """Template'de kullanilmak uzere formatlanmiş fiyat."""
        return f"{self.fiyat:,.2f} {self.para_birimi}".replace(",", "X").replace(".", ",").replace("X", ".")


class BaseScraper:
    TOPTANCI_ADI = "Bilinmeyen"

    def __init__(self, kullanici: str, sifre: str):
        self.kullanici = kullanici
        self.sifre = sifre

    def login(self, page) -> bool:
        """Giriş işlemini yapar, basarılıysa True doner."""
        raise NotImplementedError

    def ara(self, page, ebat: str, marka: str = "") -> list[LastikSonuc]:
        """Arama yapar ve LastikSonuc listesi doner."""
        raise NotImplementedError

    def sonuc_olustur(self, **kwargs) -> LastikSonuc:
        """Sinifa ait toptanci adini ekleyerek sonuc nesnesi olusturur."""
        kwargs["toptanci"] = self.TOPTANCI_ADI
        return LastikSonuc(**kwargs)
