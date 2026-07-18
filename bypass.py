import os
import sys
import time
import re
import email.utils
import json
from bs4 import BeautifulSoup
from curl_cffi import requests

# --- Configuration & Secrets ---
BROWSER_TOKEN = "3f132a0c3d414a8fb4a02775f61b6a04|7e902b4485babe129208d474402e921516f2f0d8b2b98cd23fb8a2e226bef6d3"
VERCEL_API_URL = os.environ.get("VERCEL_API_URL")
INTERNAL_API_SECRET = os.environ.get("INTERNAL_API_SECRET")

# Cloudflare WARP local proxy (set up by the GitHub Action)
PROXIES = {
    "http": "socks5://127.0.0.1:40000",
    "https": "socks5://127.0.0.1:40000"
}

def log(msg):
    print(msg, flush=True)

def run_scraper():
    session = requests.Session(impersonate="chrome", proxies=PROXIES)

    log("> [STEP 1] Fetching ad token from scloudx.lol...")
    temp_ad_code = get_temp_ad_code(session)
    if not temp_ad_code:
        log("[ERROR] Failed to retrieve temp_ad_code.")
        sys.exit(1)
    log(f"> Extracted Code: {temp_ad_code}")
    time.sleep(2)

    log("> [STEP 2] Fetching ad_form_data...")
    ad_form_data = get_temp_ad_string(session, temp_ad_code)
    if not ad_form_data:
        log("[ERROR] Failed to retrieve ad_form_data.")
        sys.exit(1)
    log(f"> Data Found: {ad_form_data[:30]}...")

    log("> [WAIT] Mandatory 90s cooldown...")
    time.sleep(90)
    log("> Timer bypassed!")

    log("> [STEP 3] Fetching verify URL from links/go...")
    verify_url = get_verify_url(session, temp_ad_code, ad_form_data)
    if not verify_url:
        log("[ERROR] Failed to retrieve verify_url.")
        sys.exit(1)

    log("> [STEP 4] Obtaining ad_verified clearance cookie...")
    ad_verified_token, expires_at = submit_verify_url(session, verify_url)
    if not ad_verified_token:
        log("[ERROR] Failed to extract 'ad_verified' cookie.")
        sys.exit(1)
        
    log(f"> [SUCCESS] Final Token: {ad_verified_token[:25]}...")
    log(f"> [SUCCESS] Valid until: {expires_at}")

    # --- STEP 5: Handoff to Vercel API ---
    log("> [STEP 5] Handing off token to Next.js API...")
    handoff_url = f"{VERCEL_API_URL}/api/internal/token-sync"
    
    # Standard requests library is fine here, no need to impersonate Chrome to talk to our own API
    import requests as std_requests
    response = std_requests.post(
        handoff_url,
        headers={
            "Authorization": f"Bearer {INTERNAL_API_SECRET}",
            "Content-Type": "application/json"
        },
        json={
            "token": ad_verified_token,
            "expires_at": expires_at
        }
    )

    if response.status_code == 200:
        log("> [SUCCESS] Token safely ingested by Next.js.")
    else:
        log(f"> [ERROR] Vercel API rejected the payload: {response.status_code} - {response.text}")
        sys.exit(1)

# --- HOLY HEADER IMPLEMENTATIONS ---

def get_temp_ad_code(session):
    url = "https://scloudx.lol/get-search-token"
    headers = {
        "Cookie": f"browser_token={BROWSER_TOKEN};",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://scloudx.lol/",
        "Origin": "https://scloudx.lol",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Te": "trailers",
    }
    response = session.post(url, headers=headers, data={"search_query": "anything+at+all"})
    if response.status_code == 200:
        match = re.search(r'https://(?:tpi\.li|lnbz\.la)/([a-zA-Z0-9]+)', response.text)
        if match: return match.group(1)
    return None

def get_temp_ad_string(session, temp_ad_code):
    url_tpi = f"https://tpi.li/{temp_ad_code}"
    headers_tpi = {
        "Cache-Control": "max-age=0",
        "Origin": "https://devsoftwr.com",
        "Content-Type": "application/x-www-form-urlencoded",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
        "Referer": "https://devsoftwr.com/",
        "Priority": "u=0, i",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    }
    try:
        response = session.post(url_tpi, headers=headers_tpi, allow_redirects=False)
        if response.status_code in [200, 302]:
            soup = BeautifulSoup(response.text, 'html.parser')
            input_tag = soup.find('input', {'name': 'ad_form_data'})
            if input_tag and input_tag.get('value'): 
                return input_tag['value']
    except Exception:
        pass

    url_lnbz = f"https://lnbz.la/{temp_ad_code}"
    headers_lnbz = {
        "Cache-Control": "max-age=0",
        "Origin": "https://avnsgames.com",
        "Content-Type": "application/x-www-form-urlencoded",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
        "Referer": "https://avnsgames.com/",
        "Priority": "u=0, i",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    }
    try:
        response = session.post(url_lnbz, headers=headers_lnbz, allow_redirects=False)
        if response.status_code in [200, 302]:
            soup = BeautifulSoup(response.text, 'html.parser')
            input_tag = soup.find('input', {'name': 'ad_form_data'})
            if input_tag and input_tag.get('value'): 
                return input_tag['value']
    except Exception:
        pass
    return None

def get_verify_url(session, temp_ad_code, ad_form_data):
    url_tpi = "https://tpi.li/links/go"
    headers_tpi = {
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://tpi.li",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": f"https://tpi.li/{temp_ad_code}",
        "Priority": "u=1, i",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    }
    try:
        response = session.post(url_tpi, headers=headers_tpi, data={"_method": "POST", "ad_form_data": ad_form_data})
        if response.status_code == 200:
            url_result = response.json().get("url", "").replace("\\", "")
            if url_result: return url_result
    except Exception:
        pass
        
    url_lnbz = "https://lnbz.la/links/go"
    headers_lnbz = {
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://lnbz.la",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": f"https://lnbz.la/{temp_ad_code}",
        "Priority": "u=1, i",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    }
    try:
        response = session.post(url_lnbz, headers=headers_lnbz, data={"_method": "POST", "ad_form_data": ad_form_data})
        if response.status_code == 200:
            url_result = response.json().get("url", "").replace("\\", "")
            if url_result: return url_result
    except Exception:
        pass
    return None

def submit_verify_url(session, verify_url):
    headers = {
        "Cookie": f"browser_token={BROWSER_TOKEN}",
        "Upgrade-Insecure-Requests": "1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
        "Referer": "https://tpi.li/",
        "Accept-Encoding": "gzip, deflate, br",
        "Priority": "u=0, i",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Accept-Language": "en-US,en;q=0.9",
    }
    response = session.get(verify_url, headers=headers, allow_redirects=False)
    cookie_header = response.headers.get("Set-Cookie", "")
    
    ad_verified, expires_at = None, None
    if "ad_verified=" in cookie_header:
        segment = cookie_header[cookie_header.find("ad_verified="):]
        v_match = re.search(r'ad_verified=([^;]+)', segment)
        e_match = re.search(r'Expires=([^;]+)', segment, re.IGNORECASE)
        if v_match: ad_verified = v_match.group(1)
        if e_match: expires_at = e_match.group(1)
            
    return ad_verified, expires_at

if __name__ == "__main__":
    if not VERCEL_API_URL or not INTERNAL_API_SECRET:
        log("[FATAL] Missing required environment variables (VERCEL_API_URL, INTERNAL_API_SECRET)")
        sys.exit(1)
    run_scraper()
