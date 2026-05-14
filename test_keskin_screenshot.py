import os
import time
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

LOGIN_URL = "https://keskinlastik.com/Giris"
kullanici = os.getenv("KESKIN_MUSTERI_KOD")
sifre = os.getenv("KESKIN_SIFRE")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = context.new_page()
    try:
        print("Navigating to", LOGIN_URL)
        page.goto(LOGIN_URL, timeout=30000)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2)
        
        inputs = page.query_selector_all("input")
        user_input = next((el for el in inputs if el.get_attribute("placeholder") == "Müşteri Kodunuz"), None)
        pass_input = next((el for el in inputs if el.get_attribute("placeholder") == "Şifreniz"), None)
        
        if user_input and pass_input:
            user_input.fill(kullanici)
            pass_input.fill(sifre)
            print("Filled inputs based on placeholder")
        else:
            page.fill('input[name="UserName"]', kullanici)
            page.fill('input[name="Password"]', sifre)
            print("Filled inputs based on name")
            
        page.screenshot(path="before_login.png")
        page.keyboard.press("Enter")
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        time.sleep(3)
        page.screenshot(path="after_login.png")
        
        if "Giris" not in page.url:
            print("Login success, url:", page.url)
        else:
            print("Login failed, url:", page.url)
    except Exception as e:
        print("Error:", e)
        page.screenshot(path="error.png")
    finally:
        browser.close()
