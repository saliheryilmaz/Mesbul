"""
LastSis B2B Scraper
Site: lastsis.com — 404 Not Found (site erişilemiyor)

Bu scraper devre dışı bırakıldı. Site 404 döndürüyor.
Motor.py'de credential kontrolü ile otomatik atlanır.
"""
from playwright.sync_api import Page
from .base import BaseScraper, LastikSonuc


class LastSisScraper(BaseScraper):
    TOPTANCI_ADI = "LastSis"

    def login(self, page: Page) -> bool:
        return False

    def ara(self, page: Page, ebat: str, marka: str = "") -> list[LastikSonuc]:
        return []
