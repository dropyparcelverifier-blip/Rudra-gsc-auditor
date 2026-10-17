#!/usr/bin/env python3
"""
Rudra Retail GSC Auditor v3.1 — Production-Ready (33 checks, 17 coverage states)
==========================================================================
Local Flask app. Open http://localhost:5000 in your browser.
Paste product URLs -> live audit -> interactive report.

Pre-flight (20 checks) works without credentials.
Full audit (33 checks) requires GSC API credentials.

Production improvements over v3.0:
- Comprehensive error handling with @handle_errors decorator
- Multithreading for batch operations (ThreadPoolExecutor)
- Robust logging (file + console)
- Retry logic for GSC API calls
- Input validation & sanitization
- Timeout on all urllib requests
- Graceful degradation & shutdown
- Environment variable configuration

Docs verified against official Google Search Console API:
  https://developers.google.com/webmaster-tools/v1/urlInspection.index/inspect
  https://developers.google.com/webmaster-tools/v1/searchanalytics/query
  https://developers.google.com/webmaster-tools/limits
"""

import os
import re
import json
import time
import logging
import datetime
from datetime import timezone, timedelta
import threading
import html as htmllib
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import wraps

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template_string, request, jsonify

# ─────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────
Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/auditor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONSTANTS & CONFIG (env-var overridable)
# ─────────────────────────────────────────────
CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
SITE_URL         = os.getenv("GOOGLE_SITE_URL", "sc-domain:YOUR_DOMAIN_HERE")
BRAND_DOMAIN     = os.getenv("BRAND_DOMAIN", "YOUR_DOMAIN_HERE")
BRAND_NAME       = os.getenv("BRAND_NAME", "Rudra Retail")
PORT             = int(os.getenv("FLASK_PORT", "5001"))
DELAY            = float(os.getenv("GOOGLE_RATE_LIMIT_DELAY", "1.0"))
MAX_WORKERS      = int(os.getenv("MAX_WORKERS", "2"))
REQUEST_TIMEOUT  = int(os.getenv("REQUEST_TIMEOUT", "15"))
MAX_BATCH_SIZE   = 50
MAX_URL_LENGTH   = 2000

# GSC API daily quota (URL Inspection: 2000/day, Search Analytics: 25000/day)
GSC_DAILY_INSPECT_LIMIT = int(os.getenv("GSC_DAILY_INSPECT_LIMIT", "1800"))
GSC_DAILY_SA_LIMIT      = int(os.getenv("GSC_DAILY_SA_LIMIT", "20000"))

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"

PT_OFFSET = timezone(timedelta(hours=-7))

def _today_pt():
    """Current date in Pacific Time — matches Google's quota reset."""
    return datetime.datetime.now(PT_OFFSET).strftime("%Y-%m-%d")


# ─────────────────────────────────────────────
# GSC RATE LIMITER (Google API guidelines)
# ─────────────────────────────────────────────
class GSCRateLimiter:
    """Track daily quota and enforce per-request delays for GSC APIs."""
    def __init__(self):
        self._lock = threading.Lock()
        self._inspect_count = 0
        self._sa_count = 0
        self._last_call = 0.0
        self._reset_date = _today_pt()

    def _maybe_reset(self):
        today = _today_pt()
        if today > self._reset_date:
            self._inspect_count = 0
            self._sa_count = 0
            self._reset_date = today

    def wait_and_track(self, api_type: str = "inspect") -> bool:
        """Wait for rate limit, track quota. Returns False if daily limit hit."""
        sleep_time = 0
        with self._lock:
            self._maybe_reset()
            if api_type == "inspect" and self._inspect_count >= GSC_DAILY_INSPECT_LIMIT:
                return False
            if api_type == "sa" and self._sa_count >= GSC_DAILY_SA_LIMIT:
                return False
            elapsed = time.time() - self._last_call
            if elapsed < DELAY:
                sleep_time = DELAY - elapsed
            self._last_call = time.time() + sleep_time
            if api_type == "inspect":
                self._inspect_count += 1
            else:
                self._sa_count += 1
        if sleep_time > 0:
            time.sleep(sleep_time)
        return True

    @property
    def usage(self) -> Dict[str, Any]:
        with self._lock:
            self._maybe_reset()
            return {
                "inspect": {"used": self._inspect_count, "limit": GSC_DAILY_INSPECT_LIMIT},
                "search_analytics": {"used": self._sa_count, "limit": GSC_DAILY_SA_LIMIT},
                "date": self._reset_date,
            }

gsc_limiter = GSCRateLimiter()


# ─────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────
@dataclass
class AuditResult:
    url: str
    status: str  # "success", "error"
    error: Optional[str] = None
    pf: Optional[Dict] = None
    gsc: Optional[Dict] = None
    sa: Optional[Dict] = None
    actions: Optional[List] = None
    score: int = 0

GSC_OFFLINE_STUB = {
    "verdict": "-", "coverage": "Connect GSC to check", "robots": "-", "indexing": "-",
    "fetch": "-", "last_crawl": "-", "g_canonical": "", "u_canonical": "", "crawled_as": "-",
    "in_sitemap": False, "referring": [], "rich_verdict": "-", "rich_issues": [], "rich_types": [],
    "link": "", "error": "Not connected", "skipped": True,
}
SA_OFFLINE_STUB = {
    "clicks": 0, "impr": 0, "pos": 0, "ctr": 0, "queries": [], "quick_wins": [],
    "mobile_pct": 0, "appearances": [], "error": "Not connected", "skipped": True,
}

# ─────────────────────────────────────────────
# FLASK APP SETUP
# ─────────────────────────────────────────────
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB upload limit


@app.before_request
def handle_preflight():
    if request.method == 'OPTIONS':
        resp = app.make_default_options_response()
        origin = request.headers.get('Origin', '')
        if origin.startswith('chrome-extension://') or origin.startswith('http://localhost') or origin.startswith('http://127.0.0.1') or not origin:
            resp.headers['Access-Control-Allow-Origin'] = origin or '*'
            resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        return resp

@app.after_request
def add_cors_headers(response):
    origin = request.headers.get('Origin', '')
    if origin.startswith('chrome-extension://') or origin.startswith('http://localhost') or origin.startswith('http://127.0.0.1') or not origin:
        response.headers['Access-Control-Allow-Origin'] = origin or '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

_creds = None
_sc_v1 = None
_wmt_v3 = None

# ─────────────────────────────────────────────
# ERROR HANDLING DECORATOR
# ─────────────────────────────────────────────
def handle_errors(f):
    """Decorator: catch all exceptions and return JSON error response."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            logger.warning(f"Validation error in {f.__name__}: {e}")
            return jsonify({"error": f"Invalid input: {str(e)}"}), 400
        except TimeoutError as e:
            logger.error(f"Timeout in {f.__name__}: {e}")
            return jsonify({"error": "Request timed out. Try again or reduce batch size."}), 408
        except Exception as e:
            logger.exception(f"Unexpected error in {f.__name__}")
            return jsonify({"error": f"Server error: {str(e)[:200]}"}), 500
    return wrapper

# ─────────────────────────────────────────────
# INPUT VALIDATION
# ─────────────────────────────────────────────
def validate_url(url: str) -> Tuple[bool, str]:
    """Validate URL format and configured domain."""
    if not url:
        return False, "URL is empty"
    if len(url) > MAX_URL_LENGTH:
        return False, f"URL too long (max {MAX_URL_LENGTH} chars)"
    if not url.startswith("https://"):
        return False, "Must use HTTPS"
    if BRAND_DOMAIN not in url:
        return False, f"Must be a {BRAND_DOMAIN} URL"
    try:
        urllib.parse.urlparse(url)
        return True, ""
    except Exception as e:
        return False, f"Invalid URL format: {str(e)}"

def validate_urls(urls: List[str]) -> Tuple[List[str], List[str]]:
    """Validate batch of URLs. Return (valid, errors)."""
    valid = []
    errors = []
    if not urls:
        errors.append("No URLs provided")
        return valid, errors
    if len(urls) > MAX_BATCH_SIZE:
        errors.append(f"Too many URLs (max {MAX_BATCH_SIZE})")
        return valid, errors
    for i, url in enumerate(urls):
        url = url.strip()
        if not url:
            continue
        is_valid, msg = validate_url(url)
        if is_valid:
            valid.append(url)
        else:
            errors.append(f"URL {i+1}: {msg}")
    return valid, errors

# ─────────────────────────────────────────────
# GOOGLE AUTH (improved error handling)
# ─────────────────────────────────────────────
def _detect_credential_type(filepath: str) -> str:
    """Detect if credentials file is a service account key or OAuth client ID."""
    try:
        with open(filepath) as f:
            data = json.load(f)
        if data.get("type") == "service_account":
            return "service_account"
        if "installed" in data or "web" in data:
            return "oauth"
        return "unknown"
    except Exception:
        return "unknown"


def init_google() -> Tuple[bool, str]:
    """
    Initialize Google API clients.
    Supports both Service Account (no login) and OAuth (browser login).
    Returns: (success, message)
    """
    global _creds, _sc_v1, _wmt_v3

    try:
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError as e:
        msg = f"Missing Google packages: {str(e)}. pip install google-auth google-auth-oauthlib google-api-python-client"
        logger.error(msg)
        return False, msg

    creds = None

    try:
        # Check what type of credentials file we have
        if not os.path.exists(CREDENTIALS_FILE):
            return False, f"{CREDENTIALS_FILE} not found. Download from Google Cloud Console."

        cred_type = _detect_credential_type(CREDENTIALS_FILE)

        # ── Service Account (no login needed) ──
        if cred_type == "service_account":
            try:
                from google.oauth2 import service_account
                creds = service_account.Credentials.from_service_account_file(
                    CREDENTIALS_FILE, scopes=SCOPES
                )
                logger.info("Using Service Account credentials (no login required)")
            except Exception as e:
                return False, f"Service account auth failed: {str(e)}"

        # ── OAuth Client (browser login) ──
        else:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow

            # Try to load cached token
            if os.path.exists("token.json"):
                try:
                    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
                except Exception as e:
                    logger.warning(f"Cached token invalid: {e}. Will re-authenticate.")

            # Refresh or re-auth if needed
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                    except Exception as e:
                        logger.warning(f"Token refresh failed: {e}. Need re-auth.")
                        creds = None

                if not creds:
                    try:
                        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                        creds = flow.run_local_server(port=8090)
                    except Exception as e:
                        return False, f"OAuth flow failed: {str(e)}"

            # Save token for next time
            try:
                with open("token.json", "w") as f:
                    f.write(creds.to_json())
            except Exception as e:
                logger.warning(f"Could not save token: {e}")

        # Build services
        try:
            _creds = creds
            _sc_v1 = build("searchconsole", "v1", credentials=creds)
            _wmt_v3 = build("webmasters", "v3", credentials=creds)
            logger.info("Google Auth OK")
            return True, "Connected to GSC"
        except Exception as e:
            return False, f"Failed to build API services: {str(e)}"

    except Exception as e:
        logger.exception("Unexpected error in init_google")
        return False, f"Unexpected error: {str(e)}"


# =============================================
# STAGE 1 -- PRE-FLIGHT (no API, 20+ checks)
# =============================================
def preflight(url: str, timeout: int = REQUEST_TIMEOUT) -> Dict[str, Any]:
    r = {"url": url, "http_status": None, "noindex": False, "canonical_self": True,
         "canonical_url": "", "title": None, "title_len": 0, "desc": None, "desc_len": 0,
         "h1_count": 0,
         # Product JSON-LD
         "has_product_jsonld": False, "product_jsonld_count": 0,
         "has_aggregate_rating": False,
         "gtin": None, "brand": None, "brand_unknown": False,
         "has_price": False, "price_currency": None, "has_availability": False,
         "has_image_in_schema": False, "offers_url_match": True,
         "faq_count": 0, "return_days": None,
         # BreadcrumbList
         "has_breadcrumb": False,
         # Images
         "img_count": 0, "img_no_alt": 0, "has_lazy_load": False,
         # OG tags
         "has_og_title": False, "has_og_image": False, "has_og_desc": False,
         # Content
         "desc_word_count": 0,
         # Links
         "internal_links": 0,
         # Page
         "page_kb": 0,
         "issues": [], "warnings": []}

    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            r["http_status"] = resp.status
            body = resp.read().decode("utf-8", errors="ignore")
        r["page_kb"] = len(body) // 1024
    except urllib.error.HTTPError as e:
        r["http_status"] = e.code
        r["issues"].append(f"HTTP {e.code}")
        return r
    except urllib.error.URLError as e:
        r["http_status"] = 0
        r["issues"].append(f"Connection error: {str(e)[:100]}")
        return r
    except Exception as e:
        r["http_status"] = 0
        r["issues"].append(f"Fetch error: {e}")
        logger.debug(f"Preflight fetch error for {url}: {e}")
        return r

    # -- 1. noindex --
    try:
        rm = re.search(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']+)', body, re.I)
        if rm and "noindex" in rm.group(1).lower():
            r["noindex"] = True
            r["issues"].append("NOINDEX tag -- blocked from Google")
    except Exception as e:
        logger.debug(f"Error checking noindex: {e}")

    # -- 2. canonical --
    try:
        cm = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', body, re.I)
        if cm:
            r["canonical_url"] = cm.group(1)
            if cm.group(1).rstrip("/") != url.rstrip("/").split("?")[0]:
                r["canonical_self"] = False
                r["warnings"].append(f"Canonical -> {cm.group(1)}")
    except Exception as e:
        logger.debug(f"Error checking canonical: {e}")

    # -- 3. title --
    try:
        tm = re.search(r"<title>(.*?)</title>", body, re.S)
        if tm:
            raw = htmllib.unescape(re.sub(r"<[^>]+>", "", tm.group(1)).strip())
            core = re.sub(r"\s*[--|-]\s*(" + re.escape(BRAND_NAME) + r"|" + re.escape(BRAND_DOMAIN) + r").*$", "", raw, flags=re.I).strip()
            r["title"] = core
            r["title_len"] = len(core)
            if len(core) > 60:
                r["warnings"].append(f"Title {len(core)} chars (<=60 ideal)")
        else:
            r["issues"].append("Title missing")
    except Exception as e:
        logger.debug(f"Error checking title: {e}")

    # -- 4. meta description --
    try:
        dm = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)', body, re.I)
        if dm:
            r["desc"] = dm.group(1)[:160]
            r["desc_len"] = len(dm.group(1))
            if r["desc_len"] < 120:
                r["warnings"].append(f"Meta desc short ({r['desc_len']} chars)")
        else:
            r["warnings"].append("Meta description missing")
    except Exception as e:
        logger.debug(f"Error checking description: {e}")

    # -- 5. H1 --
    try:
        h1s = re.findall(r"<h1[^>]*>.*?</h1>", body, re.S)
        r["h1_count"] = len(h1s)
        if len(h1s) != 1:
            r["warnings"].append(f"H1 count: {len(h1s)} (should be 1)")
    except Exception as e:
        logger.debug(f"Error checking H1: {e}")

    # -- 6-8. Open Graph --
    try:
        r["has_og_title"] = bool(re.search(r'<meta[^>]+property=["\']og:title["\']', body, re.I))
        r["has_og_image"] = bool(re.search(r'<meta[^>]+property=["\']og:image["\']', body, re.I))
        r["has_og_desc"]  = bool(re.search(r'<meta[^>]+property=["\']og:description["\']', body, re.I))
        missing_og = []
        if not r["has_og_title"]: missing_og.append("og:title")
        if not r["has_og_image"]: missing_og.append("og:image")
        if not r["has_og_desc"]:  missing_og.append("og:description")
        if missing_og:
            r["warnings"].append(f"Missing OG tags: {', '.join(missing_og)} -- broken social/WhatsApp previews")
    except Exception as e:
        logger.debug(f"Error checking OG tags: {e}")

    # -- 9. Images --
    try:
        imgs = re.findall(r'<img\s[^>]*>', body, re.I)
        product_imgs = [i for i in imgs if 'cdn.shopify' in i or 'product' in i.lower()]
        r["img_count"] = len(product_imgs)
        r["img_no_alt"] = sum(1 for i in product_imgs if not re.search(r'alt=["\'][^"\']+', i, re.I))
        if r["img_count"] == 0:
            r["warnings"].append("No product images found on page")
        elif r["img_no_alt"] > 0:
            r["warnings"].append(f"{r['img_no_alt']}/{r['img_count']} product images missing alt text")
    except Exception as e:
        logger.debug(f"Error checking images: {e}")

    # -- 10. Lazy loading --
    try:
        r["has_lazy_load"] = bool(re.search(r'loading=["\']lazy["\']', body, re.I))
    except Exception as e:
        logger.debug(f"Error checking lazy loading: {e}")

    # -- 11. Internal links --
    # Count ALL <a href="..."> that point to the same site:
    #   - Relative paths: /products/..., /collections/..., /blogs/..., /pages/...
    #   - Absolute: https://YOUR_DOMAIN_HERE/...
    # EXCLUDE: fragment-only (#), javascript:, mailto:, tel:, external
    try:
        all_hrefs = re.findall(r'<a[^>]+href=["\']([^"\']+)["\']', body, re.I)
        internal_count = 0
        for h in all_hrefs:
            h = h.strip()
            if not h or h.startswith('#') or h.startswith('javascript') or h.startswith('mailto') or h.startswith('tel'):
                continue
            if h.startswith('/'):  # relative path -- always internal
                internal_count += 1
            elif BRAND_DOMAIN in h:  # absolute internal
                internal_count += 1
        r["internal_links"] = internal_count
        if internal_count < 5:
            r["warnings"].append(f"Only {internal_count} internal links (should be >=5)")
    except Exception as e:
        logger.debug(f"Error checking internal links: {e}")

    # -- 12. Product description word count (from JSON-LD) --
    # Shopify ALWAYS puts the product description in the Product JSON-LD "description" field.
    # It's clean text, no HTML to parse, no class names to guess.
    try:
        desc_words = 0
        _ld_blocks = re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', body, re.S)
        for _b in _ld_blocks:
            try:
                _d = json.loads(_b)
            except json.JSONDecodeError:
                continue
            except Exception as e:
                logger.debug(f"Error parsing JSON-LD for desc_word_count: {e}")
                continue
            if _d.get("@type") == "Product" and _d.get("description"):
                desc_text = _d["description"]
                desc_text = re.sub(r'<[^>]+>', ' ', desc_text)
                desc_text = re.sub(r'\s+', ' ', desc_text).strip()
                desc_words = len(desc_text.split())
                break

        r["desc_word_count"] = desc_words
        if desc_words > 0 and desc_words < 50:
            r["issues"].append(f"Product description only {desc_words} words -- thin content risk")
        elif desc_words >= 50 and desc_words < 100:
            r["warnings"].append(f"Product description {desc_words} words (100+ recommended)")
    except Exception as e:
        logger.debug(f"Error checking desc_word_count: {e}")

    # -- 13-20. JSON-LD schema checks --
    try:
        lds = re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', body, re.S)
        product_count = 0
        for b in lds:
            try:
                d = json.loads(b)
            except json.JSONDecodeError:
                continue
            except Exception as e:
                logger.debug(f"Error parsing JSON-LD block: {e}")
                continue
            t = d.get("@type", "")
            if t == "FAQPage":
                r["faq_count"] += 1
            if t == "BreadcrumbList":
                r["has_breadcrumb"] = True
            if t == "Product":
                product_count += 1
                r["has_product_jsonld"] = True
                if d.get("aggregateRating"):
                    r["has_aggregate_rating"] = True
                r["gtin"] = d.get("gtin") or d.get("gtin13") or d.get("gtin12")
                if d.get("image"):
                    r["has_image_in_schema"] = True
                brand = (d.get("brand") or {}).get("name", "")
                r["brand"] = brand
                if brand.lower() in ("unknown brand", "unknown", ""):
                    r["brand_unknown"] = True
                    r["warnings"].append(f"Brand = '{brand}'")
                # offers
                off = d.get("offers", {})
                if isinstance(off, list):
                    off = off[0] if off else {}
                if off.get("price") or off.get("lowPrice"):
                    r["has_price"] = True
                r["price_currency"] = off.get("priceCurrency", "")
                if off.get("availability"):
                    r["has_availability"] = True
                # offers.url vs canonical
                off_url = off.get("url", "")
                if off_url and r["canonical_url"]:
                    if off_url.rstrip("/") != r["canonical_url"].rstrip("/"):
                        r["offers_url_match"] = False
                # return policy
                ret = off.get("hasMerchantReturnPolicy", {})
                if isinstance(ret, dict):
                    days = ret.get("merchantReturnDays")
                    if days is not None:
                        try:
                            r["return_days"] = int(days)
                            if int(days) > 3:
                                r["issues"].append(
                                    f"Return schema says {days} days -- actual policy is 3-day "
                                    f"damaged-only window (beauty/supplements non-returnable). "
                                    f"The '30 days' is a delivery guarantee, not returns."
                                )
                        except (ValueError, TypeError) as e:
                            logger.debug(f"Error parsing merchantReturnDays: {e}")

        r["product_jsonld_count"] = product_count
        if product_count > 1:
            r["warnings"].append(f"{product_count} Product JSON-LD blocks -- should be 1 (confuses Google)")
        if r["faq_count"] > 0:
            r["warnings"].append(f"{r['faq_count']}x FAQPage (dead since May 2026)")
        if not r["has_product_jsonld"]:
            r["issues"].append("Product JSON-LD missing")
        else:
            if not r["has_aggregate_rating"]:
                r["warnings"].append("No aggregateRating -> no star snippets")
            if not r["has_price"]:
                r["issues"].append("offers.price missing in Product schema -- rich result fails")
            if not r["has_availability"]:
                r["warnings"].append("offers.availability missing -- Google can't show availability badge")
            if r["price_currency"] and r["price_currency"] != "INR":
                r["warnings"].append(f"priceCurrency = '{r['price_currency']}' (should be INR)")
            if not r["has_image_in_schema"]:
                r["warnings"].append("image missing in Product JSON-LD -- required field")
            if not r["offers_url_match"]:
                r["warnings"].append("offers.url doesn't match canonical -- confusing signal")
        if not r["has_breadcrumb"]:
            r["warnings"].append("BreadcrumbList JSON-LD missing -- no breadcrumbs in SERP")
        if r["has_product_jsonld"] and not r["gtin"]:
            r["warnings"].append("GTIN missing")
        if r["page_kb"] > 800:
            r["warnings"].append(f"Page {r['page_kb']}KB (>800KB)")
    except Exception as e:
        logger.debug(f"Error in JSON-LD schema checks: {e}")

    return r


# =============================================
# STAGE 2 -- GSC URL INSPECTION API (with retries)
# =============================================
def gsc_inspect(url: str, retries: int = 2) -> Dict[str, Any]:
    if not _sc_v1:
        return {"error": "Not authenticated"}

    if not gsc_limiter.wait_and_track("inspect"):
        return {"error": "Daily URL Inspection quota reached. Resets tomorrow."}

    for attempt in range(retries):
        try:
            body = {"inspectionUrl": url, "siteUrl": SITE_URL, "languageCode": "en-US"}
            resp = _sc_v1.urlInspection().index().inspect(body=body).execute()
            r = resp.get("inspectionResult", {})
            idx = r.get("indexStatusResult", {})
            rr = r.get("richResultsResult", {})

            rich_issues = []
            detected_types = []
            try:
                for ig in rr.get("detectedItems", []):
                    rt = ig.get("richResultType", "")
                    detected_types.append(rt)
                    for item in ig.get("items", []):
                        for iss in item.get("issues", []):
                            rich_issues.append({
                                "type": rt,
                                "message": iss.get("issueMessage", ""),
                                "severity": iss.get("severity", "")
                            })
            except Exception as e:
                logger.debug(f"Error parsing rich results: {e}")

            return {
                "verdict": idx.get("verdict", "?"),
                "coverage": idx.get("coverageState", "?"),
                "robots": idx.get("robotsTxtState", "?"),
                "indexing": idx.get("indexingState", "?"),
                "fetch": idx.get("pageFetchState", "?"),
                "last_crawl": idx.get("lastCrawlTime", "Never")[:19].replace("T", " ") if idx.get("lastCrawlTime") else "Never",
                "g_canonical": idx.get("googleCanonical", ""),
                "u_canonical": idx.get("userCanonical", ""),
                "crawled_as": idx.get("crawledAs", "?"),
                "in_sitemap": bool(idx.get("sitemap")),
                "referring": idx.get("referringUrls", [])[:3],
                "rich_verdict": rr.get("verdict", "NEUTRAL"),
                "rich_issues": rich_issues,
                "rich_types": detected_types,
                "link": r.get("inspectionResultLink", ""),
                "error": None,
            }
        except Exception as e:
            if attempt < retries - 1:
                logger.warning(f"GSC inspect attempt {attempt+1} failed: {e}. Retrying...")
                time.sleep(1)
            else:
                logger.error(f"GSC inspect failed after {retries} attempts: {e}")
                return {"error": str(e)[:200]}

    return {"error": "GSC inspection failed"}


# =============================================
# STAGE 3 -- SEARCH ANALYTICS (per URL)
# =============================================
def gsc_analytics(url: str) -> Dict[str, Any]:
    if not _wmt_v3:
        return {"error": "Not authenticated", "clicks": 0, "impr": 0, "pos": 0, "ctr": 0,
                "queries": [], "quick_wins": [], "mobile_pct": 0, "appearances": []}
    today = datetime.date.today()
    end = (today - datetime.timedelta(days=3)).isoformat()
    start = (today - datetime.timedelta(days=93)).isoformat()
    try:
        # Total metrics
        if not gsc_limiter.wait_and_track("sa"):
            return {"clicks": 0, "impr": 0, "pos": 0, "ctr": 0, "queries": [], "quick_wins": [],
                    "mobile_pct": 0, "appearances": [], "error": "Daily Search Analytics quota reached"}
        try:
            b1 = {"startDate": start, "endDate": end, "dimensions": [],
                  "dimensionFilterGroups": [{"groupType": "and", "filters": [{"dimension": "page", "operator": "equals", "expression": url}]}],
                  "aggregationType": "byPage", "type": "web", "rowLimit": 1, "dataState": "final"}
            r1 = _wmt_v3.searchanalytics().query(siteUrl=SITE_URL, body=b1).execute()
            total = r1.get("rows", [{}])[0] if r1.get("rows") else {}
        except Exception as e:
            logger.warning(f"Error fetching total metrics: {e}")
            total = {}

        # Top queries
        if not gsc_limiter.wait_and_track("sa"):
            return {"clicks": int(total.get("clicks", 0)), "impr": int(total.get("impressions", 0)),
                    "pos": round(total.get("position", 0), 1), "ctr": round(total.get("ctr", 0) * 100, 1),
                    "queries": [], "quick_wins": [], "mobile_pct": 0, "appearances": [],
                    "error": "Daily Search Analytics quota reached"}
        try:
            b2 = {"startDate": start, "endDate": end, "dimensions": ["query"],
                  "dimensionFilterGroups": [{"groupType": "and", "filters": [{"dimension": "page", "operator": "equals", "expression": url}]}],
                  "aggregationType": "byPage", "type": "web", "rowLimit": 10, "dataState": "final"}
            r2 = _wmt_v3.searchanalytics().query(siteUrl=SITE_URL, body=b2).execute()
            queries = [{"q": r["keys"][0], "clicks": int(r.get("clicks", 0)), "impr": int(r.get("impressions", 0)),
                        "pos": round(r.get("position", 0), 1), "ctr": round(r.get("ctr", 0) * 100, 1)} for r in r2.get("rows", [])]
        except Exception as e:
            logger.warning(f"Error fetching queries: {e}")
            queries = []

        # Device split
        if not gsc_limiter.wait_and_track("sa"):
            pass  # non-critical, continue with defaults
        try:
            b3 = {"startDate": start, "endDate": end, "dimensions": ["device"],
                  "dimensionFilterGroups": [{"groupType": "and", "filters": [{"dimension": "page", "operator": "equals", "expression": url}]}],
                  "aggregationType": "byPage", "type": "web", "rowLimit": 5, "dataState": "final"}
            r3 = _wmt_v3.searchanalytics().query(siteUrl=SITE_URL, body=b3).execute()
            devices = {r["keys"][0]: int(r.get("impressions", 0)) for r in r3.get("rows", [])}
            total_dev = sum(devices.values()) or 1
            mobile_pct = round(devices.get("MOBILE", 0) / total_dev * 100)
        except Exception as e:
            logger.warning(f"Error fetching device split: {e}")
            mobile_pct = 0

        # Search appearance
        if not gsc_limiter.wait_and_track("sa"):
            pass  # non-critical, continue with defaults
        try:
            b4 = {"startDate": start, "endDate": end, "dimensions": ["searchAppearance"],
                  "dimensionFilterGroups": [{"groupType": "and", "filters": [{"dimension": "page", "operator": "equals", "expression": url}]}],
                  "aggregationType": "byPage", "type": "web", "rowLimit": 10, "dataState": "final"}
            r4 = _wmt_v3.searchanalytics().query(siteUrl=SITE_URL, body=b4).execute()
            appearances = [r["keys"][0] for r in r4.get("rows", [])]
        except Exception as e:
            logger.warning(f"Error fetching search appearance: {e}")
            appearances = []

        # Quick-win flag: pos 8-20 + high impressions
        quick_wins = [q for q in queries if 8 <= q["pos"] <= 20 and q["impr"] >= 50]

        return {"clicks": int(total.get("clicks", 0)), "impr": int(total.get("impressions", 0)),
                "pos": round(total.get("position", 0), 1), "ctr": round(total.get("ctr", 0) * 100, 1),
                "queries": queries, "quick_wins": quick_wins,
                "mobile_pct": mobile_pct, "appearances": appearances,
                "error": None}
    except Exception as e:
        logger.exception(f"Error in gsc_analytics for {url}")
        return {"clicks": 0, "impr": 0, "pos": 0, "ctr": 0, "queries": [], "quick_wins": [],
                "mobile_pct": 0, "appearances": [], "error": str(e)[:200]}


# =============================================
# SITEMAP GAP (one-time per session)
# =============================================
_sitemap_data = None
_sitemap_fetched_at = 0
_SITEMAP_TTL = 300  # 5 minutes

def get_sitemap_gap():
    global _sitemap_data, _sitemap_fetched_at
    if _sitemap_data is not None and (time.time() - _sitemap_fetched_at) < _SITEMAP_TTL:
        return _sitemap_data
    if not _wmt_v3:
        return None
    try:
        resp = _wmt_v3.sitemaps().list(siteUrl=SITE_URL).execute()
        sms = resp.get("sitemap", [])
        result = []
        for sm in sms:
            submitted = 0
            indexed = 0
            for c in sm.get("contents", []):
                submitted += int(c.get("submitted", 0))
                indexed += int(c.get("indexed", 0))
            result.append({"path": sm.get("path", ""), "submitted": submitted, "indexed": indexed,
                           "gap": submitted - indexed, "last_submitted": sm.get("lastSubmitted", ""),
                           "last_downloaded": sm.get("lastDownloaded", "")})
        _sitemap_data = result
        _sitemap_fetched_at = time.time()
        return result
    except Exception as e:
        logger.debug(f"Error fetching sitemap gap: {e}")
        _sitemap_data = []
        _sitemap_fetched_at = time.time()
        return []


# =============================================
# STAGE 4 -- DECISION ENGINE (all 17 states)
# =============================================
def decide(pf, gsc, sa):
    acts = []
    def a(p, cat, msg, fix):
        acts.append({"p": p, "cat": cat, "msg": msg, "fix": fix})

    # -- Pre-flight checks (no API) --
    if pf["http_status"] and pf["http_status"] >= 400:
        a(1, "HTTP", f"HTTP {pf['http_status']} -- page broken", "Restore product or 301 redirect in Shopify.")
    if pf["http_status"] and 300 <= pf["http_status"] < 400:
        a(2, "REDIRECT", f"HTTP {pf['http_status']} -- redirects", "Check if intentional. Fix canonical in Shopify.")
    if pf["noindex"]:
        a(1, "BLOCKED", "Page has noindex -- invisible to Google", "Shopify -> Products -> SEO -> uncheck 'Hide from search'")
    if not pf["canonical_self"]:
        a(2, "CANONICAL", "Canonical points to different URL", "Check duplicate handles. Delete dupes + 301 redirect.")
    if pf["brand_unknown"]:
        a(3, "SCHEMA", f"Brand = '{pf['brand']}'", "Set real brand in Shopify vendor field.")
    if pf["desc_word_count"] > 0 and pf["desc_word_count"] < 50:
        a(1, "QUALITY", f"Product description only {pf['desc_word_count']} words -- thin content", "Write unique 150+ word description. Add India-specific context, usage tips, specs.")
    elif pf["desc_word_count"] >= 50 and pf["desc_word_count"] < 100:
        a(3, "QUALITY", f"Description {pf['desc_word_count']} words (100+ ideal)", "Expand with usage tips, comparisons, India-specific info.")
    if pf["has_product_jsonld"] and not pf["has_price"]:
        a(1, "SCHEMA", "offers.price missing -- Product rich result will fail", "Check theme Product JSON-LD. Ensure offers.price is populated from Shopify variant price.")
    if pf["has_product_jsonld"] and not pf["has_availability"]:
        a(2, "SCHEMA", "offers.availability missing", "Add InStock/OutOfStock to Product schema in theme.")
    if pf["has_product_jsonld"] and not pf["has_image_in_schema"]:
        a(2, "SCHEMA", "image missing in Product JSON-LD -- required field", "Add product image URL to schema in theme Liquid.")
    if pf["has_product_jsonld"] and not pf["offers_url_match"]:
        a(3, "SCHEMA", "offers.url != canonical", "Match offers.url to canonical in theme JSON-LD.")
    if pf["has_product_jsonld"] and pf["price_currency"] and pf["price_currency"] != "INR":
        a(2, "SCHEMA", f"priceCurrency = '{pf['price_currency']}' (should be INR)", "Fix in theme or Shopify currency settings.")
    if pf["product_jsonld_count"] > 1:
        a(2, "SCHEMA", f"{pf['product_jsonld_count']} Product JSON-LD blocks", "Remove duplicate. Keep one. Check theme + apps injecting schema.")
    if not pf["has_breadcrumb"]:
        a(3, "SCHEMA", "BreadcrumbList missing -- no breadcrumbs in SERP", "Add BreadcrumbList JSON-LD in theme (Home > Collections > Product).")
    if pf["img_count"] == 0:
        a(2, "CONTENT", "No product images on page", "Add product images. Essential for image search + conversions.")
    elif pf["img_no_alt"] > 0:
        a(3, "IMAGE", f"{pf['img_no_alt']}/{pf['img_count']} images missing alt text", "Add descriptive alt text (brand + product name) to images.")
    if pf["internal_links"] < 5:
        a(3, "CRAWL", f"Only {pf['internal_links']} internal links", "Add links from collection pages + related products + blog posts.")
    # Return policy: actual policy is 3-day damaged-only, schema says 30
    if pf.get("return_days") and pf["return_days"] > 3:
        a(1, "RISK",
          f"Schema says {pf['return_days']}-day returns -- actual policy: 3-day damaged-only, beauty/supplements non-returnable",
          "Fix theme JSON-LD: merchantReturnDays -> 3, returnPolicyCategory -> MerchantReturnFiniteReturnWindow, "
          "applicableCountry -> IN. Add returnPolicySeasonalOverride or remove for non-returnable categories. "
          "Also fix '30-Day Easy Returns' banner -- misleading vs actual 3-day damaged-only policy.")
    if pf["has_product_jsonld"] and not pf["has_aggregate_rating"]:
        a(2, "CTR", "No star snippet -- aggregateRating missing", "Judge.me -> Settings -> Rich Snippets -> enable Product review JSON-LD.")
    if pf["has_product_jsonld"] and not pf["gtin"] and pf["brand"] and not pf["brand_unknown"]:
        a(3, "SCHEMA", f"GTIN missing ({pf['brand']})", "Add UPC from US listing -> Shopify Barcode field.")
    if pf["title_len"] > 60:
        a(3, "CTR", f"Title {pf['title_len']} chars (>60 = truncated)", f"Shorten to: '{(pf['title'] or '')[:55]}...'")
    if pf["faq_count"] > 0:
        a(4, "CLEANUP", f"{pf['faq_count']}x FAQPage (dead May 2026)", "Remove from theme JSON-LD. Keep FAQ as HTML.")
    if pf["page_kb"] > 800:
        a(4, "PERF", f"Page {pf['page_kb']}KB", "Cut nav links 547->30, defer scripts. Target <500KB.")

    # -- GSC-dependent checks (all 17 states) --
    cov = gsc.get("coverage", "")
    fetch = gsc.get("fetch", "")
    idx_state = gsc.get("indexing", "")

    # All 17 coverage states
    if cov:
        cl = cov.lower()
        if "submitted and indexed" in cl:
            pass  # good
        elif "indexed" in cl and "not submitted" in cl:
            a(3, "SITEMAP", "Indexed but not in sitemap", "Add URL to sitemap. Resubmit sitemap in GSC.")
        elif "crawled" in cl and "not indexed" in cl:
            a(1, "QUALITY", f"'{cov}' -- Google crawled but rejected", "Make description unique 150+ words. Add value beyond Amazon copy.")
        elif "discovered" in cl and "not indexed" in cl:
            a(2, "CRAWL", f"'{cov}' -- queued, not yet crawled", "Add internal links from collections + blog posts.")
        elif "alternate" in cl and "canonical" in cl:
            a(4, "INFO", f"'{cov}'", "OK if intentional variant. Check canonical is correct.")
        elif "duplicate" in cl and "user" in cl:
            a(2, "CANONICAL", f"'{cov}'", "Set explicit canonical tag on this page.")
        elif "duplicate" in cl and "google chose" in cl:
            a(2, "CANONICAL", f"'{cov}'", "Google picked a different canonical. Check for duplicate products with similar handles.")
        elif "redirect" in cl:
            a(1 if "error" in cl else 3, "REDIRECT", f"'{cov}'", "Fix redirect chain. Ensure final destination is live.")

    if fetch == "NOT_FOUND":
        a(1, "404", "Google got 404", "Restore product or 301 redirect.")
    elif fetch == "SOFT_404":
        a(1, "404", "Soft 404 -- page exists but looks empty to Google", "Add real content. Check if product is unpublished.")
    elif fetch == "SERVER_ERROR":
        a(1, "SERVER", "Google got 5xx", "Check Shopify status / app conflicts.")
    elif fetch == "ACCESS_DENIED":
        a(1, "AUTH", "Google got 401 -- page requires login", "Remove password protection from this page.")
    elif fetch == "ACCESS_FORBIDDEN":
        a(1, "AUTH", "Google got 403 -- access forbidden", "Check Shopify permissions / country blocks.")
    elif fetch == "BLOCKED_ROBOTS_TXT":
        a(1, "ROBOTS", "Blocked by robots.txt", "Fix robots.txt -- /products/ should not be disallowed.")
    elif fetch == "REDIRECT_ERROR":
        a(1, "REDIRECT", "Redirect error -- Google can't follow", "Fix redirect chain in Shopify URL redirects.")
    elif fetch == "BLOCKED_4XX":
        a(1, "HTTP", "Blocked by other 4xx error", "Check server response. May be geo-blocking or rate limiting Googlebot.")

    if idx_state == "BLOCKED_BY_META_TAG":
        if not pf["noindex"]:  # noindex in GSC but not in our crawl = was recently fixed
            a(2, "INFO", "GSC still shows noindex (may be stale)", "Wait for re-crawl. Or open in GSC -> Request Indexing.")
    elif idx_state == "BLOCKED_BY_HTTP_HEADER":
        a(1, "BLOCKED", "X-Robots-Tag: noindex in HTTP header", "Remove noindex header from Shopify app or theme.")

    if gsc.get("robots") == "DISALLOWED":
        a(1, "ROBOTS", "Blocked by robots.txt", "Fix robots.txt for /products/ path.")

    gc, uc = gsc.get("g_canonical", ""), gsc.get("u_canonical", "")
    if gc and uc and gc.rstrip("/") != uc.rstrip("/"):
        a(2, "CANONICAL", f"Google chose: {gc}", "Delete duplicate handle, 301 redirect.")

    for ri in gsc.get("rich_issues", []):
        if ri["severity"] == "ERROR":
            a(2, "SCHEMA", f"{ri['type']}: {ri['message']}", "Fix in theme JSON-LD. Validate: search.google.com/test/rich-results")

    # -- CROSS-VALIDATION: GSC (stale) vs Pre-flight (live) --
    live_status = pf.get("http_status", 0)
    live_noindex = pf.get("noindex", False)

    if fetch in ("NOT_FOUND", "SOFT_404") and live_status == 200:
        a(1, "FIXED", "GSC says 404 but page is LIVE now (HTTP 200) -- GSC data is stale",
          "Page is restored. Click 'Request Indexing' below to tell Google to recrawl NOW.")
    if fetch == "SERVER_ERROR" and live_status == 200:
        a(1, "FIXED", "GSC says 5xx but page loads fine now (HTTP 200)",
          "Server issue resolved. Click 'Request Indexing' to recrawl.")
    if idx_state == "BLOCKED_BY_META_TAG" and not live_noindex:
        a(1, "FIXED", "GSC says noindex but page has NO noindex tag now",
          "Noindex removed. Click 'Request Indexing' -- Google will index on next crawl.")
    if fetch == "ACCESS_DENIED" and live_status == 200:
        a(1, "FIXED", "GSC says 401 (login required) but page is publicly accessible now",
          "Auth removed. Click 'Request Indexing'.")
    if fetch == "ACCESS_FORBIDDEN" and live_status == 200:
        a(1, "FIXED", "GSC says 403 (forbidden) but page loads fine now",
          "Access fixed. Click 'Request Indexing'.")

    # Reverse: page was indexed but is now broken
    if cov and "indexed" in cov.lower() and "not" not in cov.lower():
        if live_status >= 400:
            a(1, "BREAKING", f"Page is INDEXED in Google but now returns HTTP {live_status} -- will LOSE indexing soon",
              f"Page returning {live_status}. Restore immediately or set up 301 redirect before Google recrawls.")
        if live_noindex:
            a(1, "BREAKING", "Page is INDEXED but now has noindex tag -- will be REMOVED from Google on next crawl",
              "Remove noindex tag if this product should stay in search. If intentional, ignore.")

    # GSC says crawled-not-indexed -- verify if content is actually thin
    if cov and "crawled" in cov.lower() and "not indexed" in cov.lower():
        dw = pf.get("desc_word_count", 0)
        if dw >= 150:
            a(2, "VERIFY", "GSC rejected this page but description is {dw} words -- content may not be the problem".format(dw=dw),
              "Content looks adequate. Issue may be: duplicate content across similar products, "
              "low backlinks, low internal links ({il}), or site-wide quality signal. "
              "Check if similar products exist with same description.".format(dw=dw, il=pf.get("internal_links", 0)))

    # Quick-win keywords
    for qw in sa.get("quick_wins", []):
        a(3, "OPPORTUNITY", f"Quick win: '{qw['q']}' at pos {qw['pos']} with {qw['impr']} impressions",
          "Almost page 1. Optimize title + description for this keyword. Add internal links with this anchor text.")

    # CTR optimization
    pos, ctr = sa.get("pos", 0), sa.get("ctr", 0)
    if 5 <= pos <= 15 and ctr < 2 and sa.get("impr", 0) > 50:
        a(3, "CTR", f"Pos {pos} but CTR {ctr}%", "Front-load keyword in title. Add USP in meta desc (USA import, COD, genuine).")

    # Search appearance check
    apps = sa.get("appearances", [])
    if apps and "PRODUCT_SNIPPET" not in apps and "MERCHANT_LISTINGS" not in apps:
        if pf["has_product_jsonld"]:
            a(3, "ENRICHMENT", "No Product enrichment in SERP despite having schema", "Check Product schema validity. Fix errors flagged above.")

    acts.sort(key=lambda x: x["p"])
    return acts


# =============================================
# PARALLEL BATCH AUDITING (multithreading)
# =============================================
def audit_url_parallel(url: str) -> AuditResult:
    """Single URL audit (for threading)."""
    try:
        pf = preflight(url)
        gsc_connected = _sc_v1 is not None
        if gsc_connected:
            gsc = gsc_inspect(url)
            sa = gsc_analytics(url)
        else:
            gsc = {**GSC_OFFLINE_STUB, "referring": [], "rich_issues": [], "rich_types": []}
            sa = {**SA_OFFLINE_STUB, "queries": [], "quick_wins": [], "appearances": []}

        actions = decide(pf, gsc if (not gsc.get("error") or gsc.get("skipped")) else {}, sa)
        score = sa.get("impr", 0) + (100000 if any(act["p"] == 1 for act in actions) else 0) + (10000 if any(act["p"] == 2 for act in actions) else 0)

        return AuditResult(
            url=url,
            status="success",
            pf=pf,
            gsc=gsc,
            sa=sa,
            actions=actions,
            score=score
        )
    except Exception as e:
        logger.exception(f"Error auditing {url}")
        return AuditResult(
            url=url,
            status="error",
            error=str(e)[:200]
        )

def audit_batch(urls: List[str]) -> List[AuditResult]:
    """Audit multiple URLs in parallel using ThreadPoolExecutor."""
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(audit_url_parallel, url): url for url in urls}
        for future in as_completed(futures):
            try:
                result = future.result(timeout=60)
                results.append(result)
            except Exception as e:
                logger.error(f"Error in batch processing: {e}")
                url = futures[future]
                results.append(AuditResult(url=url, status="error", error=str(e)[:200]))
    return results


# =============================================
# API ROUTES
# =============================================

@app.route("/api/audit", methods=["POST"])
@handle_errors
def api_audit():
    data = request.get_json() or {}
    url = (data.get("url", "") or "").strip()
    if not url:
        return jsonify({"error": "No URL"}), 400

    is_valid, msg = validate_url(url)
    if not is_valid:
        return jsonify({"error": msg}), 400

    pf = preflight(url)
    gsc_connected = _sc_v1 is not None
    if gsc_connected:
        gsc = gsc_inspect(url)
        sa = gsc_analytics(url)
    else:
        gsc = {**GSC_OFFLINE_STUB, "referring": [], "rich_issues": [], "rich_types": []}
        sa = {**SA_OFFLINE_STUB, "queries": [], "quick_wins": [], "appearances": []}

    actions = decide(pf, gsc if (not gsc.get("error") or gsc.get("skipped")) else {}, sa)
    score = sa.get("impr", 0) + (100000 if any(act["p"] == 1 for act in actions) else 0) + (10000 if any(act["p"] == 2 for act in actions) else 0)
    return jsonify({"pf": pf, "gsc": gsc, "sa": sa, "actions": actions, "score": score,
                    "mode": "full" if gsc_connected else "preflight"})


@app.route("/api/audit-batch", methods=["POST"])
@handle_errors
def api_audit_batch():
    """Batch audit with ThreadPoolExecutor."""
    data = request.get_json() or {}
    urls_raw = data.get("urls", [])

    if not isinstance(urls_raw, list):
        return jsonify({"error": "URLs must be a list"}), 400

    urls_raw = [u.strip() for u in urls_raw if isinstance(u, str)]
    valid_urls, errors = validate_urls(urls_raw)

    if not valid_urls:
        return jsonify({"error": f"No valid URLs: {', '.join(errors[:3])}"}), 400

    results = audit_batch(valid_urls)

    results_data = []
    for r in results:
        results_data.append({
            "url": r.url,
            "status": r.status,
            "error": r.error,
            "pf": r.pf,
            "gsc": r.gsc,
            "sa": r.sa,
            "actions": r.actions,
            "score": r.score,
            "mode": "full" if _sc_v1 else "preflight"
        })

    return jsonify({
        "total": len(valid_urls),
        "success": sum(1 for r in results if r.status == "success"),
        "failed": sum(1 for r in results if r.status == "error"),
        "results": results_data,
        "warnings": errors if errors else []
    })


@app.route("/api/auth", methods=["POST"])
@handle_errors
def api_auth():
    success, msg = init_google()
    if success:
        return jsonify({"ok": True, "site": SITE_URL})
    else:
        return jsonify({"ok": False, "error": msg}), 500


@app.route("/api/status")
@handle_errors
def api_status():
    return jsonify({
        "authenticated": _sc_v1 is not None,
        "site": SITE_URL,
        "quota": gsc_limiter.usage if _sc_v1 else None,
    })


@app.route("/api/import-csv", methods=["POST"])
@handle_errors
def api_import_csv():
    """
    Import GSC CSV export (Table.csv + optional Metadata.csv).
    Parses URLs, reads the GSC issue type from Metadata,
    returns URLs with the reported issue for batch cross-validation.
    Accepts multipart form: files 'table' and optionally 'metadata'.
    """
    import csv
    import io

    if 'table' not in request.files:
        return jsonify({"error": "Upload Table.csv file"}), 400

    table_file = request.files['table']
    table_text = table_file.read().decode('utf-8', errors='ignore')

    # Parse metadata if provided
    issue_type = "Unknown"
    if 'metadata' in request.files:
        meta_text = request.files['metadata'].read().decode('utf-8', errors='ignore')
        for row in csv.DictReader(io.StringIO(meta_text)):
            if row.get("Property") == "Issue":
                issue_type = row.get("Value", "Unknown")

    # Parse table
    urls = []
    reader = csv.DictReader(io.StringIO(table_text))
    for row in reader:
        url = row.get("URL", "").strip()
        last_crawled = row.get("Last crawled", "").strip()
        if url and url.startswith("http"):
            urls.append({"url": url, "last_crawled": last_crawled, "gsc_issue": issue_type})

    return jsonify({"issue_type": issue_type, "total": len(urls), "urls": urls})


@app.route("/api/verify-url", methods=["POST"])
@handle_errors
def api_verify_url():
    """
    Cross-validate a single URL from GSC CSV against live page.
    Takes the URL + the GSC-reported issue and checks if it's still valid.
    Returns: live status + whether issue is fixed/still broken/worse.
    """
    data = request.get_json() or {}
    url = (data.get("url", "") or "").strip()
    gsc_issue = data.get("gsc_issue", "")

    if not url:
        return jsonify({"error": "No URL"}), 400

    # -- Detect URL type --
    url_type = "other"
    if "/products/" in url:
        url_type = "product"
    elif "/collections/" in url:
        url_type = "collection"
    elif "/blogs/" in url:
        url_type = "blog"
    elif "/pages/" in url:
        url_type = "page"

    # Quick live check
    live_status = 0
    noindex = False
    page_kb = 0
    desc_words = 0
    has_product = False
    has_rating = False
    has_collection_desc = False
    product_count_on_page = 0
    shopify_exists = None  # None = not checked, True/False = result
    title = ""

    # -- For products: check Shopify JSON endpoint first (fast, no HTML parsing) --
    if url_type == "product":
        try:
            handle = url.split("/products/")[-1].split("?")[0]
            json_url = f"https://{BRAND_DOMAIN}/products/{handle}.json"
            req = urllib.request.Request(json_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                pdata = json.loads(resp.read().decode())
                p = pdata.get("product", {})
                shopify_exists = True
                title = p.get("title", "")
                body_html = p.get("body_html", "")
                desc_words = len(re.sub(r'<[^>]+>', ' ', body_html).split()) if body_html else 0
                variants = p.get("variants", [])
        except urllib.error.HTTPError as e:
            if e.code == 404:
                shopify_exists = False
            live_status = e.code
        except json.JSONDecodeError as e:
            logger.debug(f"JSON parse error for Shopify endpoint: {e}")
            shopify_exists = None
        except Exception as e:
            logger.debug(f"Error checking Shopify JSON endpoint: {e}")
            shopify_exists = None  # couldn't check

    # -- Live page check (for all URL types) --
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            live_status = resp.status
            body = resp.read().decode("utf-8", errors="ignore")
        page_kb = len(body) // 1024

        # noindex check
        try:
            rm = re.search(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']+)', body, re.I)
            if rm and "noindex" in rm.group(1).lower():
                noindex = True
        except Exception as e:
            logger.debug(f"Error checking noindex in verify-url: {e}")

        # JSON-LD scan
        try:
            lds = re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', body, re.S)
            for b in lds:
                try:
                    d = json.loads(b)
                    if d.get("@type") == "Product":
                        has_product = True
                        if d.get("aggregateRating"):
                            has_rating = True
                        if url_type == "product" and desc_words == 0:
                            desc = d.get("description", "")
                            desc_words = len(re.sub(r'<[^>]+>', ' ', desc).split()) if desc else 0
                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    logger.debug(f"Error parsing JSON-LD in verify-url: {e}")
        except Exception as e:
            logger.debug(f"Error scanning JSON-LD in verify-url: {e}")

        # For collections: check for description + product count
        if url_type == "collection":
            try:
                col_desc = re.search(r'<div[^>]*class="[^"]*collection[_-]?description[^"]*"[^>]*>(.*?)</div>', body, re.S | re.I)
                if col_desc:
                    ctext = re.sub(r'<[^>]+>', ' ', col_desc.group(1)).strip()
                    if len(ctext.split()) > 20:
                        has_collection_desc = True
                        desc_words = len(ctext.split())
                # Count products on page
                product_count_on_page = len(re.findall(r'class="[^"]*product-card[^"]*"', body, re.I))
                if product_count_on_page == 0:
                    product_count_on_page = len(re.findall(r'/products/[a-z0-9-]+', body))
            except Exception as e:
                logger.debug(f"Error checking collection in verify-url: {e}")

    except urllib.error.HTTPError as e:
        live_status = e.code
    except Exception as e:
        live_status = 0
        logger.debug(f"Error in live page check for verify-url: {e}")

    # Cross-validate: GSC issue vs live reality
    verdict = "UNKNOWN"
    detail = ""
    action = ""
    issue_lower = gsc_issue.lower()

    if "server error" in issue_lower or "5xx" in issue_lower:
        if live_status == 200:
            verdict = "FIXED"
            detail = f"GSC: server error -> Live: HTTP {live_status}"
            action = "Request re-indexing in GSC"
        elif live_status == 404:
            verdict = "CHANGED"
            detail = f"GSC: server error -> Live: HTTP 404 (product deleted)"
            action = "Remove from sitemap or leave -- Google will drop it"
        else:
            verdict = "STILL_BROKEN"
            detail = f"GSC: server error -> Live: HTTP {live_status}"
            action = "Check Shopify status / app conflicts"

    elif "not found" in issue_lower or "404" in issue_lower:
        if live_status == 200:
            verdict = "FIXED"
            detail = f"GSC: 404 -> Live: HTTP {live_status} (page restored)"
            action = "Request re-indexing in GSC"
        elif live_status == 404:
            verdict = "STILL_BROKEN"
            detail = "Still 404 -- product doesn't exist"
            action = "Delete from sitemap or leave for natural removal"
        else:
            verdict = "CHANGED"
            detail = f"GSC: 404 -> Live: HTTP {live_status}"
            action = "Check what changed"

    elif "noindex" in issue_lower:
        if live_status == 200 and not noindex:
            verdict = "FIXED"
            detail = "GSC: noindex -> Live: no noindex tag"
            action = "Request re-indexing -- noindex removed"
        elif noindex:
            verdict = "STILL_BROKEN"
            detail = "Still has noindex tag"
            action = "Shopify -> Products -> SEO -> uncheck 'Hide from search'"
        elif live_status == 404:
            verdict = "CHANGED"
            detail = "GSC: noindex -> Live: 404 (product deleted)"
            action = "Product gone -- ignore"

    elif "crawled" in issue_lower and "not indexed" in issue_lower:
        if live_status == 404:
            verdict = "NOW_DEAD"
            if shopify_exists is False:
                detail = "Product deleted from Shopify -- confirmed via Shopify API"
            else:
                detail = "Page returns 404"
            action = "Will drop from GSC naturally"
        elif live_status != 200:
            verdict = "BROKEN"
            detail = f"HTTP {live_status}"
            action = "Fix the page first"
        elif url_type == "collection":
            # Collection pages need description + products
            if has_collection_desc and desc_words > 50:
                verdict = "COLLECTION_OK"
                detail = f"Collection page with {desc_words}-word description, ~{product_count_on_page} products"
                action = "Looks good -- add internal links from blog posts to boost authority"
            else:
                verdict = "COLLECTION_EMPTY"
                detail = f"Collection page -- no description text ({desc_words} words)"
                action = "Add 100+ word unique collection description in Shopify Admin -> Collections -> this collection -> Description"
        elif url_type == "product":
            # Product pages -- use Shopify data if available
            if shopify_exists is False:
                verdict = "SHOPIFY_DELETED"
                detail = "Product handle exists as URL but NOT in Shopify catalog -- orphan page"
                action = "Product was deleted from Shopify. URL will eventually 404. Consider 301 redirect if it had traffic."
            elif desc_words < 50:
                verdict = "STILL_WEAK"
                detail = f"Product exists ({desc_words} words) -- description too thin"
                action = "Write unique 150+ word description in Shopify Admin -> Products -> this product"
                if not has_product:
                    detail += " | No Product JSON-LD"
            elif desc_words < 100:
                verdict = "NEEDS_WORK"
                detail = f"Product exists ({desc_words} words) -- could be longer"
                action = "Expand to 150+ words with India-specific content"
                if not has_rating:
                    detail += " | No star rating"
            else:
                verdict = "CONTENT_OK"
                detail = f"Product exists ({desc_words} words) -- content adequate"
                action = "Issue likely: low authority or weak internal links. Add blog post + collection links."
                if not has_rating:
                    detail += " | No star rating"
        elif url_type == "blog":
            verdict = "BLOG_THIN"
            detail = f"Blog post ({desc_words} words)"
            if desc_words > 200:
                verdict = "BLOG_OK"
                action = "Blog content OK -- add internal links + promote on social"
            else:
                action = "Expand blog post to 500+ words with unique content"
        else:
            # Other page types
            verdict = "LIVE"
            detail = f"Page type: {url_type} ({page_kb}KB)"
            action = "Check if this page should be indexed or noindexed"

    elif "blocked" in issue_lower and "robots" in issue_lower:
        if live_status == 200:
            verdict = "ACCESSIBLE"
            detail = "Page loads OK -- but may still be blocked by robots.txt rules"
            action = "Check robots.txt for this path. Our robots.txt changes may fix this."
        elif live_status == 404:
            verdict = "DEAD"
            detail = "Product deleted -- robots.txt block doesn't matter"
            action = "Ignore"

    elif "forbidden" in issue_lower or "403" in issue_lower:
        if live_status == 200:
            verdict = "FIXED"
            detail = "GSC: 403 forbidden -> Live: HTTP 200"
            action = "Request re-indexing"
        elif live_status == 403:
            verdict = "STILL_BROKEN"
            detail = "Still returning 403"
            action = "Check Shopify geo-blocking / password protection"

    elif "soft 404" in issue_lower:
        if live_status == 200 and desc_words > 50:
            verdict = "FIXED"
            detail = f"GSC: soft 404 -> Live: real content ({desc_words} words)"
            action = "Request re-indexing"
        elif live_status == 200 and desc_words <= 50:
            verdict = "STILL_WEAK"
            detail = "Page exists but content too thin -- Google sees it as empty"
            action = "Add real product content"

    elif "redirect" in issue_lower:
        if live_status == 200:
            verdict = "FIXED"
            detail = "GSC: redirect issue -> Live: HTTP 200 (no redirect)"
            action = "Request re-indexing"
        elif 300 <= live_status < 400:
            verdict = "STILL_REDIRECTING"
            detail = f"Still redirecting (HTTP {live_status})"
            action = "Fix redirect chain or accept if intentional"

    elif "duplicate" in issue_lower:
        if live_status == 200:
            verdict = "LIVE"
            detail = "Page exists -- check canonical tag"
            action = "Set explicit canonical. Check for duplicate product handles."

    else:
        # Unknown issue type -- just report live status
        if live_status == 200:
            verdict = "LIVE"
            detail = f"Page loads OK (HTTP 200, {page_kb}KB)"
            action = "Page is live -- check specific issue in GSC"
        elif live_status == 404:
            verdict = "DEAD"
            detail = "Page returns 404"
            action = "Product deleted"
        else:
            verdict = "CHECK"
            detail = f"HTTP {live_status}"
            action = "Investigate"

    return jsonify({
        "url": url,
        "url_type": url_type,
        "gsc_issue": gsc_issue,
        "live_status": live_status,
        "verdict": verdict,
        "detail": detail,
        "action": action,
        "noindex": noindex,
        "page_kb": page_kb,
        "desc_words": desc_words,
        "has_product_schema": has_product,
        "has_rating": has_rating,
        "shopify_exists": shopify_exists,
        "title": title,
    })


@app.route("/api/sitemap-gap")
@handle_errors
def api_sitemap_gap():
    data = get_sitemap_gap()
    if data is None:
        return jsonify({"error": "Not connected"}), 401
    return jsonify(data)


@app.route("/api/snippet-performance", methods=["POST"])
@handle_errors
def api_snippet_performance():
    """Product snippet & rich results performance."""
    from gsc_snippets import get_all_snippet_types_for_product
    data = request.get_json() or {}
    url = (data.get("url", "") or "").strip()
    if not url:
        return jsonify({"error": "No URL"}), 400
    if not _wmt_v3:
        return jsonify({"error": "Not authenticated"}), 401
    snippets = get_all_snippet_types_for_product(_wmt_v3, SITE_URL, url, days=90)
    return jsonify(snippets)


@app.route("/api/merchant-listings", methods=["POST"])
@handle_errors
def api_merchant_listings():
    """Google Shopping / Merchant Listings performance."""
    from gsc_snippets import get_merchant_listings_data
    data = request.get_json() or {}
    url = (data.get("url", "") or "").strip()
    if not url:
        return jsonify({"error": "No URL"}), 400
    if not _wmt_v3:
        return jsonify({"error": "Not authenticated"}), 401
    merchant = get_merchant_listings_data(_wmt_v3, SITE_URL, url, days=90)
    return jsonify(merchant)


@app.route("/api/store-snippet-stats")
@handle_errors
def api_store_snippet_stats():
    """Site-wide snippet statistics."""
    from gsc_snippets import get_store_wide_snippet_stats
    if not _wmt_v3:
        return jsonify({"error": "Not authenticated"}), 401
    stats = get_store_wide_snippet_stats(_wmt_v3, SITE_URL, days=90)
    return jsonify(stats)


@app.route("/api/shopify-preview", methods=["POST"])
@handle_errors
def api_shopify_preview():
    """Preview what fixes would be applied to Shopify — no changes made."""
    data = request.get_json() or {}
    url = (data.get("url", "") or "").strip()
    audit_result = data.get("audit", {})

    if not url or "/products/" not in url:
        return jsonify({"error": "Not a product URL"}), 400

    try:
        handle = url.split("/products/")[-1].split("?")[0]
    except Exception:
        return jsonify({"error": "Could not extract product handle"}), 400

    shopify_token = os.getenv("SHOPIFY_ACCESS_TOKEN", "")
    shopify_store = os.getenv("SHOPIFY_STORE", "")
    if not shopify_token:
        return jsonify({"error": "SHOPIFY_ACCESS_TOKEN not set in .env"}), 400

    try:
        from shopify_sync import ShopifyClient, get_product_id_by_handle, get_product_details
        from shopify_sync import fix_product_title, fix_product_description, fix_product_hidden_status
    except ImportError as e:
        return jsonify({"error": f"Missing module: {e}"}), 500

    client = ShopifyClient(shopify_store, shopify_token)

    product_id = get_product_id_by_handle(client, handle)
    if not product_id:
        return jsonify({"error": f"Product '{handle}' not found in Shopify"}), 404

    product = get_product_details(client, product_id)
    if not product:
        return jsonify({"error": "Could not fetch product details"}), 500

    changes = []

    title_changed, new_title = fix_product_title(product, audit_result)
    if title_changed:
        changes.append({
            "field": "Title",
            "old": product.get("title", ""),
            "new": new_title,
            "reason": f"Title too long ({audit_result.get('pf', {}).get('title_len', 0)} chars > 60)"
        })

    desc_changed, new_desc = fix_product_description(product, audit_result)
    if desc_changed:
        old_words = len((product.get("body_html", "") or "").split())
        new_words = len((new_desc or "").split())
        changes.append({
            "field": "Description",
            "old": f"{old_words} words",
            "new": f"{new_words} words",
            "reason": f"Thin content ({old_words} words < 150)"
        })

    hidden_changed, _ = fix_product_hidden_status(product, audit_result)
    if hidden_changed:
        changes.append({
            "field": "Visibility",
            "old": "Hidden (noindex)",
            "new": "Visible",
            "reason": "Product has noindex tag"
        })

    return jsonify({
        "handle": handle,
        "product_id": product_id,
        "product_title": product.get("title", ""),
        "changes": changes,
        "has_changes": len(changes) > 0,
        "message": f"{len(changes)} fix(es) available" if changes else "No auto-fixes needed"
    })


@app.route("/api/shopify-fix", methods=["POST"])
@handle_errors
def api_shopify_fix():
    """Apply fixes to Shopify product after user confirms preview."""
    data = request.get_json() or {}
    url = (data.get("url", "") or "").strip()
    audit_result = data.get("audit", {})

    if not url or "/products/" not in url:
        return jsonify({"error": "Not a product URL"}), 400

    handle = url.split("/products/")[-1].split("?")[0]

    shopify_token = os.getenv("SHOPIFY_ACCESS_TOKEN", "")
    shopify_store = os.getenv("SHOPIFY_STORE", "")
    if not shopify_token:
        return jsonify({"error": "SHOPIFY_ACCESS_TOKEN not set in .env"}), 400

    try:
        from shopify_sync import ShopifyClient, get_product_id_by_handle, get_product_details, apply_fixes_to_product
    except ImportError as e:
        return jsonify({"error": f"Missing module: {e}"}), 500

    client = ShopifyClient(shopify_store, shopify_token)

    product_id = get_product_id_by_handle(client, handle)
    if not product_id:
        return jsonify({"error": f"Product '{handle}' not found in Shopify"}), 404

    product = get_product_details(client, product_id)
    if not product:
        return jsonify({"error": "Could not fetch product details"}), 500

    logger.info(f"Applying Shopify fixes to: {handle} (ID: {product_id})")
    fix_result = apply_fixes_to_product(client, product, audit_result)

    if fix_result["success"]:
        logger.info(f"Shopify fix applied: {handle} — {fix_result['changes']}")
    else:
        logger.error(f"Shopify fix failed: {handle} — {fix_result['error']}")

    return jsonify(fix_result)


@app.route("/api/reindex", methods=["POST"])
@handle_errors
def api_reindex():
    """Request Google to re-crawl a URL after fixes."""
    data = request.get_json() or {}
    url = (data.get("url", "") or "").strip()

    if not url:
        return jsonify({"error": "No URL"}), 400
    if not _sc_v1:
        return jsonify({"error": "Connect GSC first"}), 401

    try:
        from gsc_reindex import request_indexing
        result = request_indexing(_sc_v1, url)
        if result.get("success"):
            logger.info(f"Reindex requested: {url}")
        else:
            logger.warning(f"Reindex failed: {url} — {result.get('error')}")
        return jsonify(result)
    except Exception as e:
        logger.error(f"Reindex error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/")
@handle_errors
def index():
    return render_template_string(HTML_TEMPLATE, site=SITE_URL)


# =============================================
# NEW DASHBOARD API ENDPOINTS (v4 — multi-account pipeline)
# =============================================

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)


def _load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}


def _save_json(path, data):
    import tempfile
    path = Path(path)
    try:
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _load_account_quotas():
    """Load account_quotas.json and auto-reset counters if the PT date has changed."""
    quotas = _load_json(DATA_DIR / "account_quotas.json", {"accounts": []})
    today = _today_pt()
    changed = False
    for acct in quotas.get("accounts", []):
        if acct.get("last_reset", "") != today:
            acct["inspect_used"] = 0
            acct["index_used"] = 0
            acct["last_reset"] = today
            changed = True
    if changed:
        _save_json(DATA_DIR / "account_quotas.json", quotas)
    return quotas


def _compute_pipeline_stats(index_db: dict) -> dict:
    """Compute coverage breakdown, rich breakdown, and counts from index_status DB."""
    total = len(index_db)
    indexed = sum(1 for v in index_db.values() if v.get("is_indexed"))

    coverage_breakdown = {}
    for v in index_db.values():
        cov = v.get("coverage", "unknown")
        coverage_breakdown[cov] = coverage_breakdown.get(cov, 0) + 1

    rich_breakdown = {"Product": 0, "MerchantListing": 0, "Review": 0, "None": 0}
    for v in index_db.values():
        rich = v.get("rich_results", [])
        if not rich:
            rich_breakdown["None"] += 1
        for r in rich:
            if "Review" in r:
                rich_breakdown["Review"] += 1
            elif "Merchant" in r:
                rich_breakdown["MerchantListing"] += 1
            elif "Product" in r:
                rich_breakdown["Product"] += 1

    today_pt = _today_pt()
    submitted_today = sum(1 for v in index_db.values()
                          if v.get("submitted_at", "").startswith(today_pt))

    return {
        "total_tracked": total,
        "indexed": indexed,
        "not_indexed": total - indexed,
        "submitted_today": submitted_today,
        "coverage_breakdown": coverage_breakdown,
        "rich_breakdown": rich_breakdown,
    }


@app.route("/dashboard")
@handle_errors
def dashboard_v4():
    from dashboard_template import DASHBOARD_HTML
    return render_template_string(DASHBOARD_HTML,
                                 site=SITE_URL,
                                 brand=BRAND_NAME,
                                 domain=BRAND_DOMAIN)


@app.route("/api/dashboard-data")
@handle_errors
def api_dashboard_data():
    """All dashboard data in one call: DB stats + GSC reports + daily history."""
    index_db = _load_json(DATA_DIR / "index_status.json", {})
    gsc_reports = _load_json(DATA_DIR / "gsc_reports.json", {})
    daily_history = _load_json(DATA_DIR / "daily_history.json", [])
    account_quotas = _load_account_quotas()

    stats = _compute_pipeline_stats(index_db)
    rich = stats["rich_breakdown"]

    return jsonify({
        "stats": {
            **{k: stats[k] for k in ("total_tracked", "indexed", "not_indexed", "submitted_today")},
            "product_snippets": rich.get("Product", 0),
            "merchant_listings": rich.get("MerchantListing", 0),
            "review_snippets": rich.get("Review", 0),
            "no_rich_results": rich.get("None", 0),
        },
        "coverage_breakdown": stats["coverage_breakdown"],
        "rich_breakdown": rich,
        "gsc_reports": gsc_reports,
        "daily_history": daily_history[-90:],
        "accounts": account_quotas.get("accounts", []),
    })


@app.route("/api/tracked-urls")
@handle_errors
def api_tracked_urls():
    """Paginated URL browser with filtering."""
    index_db = _load_json(DATA_DIR / "index_status.json", {})

    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))
    status_filter = request.args.get("status", "")
    search = request.args.get("search", "").lower()
    rich_filter = request.args.get("rich", "")

    items = list(index_db.items())

    if status_filter:
        items = [(url, v) for url, v in items
                 if status_filter.lower() in v.get("coverage", "").lower()]
    if search:
        items = [(url, v) for url, v in items if search in url.lower()]
    if rich_filter:
        if rich_filter == "none":
            items = [(url, v) for url, v in items if not v.get("rich_results")]
        else:
            items = [(url, v) for url, v in items
                     if any(rich_filter.lower() in r.lower()
                            for r in v.get("rich_results", []))]

    sort_by = request.args.get("sort", "checked_at")
    sort_dir = request.args.get("dir", "desc")
    reverse = sort_dir == "desc"
    if sort_by == "url":
        items.sort(key=lambda x: x[0].lower(), reverse=reverse)
    elif sort_by == "coverage":
        items.sort(key=lambda x: x[1].get("coverage", ""), reverse=reverse)
    elif sort_by == "last_crawl":
        items.sort(key=lambda x: x[1].get("last_crawl", ""), reverse=reverse)
    elif sort_by == "submitted_at":
        items.sort(key=lambda x: x[1].get("submitted_at", ""), reverse=reverse)
    else:
        items.sort(key=lambda x: x[1].get("checked_at", ""), reverse=reverse)

    total = len(items)
    start = (page - 1) * per_page
    page_items = items[start:start + per_page]

    return jsonify({
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
        "urls": [{"url": url, **v} for url, v in page_items],
    })


@app.route("/api/smart-sync", methods=["POST"])
@handle_errors
def api_smart_sync():
    """Free bulk index sync via Search Analytics — marks URLs with impressions as indexed."""
    wmt = _wmt_v3 or _get_any_wmt_service()
    if wmt is None:
        return jsonify({"error": "GSC not authenticated"}), 401

    index_db = _load_json(DATA_DIR / "index_status.json", {})

    from datetime import datetime as dt, timedelta
    end = dt.utcnow().strftime("%Y-%m-%d")
    start = (dt.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d")

    try:
        body = {
            "startDate": start,
            "endDate": end,
            "dimensions": ["page"],
            "rowLimit": 25000,
        }
        resp = wmt.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()
        rows = resp.get("rows", [])

        synced = 0
        for row in rows:
            url = row["keys"][0]
            if url in index_db:
                if not index_db[url].get("is_indexed"):
                    index_db[url]["is_indexed"] = True
                    index_db[url]["coverage"] = "Submitted and indexed"
                    index_db[url]["synced_via"] = "search_analytics"
                    synced += 1
            else:
                index_db[url] = {
                    "coverage": "Submitted and indexed",
                    "is_indexed": True,
                    "rich_results": [],
                    "last_crawl": "",
                    "checked_at": end,
                    "synced_via": "search_analytics",
                    "clicks": row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                }
                synced += 1

        _save_json(DATA_DIR / "index_status.json", index_db)

        return jsonify({
            "ok": True,
            "urls_from_analytics": len(rows),
            "newly_synced": synced,
            "total_tracked": len(index_db),
        })
    except Exception as e:
        logger.error(f"Smart sync error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/auto-inspect", methods=["POST"])
@handle_errors
def api_auto_inspect():
    """Batch URL inspection from dashboard — inspects up to 50 URLs."""
    sc = _sc_v1 or _get_any_sc_service()
    if sc is None:
        return jsonify({"error": "GSC not authenticated"}), 401

    data = request.get_json() or {}
    urls = data.get("urls", [])[:50]

    if not urls:
        index_db = _load_json(DATA_DIR / "index_status.json", {})
        urls = [url for url, v in index_db.items()
                if not v.get("is_indexed") and not v.get("coverage", "").startswith("ERROR")][:50]

    quotas = _load_account_quotas()
    results = []
    for url in urls:
        try:
            result = sc.urlInspection().index().inspect(
                body={"inspectionUrl": url, "siteUrl": SITE_URL}
            ).execute()
            idx = result.get("inspectionResult", {}).get("indexStatusResult", {})
            coverage = idx.get("coverageState", "unknown")
            rich = result.get("inspectionResult", {}).get("richResultsResult", {})
            rich_items = [item.get("richResultType", "")
                          for item in rich.get("detectedItems", [])]

            results.append({
                "url": url,
                "coverage": coverage,
                "rich_results": rich_items,
                "is_indexed": "indexed" in coverage.lower() and "not" not in coverage.lower(),
            })
            # Track quota for the first account (auto-inspect uses primary credentials)
            if quotas.get("accounts"):
                quotas["accounts"][0]["inspect_used"] = quotas["accounts"][0].get("inspect_used", 0) + 1
            time.sleep(DELAY)
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower():
                if quotas.get("accounts"):
                    quotas["accounts"][0]["inspect_used"] = quotas["accounts"][0].get("inspect_limit", 2000)
                break
            results.append({"url": url, "coverage": f"ERROR: {err[:80]}", "rich_results": [], "is_indexed": False})
            time.sleep(1)
    _save_json(DATA_DIR / "account_quotas.json", quotas)

    # Update index_status DB
    index_db = _load_json(DATA_DIR / "index_status.json", {})
    from datetime import datetime as dt
    today = dt.utcnow().strftime("%Y-%m-%d")
    for r in results:
        if r["url"] not in index_db:
            index_db[r["url"]] = {}
        index_db[r["url"]].update({
            "coverage": r["coverage"],
            "rich_results": r["rich_results"],
            "is_indexed": r["is_indexed"],
            "checked_at": today,
            "last_crawl": r.get("last_crawl", index_db[r["url"]].get("last_crawl", "")),
        })
    _save_json(DATA_DIR / "index_status.json", index_db)

    return jsonify({"ok": True, "inspected": len(results), "results": results})


@app.route("/api/gsc-reports", methods=["GET", "POST"])
@handle_errors
def api_gsc_reports():
    """Read/update cached GSC report numbers (from GSC UI)."""
    if request.method == "GET":
        reports = _load_json(DATA_DIR / "gsc_reports.json", {})
        return jsonify(reports)
    else:
        data = request.get_json() or {}
        reports = _load_json(DATA_DIR / "gsc_reports.json", {})
        reports.update(data)
        from datetime import datetime as dt
        reports["last_updated"] = dt.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        _save_json(DATA_DIR / "gsc_reports.json", reports)
        return jsonify({"ok": True, "reports": reports})


@app.route("/api/accounts")
@handle_errors
def api_accounts():
    """Show service account status/quota — auto-discovers all credentials files."""
    quotas = _load_account_quotas()
    known = {a.get("credentials_file") for a in quotas.get("accounts", [])}
    for cred_file in sorted(Path(".").glob("credentials*.json")):
        if cred_file.name not in known:
            try:
                cred_data = json.loads(cred_file.read_text())
                if cred_data.get("type") == "service_account":
                    idx = len(quotas["accounts"]) + 1
                    quotas["accounts"].append({
                        "name": f"account-{idx}",
                        "email": cred_data.get("client_email", ""),
                        "credentials_file": cred_file.name,
                        "inspect_used": 0, "inspect_limit": 2000,
                        "index_used": 0, "index_limit": 200,
                        "last_reset": _today_pt(),
                    })
                    known.add(cred_file.name)
            except Exception:
                continue
    for a in quotas.get("accounts", []):
        if not a.get("email") and a.get("credentials_file"):
            try:
                cd = json.loads(Path(a["credentials_file"]).read_text())
                a["email"] = cd.get("client_email", "")
            except Exception:
                pass
    _save_json(DATA_DIR / "account_quotas.json", quotas)
    return jsonify(quotas)


@app.route("/api/accounts/reset", methods=["POST"])
@handle_errors
def api_accounts_reset():
    """Force-reset all account quotas to 0 for today (PT)."""
    quotas = _load_json(DATA_DIR / "account_quotas.json", {"accounts": []})
    today = _today_pt()
    for acct in quotas.get("accounts", []):
        acct["inspect_used"] = 0
        acct["index_used"] = 0
        acct["last_reset"] = today
    _save_json(DATA_DIR / "account_quotas.json", quotas)
    return jsonify({"ok": True, "message": f"All quotas reset for {today} (PT)"})


# =============================================
# LIVE GSC DATA ENDPOINTS (multi-account)
# =============================================

_cached_sc_service = None
_cached_wmt_service = None


def _get_any_sc_service():
    """Get a Search Console v1 service from any available service account."""
    global _cached_sc_service
    if _sc_v1 is not None:
        return _sc_v1
    if _cached_sc_service is not None:
        return _cached_sc_service
    for cred_file in sorted(Path(".").glob("credentials*.json")):
        try:
            cred_data = json.loads(cred_file.read_text())
            if cred_data.get("type") == "service_account":
                from google.oauth2 import service_account as sa_mod
                from googleapiclient.discovery import build as gbuild
                creds = sa_mod.Credentials.from_service_account_file(
                    str(cred_file),
                    scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
                _cached_sc_service = gbuild("searchconsole", "v1", credentials=creds, cache_discovery=False)
                return _cached_sc_service
        except Exception:
            continue
    return None


def _get_any_wmt_service():
    """Get a Webmasters v3 service from any available service account."""
    global _cached_wmt_service
    if _wmt_v3 is not None:
        return _wmt_v3
    if _cached_wmt_service is not None:
        return _cached_wmt_service
    for cred_file in sorted(Path(".").glob("credentials*.json")):
        try:
            cred_data = json.loads(cred_file.read_text())
            if cred_data.get("type") == "service_account":
                from google.oauth2 import service_account as sa_mod
                from googleapiclient.discovery import build as gbuild
                creds = sa_mod.Credentials.from_service_account_file(
                    str(cred_file),
                    scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
                _cached_wmt_service = gbuild("webmasters", "v3", credentials=creds, cache_discovery=False)
                return _cached_wmt_service
        except Exception:
            continue
    return None


# In-memory cache with TTL
_live_cache = {}

def _cached(key, ttl_seconds=300):
    """Check if cached value exists and is fresh."""
    if key in _live_cache:
        val, ts = _live_cache[key]
        if time.time() - ts < ttl_seconds:
            return val
    return None

def _set_cache(key, val):
    _live_cache[key] = (val, time.time())


@app.route("/api/live/sitemap-stats")
@handle_errors
def api_live_sitemap_stats():
    """LIVE: Get total submitted/indexed counts from sitemaps API."""
    cached = _cached("sitemap_stats", 600)
    if cached:
        return jsonify(cached)

    wmt = _get_any_wmt_service()
    if not wmt:
        return jsonify({"error": "No GSC service available"}), 401

    try:
        resp = wmt.sitemaps().list(siteUrl=SITE_URL).execute()
        sitemaps = resp.get("sitemap", [])
        total_submitted = 0
        total_indexed = 0
        sitemap_details = []
        for sm in sitemaps:
            submitted = sum(int(c.get("submitted", 0)) for c in sm.get("contents", []))
            indexed = sum(int(c.get("indexed", 0)) for c in sm.get("contents", []))
            total_submitted += submitted
            total_indexed += indexed
            sitemap_details.append({
                "path": sm.get("path", ""),
                "submitted": submitted,
                "indexed": indexed,
                "gap": submitted - indexed,
                "last_submitted": sm.get("lastSubmitted", ""),
                "last_downloaded": sm.get("lastDownloaded", ""),
            })

        result = {
            "total_submitted": total_submitted,
            "total_indexed": total_indexed,
            "total_not_indexed": total_submitted - total_indexed,
            "index_rate": round(total_indexed / total_submitted * 100, 1) if total_submitted else 0,
            "sitemaps": sitemap_details,
            "sitemap_count": len(sitemap_details),
            "source": "live_sitemaps_api",
            "fetched_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
        _set_cache("sitemap_stats", result)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Sitemap stats error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/live/snippet-stats")
@handle_errors
def api_live_snippet_stats():
    """LIVE: Site-wide snippet/rich result stats from Search Analytics."""
    cached = _cached("snippet_stats", 600)
    if cached:
        return jsonify(cached)

    wmt = _get_any_wmt_service()
    if not wmt:
        return jsonify({"error": "No GSC service available"}), 401

    try:
        end = (datetime.datetime.utcnow() - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        start = (datetime.datetime.utcnow() - datetime.timedelta(days=90)).strftime("%Y-%m-%d")

        body = {
            "startDate": start,
            "endDate": end,
            "dimensions": ["searchAppearance"],
            "aggregationType": "auto",
            "type": "web",
            "rowLimit": 25,
            "dataState": "final",
        }
        resp = wmt.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()

        snippet_types = {}
        total_impressions = 0
        total_clicks = 0
        for row in resp.get("rows", []):
            appearance = row["keys"][0]
            impr = int(row.get("impressions", 0))
            clicks = int(row.get("clicks", 0))
            ctr = row.get("ctr", 0)
            pos = row.get("position", 0)
            snippet_types[appearance] = {
                "impressions": impr,
                "clicks": clicks,
                "ctr": round(ctr * 100, 2),
                "avg_position": round(pos, 1),
            }
            total_impressions += impr
            total_clicks += clicks

        for s in snippet_types.values():
            s["impr_share"] = round(s["impressions"] / total_impressions * 100, 1) if total_impressions else 0

        result = {
            "snippet_types": snippet_types,
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "product_snippets": snippet_types.get("PRODUCT_SNIPPET", {}).get("impressions", 0),
            "merchant_listings": snippet_types.get("MERCHANT_LISTINGS", {}).get("impressions", 0),
            "review_snippets": snippet_types.get("REVIEW_SNIPPET", {}).get("impressions", 0),
            "days_analyzed": 90,
            "source": "live_search_analytics",
            "fetched_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
        _set_cache("snippet_stats", result)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Snippet stats error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/live/search-performance")
@handle_errors
def api_live_search_performance():
    """LIVE: Site-wide search performance (clicks, impressions, CTR, position) over time."""
    cached = _cached("search_performance", 600)
    if cached:
        return jsonify(cached)

    wmt = _get_any_wmt_service()
    if not wmt:
        return jsonify({"error": "No GSC service available"}), 401

    try:
        end = (datetime.datetime.utcnow() - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        start = (datetime.datetime.utcnow() - datetime.timedelta(days=90)).strftime("%Y-%m-%d")

        body = {
            "startDate": start,
            "endDate": end,
            "dimensions": ["date"],
            "aggregationType": "auto",
            "type": "web",
            "rowLimit": 25000,
            "dataState": "final",
        }
        resp = wmt.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()

        daily = []
        totals = {"clicks": 0, "impressions": 0}
        for row in resp.get("rows", []):
            d = {
                "date": row["keys"][0],
                "clicks": int(row.get("clicks", 0)),
                "impressions": int(row.get("impressions", 0)),
                "ctr": round(row.get("ctr", 0) * 100, 2),
                "position": round(row.get("position", 0), 1),
            }
            daily.append(d)
            totals["clicks"] += d["clicks"]
            totals["impressions"] += d["impressions"]

        daily.sort(key=lambda x: x["date"])

        result = {
            "daily": daily,
            "totals": {
                "clicks": totals["clicks"],
                "impressions": totals["impressions"],
                "avg_ctr": round(totals["clicks"] / totals["impressions"] * 100, 2) if totals["impressions"] else 0,
            },
            "days": len(daily),
            "source": "live_search_analytics",
            "fetched_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
        _set_cache("search_performance", result)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Search performance error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/live/top-queries")
@handle_errors
def api_live_top_queries():
    """LIVE: Top search queries with clicks, impressions, CTR, position."""
    cached = _cached("top_queries", 600)
    if cached:
        return jsonify(cached)

    wmt = _get_any_wmt_service()
    if not wmt:
        return jsonify({"error": "No GSC service available"}), 401

    try:
        end = (datetime.datetime.utcnow() - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        start = (datetime.datetime.utcnow() - datetime.timedelta(days=28)).strftime("%Y-%m-%d")

        body = {
            "startDate": start,
            "endDate": end,
            "dimensions": ["query"],
            "aggregationType": "auto",
            "type": "web",
            "rowLimit": 200,
            "dataState": "final",
        }
        resp = wmt.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()

        queries = []
        for row in resp.get("rows", []):
            queries.append({
                "query": row["keys"][0],
                "clicks": int(row.get("clicks", 0)),
                "impressions": int(row.get("impressions", 0)),
                "ctr": round(row.get("ctr", 0) * 100, 2),
                "position": round(row.get("position", 0), 1),
            })

        result = {
            "queries": queries,
            "total": len(queries),
            "period": f"{start} to {end}",
            "source": "live_search_analytics",
            "fetched_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
        _set_cache("top_queries", result)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Top queries error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/live/top-pages")
@handle_errors
def api_live_top_pages():
    """LIVE: Top performing pages with clicks, impressions, CTR, position."""
    cached = _cached("top_pages", 600)
    if cached:
        return jsonify(cached)

    wmt = _get_any_wmt_service()
    if not wmt:
        return jsonify({"error": "No GSC service available"}), 401

    try:
        end = (datetime.datetime.utcnow() - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        start = (datetime.datetime.utcnow() - datetime.timedelta(days=28)).strftime("%Y-%m-%d")

        body = {
            "startDate": start,
            "endDate": end,
            "dimensions": ["page"],
            "aggregationType": "byPage",
            "type": "web",
            "rowLimit": 200,
            "dataState": "final",
        }
        resp = wmt.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()

        pages = []
        for row in resp.get("rows", []):
            pages.append({
                "page": row["keys"][0],
                "clicks": int(row.get("clicks", 0)),
                "impressions": int(row.get("impressions", 0)),
                "ctr": round(row.get("ctr", 0) * 100, 2),
                "position": round(row.get("position", 0), 1),
            })

        result = {
            "pages": pages,
            "total": len(pages),
            "period": f"{start} to {end}",
            "source": "live_search_analytics",
            "fetched_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
        _set_cache("top_pages", result)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Top pages error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/live/device-stats")
@handle_errors
def api_live_device_stats():
    """LIVE: Performance breakdown by device type."""
    cached = _cached("device_stats", 600)
    if cached:
        return jsonify(cached)

    wmt = _get_any_wmt_service()
    if not wmt:
        return jsonify({"error": "No GSC service available"}), 401

    try:
        end = (datetime.datetime.utcnow() - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        start = (datetime.datetime.utcnow() - datetime.timedelta(days=28)).strftime("%Y-%m-%d")

        body = {
            "startDate": start,
            "endDate": end,
            "dimensions": ["device"],
            "aggregationType": "auto",
            "type": "web",
            "rowLimit": 10,
            "dataState": "final",
        }
        resp = wmt.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()

        devices = {}
        for row in resp.get("rows", []):
            devices[row["keys"][0]] = {
                "clicks": int(row.get("clicks", 0)),
                "impressions": int(row.get("impressions", 0)),
                "ctr": round(row.get("ctr", 0) * 100, 2),
                "position": round(row.get("position", 0), 1),
            }

        result = {
            "devices": devices,
            "source": "live_search_analytics",
            "fetched_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
        _set_cache("device_stats", result)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Device stats error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/live/country-stats")
@handle_errors
def api_live_country_stats():
    """LIVE: Performance breakdown by country."""
    cached = _cached("country_stats", 600)
    if cached:
        return jsonify(cached)

    wmt = _get_any_wmt_service()
    if not wmt:
        return jsonify({"error": "No GSC service available"}), 401

    try:
        end = (datetime.datetime.utcnow() - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        start = (datetime.datetime.utcnow() - datetime.timedelta(days=28)).strftime("%Y-%m-%d")

        body = {
            "startDate": start,
            "endDate": end,
            "dimensions": ["country"],
            "aggregationType": "auto",
            "type": "web",
            "rowLimit": 50,
            "dataState": "final",
        }
        resp = wmt.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()

        countries = []
        for row in resp.get("rows", []):
            countries.append({
                "country": row["keys"][0],
                "clicks": int(row.get("clicks", 0)),
                "impressions": int(row.get("impressions", 0)),
                "ctr": round(row.get("ctr", 0) * 100, 2),
                "position": round(row.get("position", 0), 1),
            })

        result = {
            "countries": countries,
            "total": len(countries),
            "source": "live_search_analytics",
            "fetched_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
        _set_cache("country_stats", result)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Country stats error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/live/all")
@handle_errors
def api_live_all():
    """LIVE: Combined endpoint — fetches all live data in one call for the dashboard."""
    errors = {}
    results = {}

    # DB stats (always available)
    index_db = _load_json(DATA_DIR / "index_status.json", {})
    account_quotas = _load_account_quotas()
    daily_history = _load_json(DATA_DIR / "daily_history.json", [])

    results["pipeline"] = _compute_pipeline_stats(index_db)
    today = _today_pt()
    accts = account_quotas.get("accounts", [])
    known_creds = {a.get("credentials_file") for a in accts}
    for cred_file in sorted(Path(".").glob("credentials*.json")):
        if cred_file.name not in known_creds:
            try:
                cd = json.loads(cred_file.read_text())
                if cd.get("type") == "service_account":
                    accts.append({
                        "name": f"account-{len(accts)+1}",
                        "email": cd.get("client_email", ""),
                        "credentials_file": cred_file.name,
                        "inspect_used": 0, "inspect_limit": 2000,
                        "index_used": 0, "index_limit": 200,
                        "last_reset": today,
                    })
                    known_creds.add(cred_file.name)
            except Exception:
                continue
    for a in accts:
        if not a.get("email") and a.get("credentials_file"):
            try:
                cd = json.loads(Path(a["credentials_file"]).read_text())
                a["email"] = cd.get("client_email", "")
            except Exception:
                pass
    results["accounts"] = accts
    results["daily_history"] = daily_history[-90:]

    # Live GSC data (with graceful fallback)
    wmt = _get_any_wmt_service()

    if wmt:
        try:
            resp = wmt.sitemaps().list(siteUrl=SITE_URL).execute()
            sitemaps = resp.get("sitemap", [])
            total_submitted = sum(sum(int(c.get("submitted", 0)) for c in sm.get("contents", [])) for sm in sitemaps)
            total_indexed_sm = sum(sum(int(c.get("indexed", 0)) for c in sm.get("contents", [])) for sm in sitemaps)
            results["sitemaps"] = {
                "total_submitted": total_submitted,
                "total_indexed": total_indexed_sm,
                "total_not_indexed": total_submitted - total_indexed_sm,
                "index_rate": round(total_indexed_sm / total_submitted * 100, 1) if total_submitted else 0,
                "details": [{"path": sm.get("path",""), "submitted": sum(int(c.get("submitted",0)) for c in sm.get("contents",[])), "indexed": sum(int(c.get("indexed",0)) for c in sm.get("contents",[]))} for sm in sitemaps],
            }
        except Exception as e:
            errors["sitemaps"] = str(e)

    if wmt:
        end = (datetime.datetime.utcnow() - datetime.timedelta(days=3)).strftime("%Y-%m-%d")

        # Count ALL indexed pages using paginated Search Analytics queries
        # The API caps at 25K rows per request, but startRow lets us paginate
        try:
            cached_idx = _cached("indexed_page_count", 600)
            if cached_idx is not None:
                indexed_from_sa = cached_idx
            else:
                start90 = (datetime.datetime.utcnow() - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
                all_pages = set()
                start_row = 0
                while True:
                    body = {"startDate": start90, "endDate": end, "dimensions": ["page"],
                            "aggregationType": "auto", "type": "web", "rowLimit": 25000,
                            "startRow": start_row, "dataState": "final"}
                    resp = wmt.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()
                    rows = resp.get("rows", [])
                    if not rows:
                        break
                    for row in rows:
                        all_pages.add(row["keys"][0])
                    if len(rows) < 25000:
                        break
                    start_row += 25000
                indexed_from_sa = len(all_pages)
                _set_cache("indexed_page_count", indexed_from_sa)
            if "sitemaps" in results:
                sm_data = results["sitemaps"]
                if sm_data["total_indexed"] == 0 and indexed_from_sa > 0:
                    sm_data["indexed_from_search"] = indexed_from_sa
                    sm_data["total_indexed"] = indexed_from_sa
                    sm_data["total_not_indexed"] = max(0, sm_data["total_submitted"] - indexed_from_sa)
                    sm_data["index_rate"] = round(indexed_from_sa / sm_data["total_submitted"] * 100, 1) if sm_data["total_submitted"] else 0
                    sm_data["index_source"] = "search_analytics_paginated"
        except Exception as e:
            errors["indexed_page_count"] = str(e)

        # Snippet stats
        try:
            start90 = (datetime.datetime.utcnow() - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
            body = {"startDate": start90, "endDate": end, "dimensions": ["searchAppearance"], "aggregationType": "auto", "type": "web", "rowLimit": 25, "dataState": "final"}
            resp = wmt.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()
            snippet_types = {}
            for row in resp.get("rows", []):
                snippet_types[row["keys"][0]] = {"impressions": int(row.get("impressions",0)), "clicks": int(row.get("clicks",0)), "ctr": round(row.get("ctr",0)*100,2), "avg_position": round(row.get("position",0),1)}
            results["snippets"] = snippet_types
        except Exception as e:
            errors["snippets"] = str(e)

        # Search performance (last 28 days daily)
        try:
            start28 = (datetime.datetime.utcnow() - datetime.timedelta(days=28)).strftime("%Y-%m-%d")
            body = {"startDate": start28, "endDate": end, "dimensions": ["date"], "aggregationType": "auto", "type": "web", "rowLimit": 25000, "dataState": "final"}
            resp = wmt.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()
            perf_daily = sorted([{"date": r["keys"][0], "clicks": int(r.get("clicks",0)), "impressions": int(r.get("impressions",0)), "ctr": round(r.get("ctr",0)*100,2), "position": round(r.get("position",0),1)} for r in resp.get("rows",[])], key=lambda x: x["date"])
            total_clicks = sum(d["clicks"] for d in perf_daily)
            total_impr = sum(d["impressions"] for d in perf_daily)
            results["search_performance"] = {
                "daily": perf_daily,
                "total_clicks": total_clicks,
                "total_impressions": total_impr,
                "avg_ctr": round(total_clicks / total_impr * 100, 2) if total_impr else 0,
            }
        except Exception as e:
            errors["search_performance"] = str(e)

        # Top queries
        try:
            start28 = (datetime.datetime.utcnow() - datetime.timedelta(days=28)).strftime("%Y-%m-%d")
            body = {"startDate": start28, "endDate": end, "dimensions": ["query"], "aggregationType": "auto", "type": "web", "rowLimit": 100, "dataState": "final"}
            resp = wmt.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()
            results["top_queries"] = [{"query": r["keys"][0], "clicks": int(r.get("clicks",0)), "impressions": int(r.get("impressions",0)), "ctr": round(r.get("ctr",0)*100,2), "position": round(r.get("position",0),1)} for r in resp.get("rows",[])]
        except Exception as e:
            errors["top_queries"] = str(e)

        # Top pages
        try:
            start28 = (datetime.datetime.utcnow() - datetime.timedelta(days=28)).strftime("%Y-%m-%d")
            body = {"startDate": start28, "endDate": end, "dimensions": ["page"], "aggregationType": "auto", "type": "web", "rowLimit": 200, "dataState": "final"}
            resp = wmt.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()
            results["top_pages"] = [{"page": r["keys"][0], "clicks": int(r.get("clicks",0)), "impressions": int(r.get("impressions",0)), "ctr": round(r.get("ctr",0)*100,2), "position": round(r.get("position",0),1)} for r in resp.get("rows",[])]
        except Exception as e:
            errors["top_pages"] = str(e)

        # Device breakdown
        try:
            start28 = (datetime.datetime.utcnow() - datetime.timedelta(days=28)).strftime("%Y-%m-%d")
            body = {"startDate": start28, "endDate": end, "dimensions": ["device"], "aggregationType": "auto", "type": "web", "rowLimit": 10, "dataState": "final"}
            resp = wmt.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()
            results["devices"] = {r["keys"][0]: {"clicks": int(r.get("clicks",0)), "impressions": int(r.get("impressions",0)), "ctr": round(r.get("ctr",0)*100,2), "position": round(r.get("position",0),1)} for r in resp.get("rows",[])}
        except Exception as e:
            errors["devices"] = str(e)

        # Country breakdown
        try:
            start28 = (datetime.datetime.utcnow() - datetime.timedelta(days=28)).strftime("%Y-%m-%d")
            body = {"startDate": start28, "endDate": end, "dimensions": ["country"], "aggregationType": "auto", "type": "web", "rowLimit": 30, "dataState": "final"}
            resp = wmt.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()
            results["countries"] = [{"country": r["keys"][0], "clicks": int(r.get("clicks",0)), "impressions": int(r.get("impressions",0)), "ctr": round(r.get("ctr",0)*100,2), "position": round(r.get("position",0),1)} for r in resp.get("rows",[])]
        except Exception as e:
            errors["countries"] = str(e)

    results["errors"] = errors
    results["is_live"] = bool(_sc_v1 or wmt)
    results["fetched_at"] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    return jsonify(results)


@app.route("/api/cache/clear", methods=["POST"])
@handle_errors
def api_cache_clear():
    """Clear in-memory API cache to force fresh data."""
    global _live_cache
    _live_cache = {}
    return jsonify({"ok": True, "message": "Cache cleared"})


@app.route("/api/urls-by-category")
@handle_errors
def api_urls_by_category():
    """URLs grouped by coverage category with pagination."""
    index_db = _load_json(DATA_DIR / "index_status.json", {})
    category = request.args.get("category", "")
    rich_filter = request.args.get("rich", "")
    action = request.args.get("action", "")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))

    items = list(index_db.items())

    if category:
        items = [(url, v) for url, v in items if v.get("coverage", "").lower() == category.lower()]
    if rich_filter:
        if rich_filter == "none":
            items = [(url, v) for url, v in items if not v.get("rich_results")]
        else:
            items = [(url, v) for url, v in items if any(rich_filter.lower() in r.lower() for r in v.get("rich_results", []))]
    if action == "submit":
        items = [(url, v) for url, v in items if not v.get("is_indexed") and any(
            k in v.get("coverage", "").lower() for k in ("unknown", "discovered", "crawled"))]
    elif action == "indexed":
        items = [(url, v) for url, v in items if v.get("is_indexed")]
    elif action == "not_indexed":
        items = [(url, v) for url, v in items if not v.get("is_indexed")]

    sort_by = request.args.get("sort", "")
    sort_dir = request.args.get("dir", "desc")
    if sort_by == "checked_at":
        items.sort(key=lambda x: x[1].get("checked_at", ""), reverse=(sort_dir == "desc"))
    elif sort_by == "coverage":
        items.sort(key=lambda x: x[1].get("coverage", ""), reverse=(sort_dir == "desc"))
    elif sort_by == "submitted_at":
        items.sort(key=lambda x: x[1].get("submitted_at", ""), reverse=(sort_dir == "desc"))
    elif sort_by == "last_crawl":
        items.sort(key=lambda x: x[1].get("last_crawl_time", ""), reverse=(sort_dir == "desc"))
    elif sort_by == "check_count":
        items.sort(key=lambda x: x[1].get("check_count", 0), reverse=(sort_dir == "desc"))

    total = len(items)
    start = (page - 1) * per_page
    page_items = items[start:start + per_page]

    return jsonify({
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
        "urls": [{"url": url, **v} for url, v in page_items],
    })


@app.route("/api/batch-submit", methods=["POST"])
@handle_errors
def api_batch_submit():
    """Submit not-indexed URLs for indexing via Google Indexing API."""
    data = request.get_json() or {}
    category = data.get("category", "")
    limit = min(int(data.get("limit", 50)), 200)

    index_db = _load_json(DATA_DIR / "index_status.json", {})
    account_quotas = _load_account_quotas()

    # Find eligible URLs
    eligible = []
    for url, v in index_db.items():
        if v.get("is_indexed"):
            continue
        cov = v.get("coverage", "").lower()
        if not any(k in cov for k in ("unknown", "discovered", "crawled")):
            continue
        if category and category.lower() not in cov:
            continue
        if v.get("submitted_at", ""):
            continue
        eligible.append(url)
    eligible = eligible[:limit]

    if not eligible:
        return jsonify({"ok": True, "submitted": 0, "message": "No eligible URLs to submit"})

    # Find an account with quota
    sc_service = None
    acct_name = None
    for acct in account_quotas.get("accounts", []):
        if acct.get("index_used", 0) < acct.get("index_limit", 200):
            cred_file = acct.get("credentials_file", "")
            if cred_file and Path(cred_file).exists():
                try:
                    from google.oauth2 import service_account
                    from googleapiclient.discovery import build
                    creds = service_account.Credentials.from_service_account_file(
                        cred_file, scopes=["https://www.googleapis.com/auth/indexing"])
                    sc_service = build("indexing", "v3", credentials=creds, cache_discovery=False)
                    acct_name = acct.get("name", cred_file)
                    break
                except Exception:
                    continue

    if not sc_service:
        return jsonify({"error": "No service account with remaining indexing quota"}), 400

    submitted = 0
    errors = []
    hit_quota = False
    today = _today_pt()
    for url in eligible:
        try:
            sc_service.urlNotifications().publish(
                body={"url": url, "type": "URL_UPDATED"}
            ).execute()
            index_db[url]["submitted_at"] = today
            submitted += 1
            time.sleep(0.5)
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower():
                hit_quota = True
                for acct in account_quotas.get("accounts", []):
                    if acct.get("name") == acct_name:
                        acct["index_used"] = acct.get("index_limit", 200)
                        break
                break
            errors.append({"url": url, "error": err[:100]})

    _save_json(DATA_DIR / "index_status.json", index_db)

    if not hit_quota:
        for acct in account_quotas.get("accounts", []):
            if acct.get("name") == acct_name:
                acct["index_used"] = acct.get("index_used", 0) + submitted
                break
    _save_json(DATA_DIR / "account_quotas.json", account_quotas)

    return jsonify({
        "ok": True,
        "submitted": submitted,
        "errors": errors,
        "account": acct_name,
        "remaining_eligible": len(eligible) - submitted,
    })


# ─────────────────────────────────────────────
# BULK QUEUE — inspect + auto-submit
# ─────────────────────────────────────────────
_bulk_queue = {
    "state": "idle",        # idle | running | paused | done
    "urls": [],
    "results": [],
    "processed": 0,
    "errors": 0,
    "total": 0,
    "current_url": "",
}
_bulk_lock = threading.Lock()
_bulk_pause = threading.Event()
_bulk_pause.set()
_bulk_thread = None


def _bulk_worker():
    """Background worker: inspect each URL, submit if not indexed."""
    queue = _bulk_queue
    account_quotas = _load_account_quotas()
    index_db = _load_json(DATA_DIR / "index_status.json", {})

    idx_service = None
    idx_acct = None
    for acct in account_quotas.get("accounts", []):
        if acct.get("index_used", 0) < acct.get("index_limit", 200):
            cred_file = acct.get("credentials_file", "")
            if cred_file and Path(cred_file).exists():
                try:
                    from google.oauth2 import service_account
                    from googleapiclient.discovery import build as gbuild
                    creds = service_account.Credentials.from_service_account_file(
                        cred_file, scopes=["https://www.googleapis.com/auth/indexing"])
                    idx_service = gbuild("indexing", "v3", credentials=creds, cache_discovery=False)
                    idx_acct = acct
                    break
                except Exception:
                    continue

    insp_service = None
    insp_acct_file = None
    for acct in account_quotas.get("accounts", []):
        if acct.get("inspect_used", 0) >= acct.get("inspect_limit", 2000):
            continue
        cred_file = acct.get("credentials_file", "")
        if cred_file and Path(cred_file).exists():
            try:
                from google.oauth2 import service_account
                from googleapiclient.discovery import build as gbuild
                creds = service_account.Credentials.from_service_account_file(
                    cred_file, scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
                insp_service = gbuild("searchconsole", "v1", credentials=creds, cache_discovery=False)
                insp_acct_file = cred_file
                break
            except Exception:
                continue

    start_from = queue.get("processed", 0)
    for i, url in enumerate(queue["urls"]):
        if i < start_from:
            continue
        _bulk_pause.wait()
        with _bulk_lock:
            if queue["state"] not in ("running", "paused"):
                break
            queue["current_url"] = url

        result = {"url": url, "status": "pending", "coverage": "", "action": "", "error": ""}

        if not insp_service:
            result["status"] = "error"
            result["error"] = "No inspection service available"
            with _bulk_lock:
                queue["results"].append(result)
                queue["errors"] += 1
                queue["processed"] = i + 1
            continue

        try:
            resp = insp_service.urlInspection().index().inspect(
                body={"inspectionUrl": url, "siteUrl": SITE_URL}
            ).execute()
            idx_result = resp.get("inspectionResult", {}).get("indexStatusResult", {})
            coverage = idx_result.get("coverageState", "unknown")
            is_indexed = "indexed" in coverage.lower() and "not" not in coverage.lower()
            result["coverage"] = coverage

            for a in account_quotas.get("accounts", []):
                if a.get("credentials_file") == insp_acct_file:
                    a["inspect_used"] = a.get("inspect_used", 0) + 1
                    break

            today = _today_pt()
            index_db[url] = {
                "coverage": coverage,
                "is_indexed": is_indexed,
                "checked_at": today,
                "last_crawl": idx_result.get("lastCrawlTime", ""),
                "rich_results": [
                    it.get("richResultType", "")
                    for it in resp.get("inspectionResult", {}).get(
                        "richResultsResult", {}).get("detectedItems", [])
                ],
            }

            if is_indexed:
                result["status"] = "indexed"
                result["action"] = "Already indexed"
            else:
                if idx_service and idx_acct and idx_acct.get("index_used", 0) < idx_acct.get("index_limit", 200):
                    try:
                        idx_service.urlNotifications().publish(
                            body={"url": url, "type": "URL_UPDATED"}
                        ).execute()
                        result["status"] = "submitted"
                        result["action"] = "Submitted for indexing"
                        index_db[url]["submitted_at"] = today
                        idx_acct["index_used"] = idx_acct.get("index_used", 0) + 1
                    except Exception as se:
                        result["status"] = "inspect_only"
                        result["action"] = f"Not indexed — submit failed: {str(se)[:60]}"
                else:
                    result["status"] = "inspect_only"
                    result["action"] = "Not indexed — no submit quota"

        except Exception as e:
            err = str(e)
            result["status"] = "error"
            result["error"] = err[:120]
            if "429" in err or "quota" in err.lower():
                result["error"] = "Rate limited — quota exceeded"
                for a in account_quotas.get("accounts", []):
                    if a.get("credentials_file") == insp_acct_file:
                        a["inspect_used"] = a["inspect_limit"]
                        break
                _save_json(DATA_DIR / "account_quotas.json", account_quotas)

        with _bulk_lock:
            queue["results"].append(result)
            queue["processed"] = i + 1
            if result["status"] == "error":
                queue["errors"] += 1
            queue["current_url"] = ""

        if (i + 1) % 10 == 0:
            _save_json(DATA_DIR / "account_quotas.json", account_quotas)
            _save_json(DATA_DIR / "index_status.json", index_db)

        time.sleep(DELAY)

    _save_json(DATA_DIR / "index_status.json", index_db)
    _save_json(DATA_DIR / "account_quotas.json", account_quotas)

    with _bulk_lock:
        queue["state"] = "done"
        queue["current_url"] = ""


@app.route("/api/bulk-queue", methods=["POST"])
@handle_errors
def api_bulk_queue_start():
    """Start bulk URL queue — inspect each, submit non-indexed."""
    data = request.get_json() or {}
    urls = data.get("urls", [])
    urls = [u.strip() for u in urls if u.strip() and u.strip().startswith("http")]

    if not urls:
        return jsonify({"error": "No valid URLs provided"}), 400
    if len(urls) > 500:
        urls = urls[:500]

    with _bulk_lock:
        if _bulk_queue["state"] in ("running", "paused"):
            return jsonify({"error": "Queue already active — stop or clear it first"}), 409
        _bulk_queue.update({
            "state": "running",
            "urls": urls,
            "results": [],
            "processed": 0,
            "errors": 0,
            "total": len(urls),
            "current_url": "",
        })
    _bulk_pause.set()
    global _bulk_thread
    _bulk_thread = threading.Thread(target=_bulk_worker, daemon=True)
    _bulk_thread.start()
    return jsonify({"ok": True, "queued": len(urls)})


@app.route("/api/bulk-queue/status")
@handle_errors
def api_bulk_queue_status():
    """Poll bulk queue progress."""
    with _bulk_lock:
        return jsonify({
            "state": _bulk_queue["state"],
            "total": _bulk_queue["total"],
            "processed": _bulk_queue["processed"],
            "errors": _bulk_queue["errors"],
            "current_url": _bulk_queue["current_url"],
            "results": _bulk_queue["results"],
        })


@app.route("/api/bulk-queue/pause", methods=["POST"])
@handle_errors
def api_bulk_queue_pause():
    """Pause the running bulk queue."""
    with _bulk_lock:
        if _bulk_queue["state"] != "running":
            return jsonify({"error": "Queue not running"}), 400
        _bulk_queue["state"] = "paused"
    _bulk_pause.clear()
    return jsonify({"ok": True})


@app.route("/api/bulk-queue/resume", methods=["POST"])
@handle_errors
def api_bulk_queue_resume():
    """Resume the paused bulk queue."""
    global _bulk_thread
    with _bulk_lock:
        if _bulk_queue["state"] != "paused":
            return jsonify({"error": "Queue not paused"}), 400
        _bulk_queue["state"] = "running"
    _bulk_pause.set()
    with _bulk_lock:
        if _bulk_thread is None or not _bulk_thread.is_alive():
            _bulk_thread = threading.Thread(target=_bulk_worker, daemon=True)
            _bulk_thread.start()
    return jsonify({"ok": True})


@app.route("/api/bulk-queue/stop", methods=["POST"])
@handle_errors
def api_bulk_queue_stop():
    """Stop and clear the bulk queue."""
    with _bulk_lock:
        _bulk_queue["state"] = "stopped"
        _bulk_queue["current_url"] = ""
    _bulk_pause.set()
    return jsonify({"ok": True})


@app.route("/api/bulk-queue/clear", methods=["POST"])
@handle_errors
def api_bulk_queue_clear():
    """Clear queue data and reset to idle."""
    with _bulk_lock:
        _bulk_queue.update({
            "state": "idle",
            "urls": [],
            "results": [],
            "processed": 0,
            "errors": 0,
            "total": 0,
            "current_url": "",
        })
    return jsonify({"ok": True})


@app.route("/api/extension/gsc-data", methods=["GET"])
@handle_errors
def api_extension_gsc_data_get():
    """Return the latest scraped GSC data from the extension."""
    data = _load_json(DATA_DIR / "extension_gsc_data.json", {})
    return jsonify(data)


@app.route("/api/extension/gsc-data", methods=["POST"])
@handle_errors
def api_extension_gsc_data():
    """Receive scraped GSC data from the Chrome extension and save it."""
    data = request.get_json() or {}
    from datetime import datetime as dt
    data["source"] = "chrome_extension"
    data["received_at"] = dt.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    _save_json(DATA_DIR / "extension_gsc_data.json", data)

    reports = _load_json(DATA_DIR / "gsc_reports.json", {})
    if data.get("pages"):
        p = data["pages"]
        if p.get("indexed"): reports["indexed_count"] = p["indexed"]
        if p.get("notIndexed"): reports["not_indexed_count"] = p["notIndexed"]
    if data.get("performance"):
        perf = data["performance"]
        if perf.get("clicks"): reports["total_clicks"] = perf["clicks"]
        if perf.get("impressions"): reports["total_impressions"] = perf["impressions"]
        if perf.get("ctr"): reports["avg_ctr"] = perf["ctr"]
        if perf.get("position"): reports["avg_position"] = perf["position"]
    if data.get("merchantListings"):
        ml = data["merchantListings"]
        reports["merchant_valid"] = ml.get("valid", "")
        reports["merchant_errors"] = ml.get("error", "")
    if data.get("productSnippets"):
        ps = data["productSnippets"]
        reports["product_snippet_valid"] = ps.get("valid", "")
        reports["product_snippet_errors"] = ps.get("error", "")
    if data.get("reviewSnippets"):
        rs = data["reviewSnippets"]
        reports["review_snippet_valid"] = rs.get("valid", "")
        reports["review_snippet_errors"] = rs.get("error", "")
    if data.get("links"):
        lk = data["links"]
        reports["external_links"] = lk.get("externalLinks", "")
        reports["internal_links"] = lk.get("internalLinks", "")
    reports["last_updated"] = dt.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    _save_json(DATA_DIR / "gsc_reports.json", reports)

    return jsonify({"ok": True, "saved": list(data.keys())})


@app.route("/api/extension/bulk-results", methods=["POST"])
@handle_errors
def api_extension_bulk_results():
    """Receive bulk indexing results from the Chrome extension."""
    data = request.get_json() or {}
    from datetime import datetime as dt
    data["received_at"] = dt.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    _save_json(DATA_DIR / "bulk_indexing_results.json", data)

    # Update index_status.json with inspection results
    index_db = _load_json(DATA_DIR / "index_status.json", {})
    for r in data.get("results", []):
        url = r.get("url", "")
        if not url:
            continue
        status = r.get("status", "")
        if url not in index_db:
            index_db[url] = {}
        index_db[url].update({
            "is_indexed": status == "indexed",
            "coverage": r.get("coverage", ""),
            "status": status,
            "action": r.get("action", ""),
            "rich_results": r.get("richResults", []),
            "last_crawl": r.get("lastCrawl", index_db[url].get("last_crawl", "")),
            "checked_at": _today_pt(),
            "synced_via": "extension",
        })
    _save_json(DATA_DIR / "index_status.json", index_db)

    return jsonify({
        "ok": True,
        "total": len(data.get("results", [])),
        "indexed": sum(1 for r in data.get("results", []) if r.get("status") == "indexed"),
    })


@app.route("/api/bulk-results")
@handle_errors
def api_bulk_results():
    """Return the latest bulk indexing results."""
    data = _load_json(DATA_DIR / "bulk_indexing_results.json", {})
    return jsonify(data)


@app.route("/api/classifications")
@handle_errors
def api_classifications():
    """URL classification summary — what to inspect, submit, track snippets for."""
    classifications = _load_json(DATA_DIR / "url_classifications.json", {})
    index_db = _load_json(DATA_DIR / "index_status.json", {})

    # Live counts from index_status
    total = len(index_db)
    indexed = sum(1 for v in index_db.values() if v.get("is_indexed"))
    not_indexed = total - indexed

    # Coverage action breakdown
    action_counts = {"submit": 0, "snippet": 0, "search": 0, "skip": 0}
    coverage_actions = {}
    for url, info in index_db.items():
        coverage = info.get("coverage", "Unknown")
        is_indexed = info.get("is_indexed", False)

        # Should submit?
        cov_lower = coverage.lower()
        if not is_indexed and ("unknown" in cov_lower or "discovered" in cov_lower or "crawled" in cov_lower):
            action_counts["submit"] += 1
        if is_indexed and "/products/" in url:
            action_counts["snippet"] += 1
        if is_indexed:
            action_counts["search"] += 1

        if coverage not in coverage_actions:
            coverage_actions[coverage] = {"count": 0, "inspect": True, "submit": False, "snippet": False}
        coverage_actions[coverage]["count"] += 1
        if is_indexed and "/products/" in url:
            coverage_actions[coverage]["snippet"] = True
        if not is_indexed and ("unknown" in cov_lower or "discovered" in cov_lower or "crawled" in cov_lower):
            coverage_actions[coverage]["submit"] = True

    return jsonify({
        "total_tracked": total,
        "indexed": indexed,
        "not_indexed": not_indexed,
        "action_counts": action_counts,
        "coverage_actions": coverage_actions,
        "saved_classification": classifications,
    })


@app.route("/api/monitor")
@handle_errors
def api_monitor():
    """Monitoring status: scan progress, changes, freshness."""
    index_db = _load_json(DATA_DIR / "index_status.json", {})
    change_log = _load_json(DATA_DIR / "change_log.json", [])
    daily_history = _load_json(DATA_DIR / "daily_history.json", [])

    stats = _compute_pipeline_stats(index_db)
    total = stats["total_tracked"]
    indexed = stats["indexed"]

    sitemap_file = Path("urls_all_sitemap.txt")
    total_in_sitemap = 0
    if sitemap_file.exists():
        with open(sitemap_file, "r") as f:
            total_in_sitemap = sum(1 for l in f if l.strip() and not l.startswith("#"))

    now = datetime.datetime.utcnow()
    freshness = {"fresh_3d": 0, "stale_3_7d": 0, "stale_7_14d": 0, "stale_14_30d": 0, "stale_30d_plus": 0}
    for v in index_db.values():
        checked = v.get("checked_at", "")
        if not checked:
            freshness["stale_30d_plus"] += 1
            continue
        try:
            d = datetime.datetime.strptime(checked, "%Y-%m-%d")
            days = (now - d).days
        except ValueError:
            freshness["stale_30d_plus"] += 1
            continue
        if days <= 3: freshness["fresh_3d"] += 1
        elif days <= 7: freshness["stale_3_7d"] += 1
        elif days <= 14: freshness["stale_7_14d"] += 1
        elif days <= 30: freshness["stale_14_30d"] += 1
        else: freshness["stale_30d_plus"] += 1

    today_str = now.strftime("%Y-%m-%d")
    today_changes = [c for c in change_log if c.get("date") == today_str]
    recent_changes = change_log[-50:] if change_log else []

    num_accounts = len(list(Path(".").glob("credentials*.json")))
    daily_capacity = num_accounts * 2000
    remaining_to_scan = max(0, total_in_sitemap - total)
    days_to_complete = remaining_to_scan / daily_capacity if daily_capacity else 0

    return jsonify({
        "scan_progress": {
            "total_in_sitemap": total_in_sitemap,
            "inspected": total,
            "indexed": indexed,
            "not_indexed": total - indexed,
            "scan_pct": round(total / total_in_sitemap * 100, 1) if total_in_sitemap else 0,
            "daily_capacity": daily_capacity,
            "remaining": remaining_to_scan,
            "est_days_to_complete": round(days_to_complete, 1),
        },
        "freshness": freshness,
        "coverage_breakdown": stats["coverage_breakdown"],
        "changes_today": {
            "total": len(today_changes),
            "newly_indexed": sum(1 for c in today_changes if c.get("type") == "newly_indexed"),
            "dropped": sum(1 for c in today_changes if c.get("type") == "dropped_from_index"),
            "status_changes": sum(1 for c in today_changes if c.get("type") == "status_change"),
        },
        "recent_changes": [{"url": c["url"], "date": c["date"], "type": c.get("type", ""),
                            "old": c.get("old_coverage", ""), "new": c.get("new_coverage", "")}
                           for c in reversed(recent_changes)],
        "daily_history": daily_history[-30:],
    })


@app.route("/api/pipeline-status")
@handle_errors
def api_pipeline_status():
    """Current pipeline run status for dashboard notifications."""
    status = _load_json(DATA_DIR / "pipeline_status.json", {})
    return jsonify(status)


@app.route("/api/changes")
@handle_errors
def api_changes():
    """Filterable change log — newly indexed, dropped, status changes."""
    change_log = _load_json(DATA_DIR / "change_log.json", [])

    change_type = request.args.get("type", "")  # newly_indexed, dropped_from_index, status_change
    date = request.args.get("date", "")
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 50)), 200)

    filtered = change_log
    if change_type:
        filtered = [c for c in filtered if c.get("type") == change_type]
    if date:
        filtered = [c for c in filtered if c.get("date") == date]

    filtered = list(reversed(filtered))
    total = len(filtered)
    start = (page - 1) * per_page
    page_items = filtered[start:start + per_page]

    dropped_total = sum(1 for c in change_log if c.get("type") == "dropped_from_index")
    newly_total = sum(1 for c in change_log if c.get("type") == "newly_indexed")

    return jsonify({
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, (total + per_page - 1) // per_page),
        "summary": {
            "total_dropped_ever": dropped_total,
            "total_newly_indexed_ever": newly_total,
        },
        "changes": [{
            "url": c.get("url", ""),
            "date": c.get("date", ""),
            "type": c.get("type", ""),
            "old_coverage": c.get("old_coverage", ""),
            "new_coverage": c.get("new_coverage", ""),
            "timestamp": c.get("timestamp", ""),
        } for c in page_items],
    })


# =============================================
# FULL HTML TEMPLATE (from app.py)
# =============================================
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rudra Retail GSC Auditor v3</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <style>
    /* ── Design tokens ── */
    :root {
      --color-bg: #0a0c10;
      --color-surface-1: #12151c;
      --color-surface-2: #1a1f2b;
      --color-surface-3: #242b3a;
      --color-border: #2d3548;
      --color-text: #e2e8f3;
      --color-text-muted: #6b7a94;
      --color-orange: #f97316;
      --color-green: #22c55e;
      --color-red: #ef4444;
      --color-yellow: #eab308;
      --color-blue: #3b82f6;
      --font-body: 'Inter', system-ui, -apple-system, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
      --radius-sm: 6px;
      --radius-md: 10px;
      --radius-lg: 14px;
      --spacing-xs: 4px;
      --spacing-sm: 8px;
      --spacing-md: 16px;
      --spacing-lg: 24px;
      --spacing-xl: 32px;
    }

    /* ── Reset ── */
    *, *::before, *::after {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      background: var(--color-bg);
      color: var(--color-text);
      font-family: var(--font-body);
      font-size: 13px;
      line-height: 1.6;
      min-height: 100vh;
    }

    a {
      color: var(--color-orange);
      text-decoration: none;
    }
    a:hover {
      text-decoration: underline;
    }

    /* ── Toast notifications ── */
    #toast-container {
      position: fixed;
      top: 16px;
      right: 16px;
      z-index: 9999;
      display: flex;
      flex-direction: column;
      gap: 8px;
      pointer-events: none;
    }
    .toast {
      pointer-events: auto;
      padding: 12px 20px;
      border-radius: var(--radius-sm);
      font-size: 13px;
      font-weight: 600;
      color: #fff;
      box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
      animation: toast-in 0.3s ease, toast-out 0.3s ease 3.5s forwards;
      max-width: 400px;
    }
    .toast-success {
      background: var(--color-green);
    }
    .toast-error {
      background: var(--color-red);
    }
    .toast-info {
      background: var(--color-blue);
    }
    @keyframes toast-in {
      from { opacity: 0; transform: translateX(40px); }
      to { opacity: 1; transform: translateX(0); }
    }
    @keyframes toast-out {
      from { opacity: 1; }
      to { opacity: 0; transform: translateY(-10px); }
    }

    /* ── Header ── */
    .header {
      background: var(--color-surface-1);
      border-bottom: 1px solid var(--color-border);
      padding: 0 var(--spacing-lg);
      height: 56px;
      display: flex;
      align-items: center;
      gap: 12px;
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .header-logo {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .header-logo svg {
      width: 28px;
      height: 28px;
      flex-shrink: 0;
    }
    .header-logo-text {
      font-size: 18px;
      font-weight: 800;
      color: var(--color-orange);
      letter-spacing: -0.5px;
    }
    .header-divider {
      width: 1px;
      height: 24px;
      background: var(--color-border);
      margin: 0 4px;
    }
    .header-site {
      font-size: 12px;
      color: var(--color-text-muted);
      font-family: var(--font-mono);
    }
    .header-version {
      font-size: 10px;
      color: var(--color-text-muted);
      background: var(--color-surface-2);
      padding: 2px 8px;
      border-radius: 99px;
      font-weight: 600;
    }
    .header-spacer {
      flex: 1;
    }
    .connection-status {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 14px;
      border-radius: 99px;
      background: var(--color-surface-2);
      border: 1px solid var(--color-border);
    }
    .connection-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      flex-shrink: 0;
    }
    .connection-label {
      font-size: 12px;
      font-weight: 600;
      color: var(--color-text-muted);
    }
    .header-connect-btn {
      padding: 8px 18px;
      border-radius: var(--radius-sm);
      border: 1px solid var(--color-border);
      background: transparent;
      color: var(--color-text-muted);
      font-size: 12px;
      font-weight: 700;
      cursor: pointer;
      font-family: var(--font-body);
      transition: all 0.15s ease;
    }
    .header-connect-btn:hover {
      border-color: var(--color-orange);
      color: var(--color-orange);
    }
    .header-connect-btn:disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }

    /* ── Input panel ── */
    .input-panel {
      background: var(--color-surface-1);
      border-bottom: 1px solid var(--color-border);
      padding: var(--spacing-lg);
    }
    .input-area {
      max-width: 960px;
    }
    .input-label {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: var(--spacing-sm);
    }
    .input-label-text {
      font-size: 12px;
      font-weight: 600;
      color: var(--color-text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .url-count {
      font-size: 11px;
      color: var(--color-text-muted);
      font-family: var(--font-mono);
    }
    .input-row {
      display: flex;
      gap: 12px;
      align-items: flex-end;
    }
    .input-group {
      flex: 1;
    }
    .url-input {
      width: 100%;
      background: var(--color-surface-2);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      padding: 14px 16px;
      color: var(--color-text);
      font-size: 13px;
      font-family: var(--font-mono);
      outline: none;
      transition: border-color 0.15s ease;
      resize: vertical;
      min-height: 100px;
      line-height: 1.6;
    }
    .url-input::placeholder {
      color: var(--color-text-muted);
      opacity: 0.6;
    }
    .url-input:focus {
      border-color: var(--color-orange);
      box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.1);
    }
    .audit-btn {
      padding: 14px 28px;
      border-radius: var(--radius-md);
      border: none;
      background: var(--color-orange);
      color: #fff;
      font-size: 14px;
      font-weight: 700;
      cursor: pointer;
      font-family: var(--font-body);
      display: flex;
      align-items: center;
      gap: 8px;
      white-space: nowrap;
      transition: background 0.15s ease;
      height: fit-content;
    }
    .audit-btn:hover {
      background: #ea580c;
    }
    .audit-btn:disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }
    .audit-btn svg {
      width: 18px;
      height: 18px;
    }

    /* ── Toolbar ── */
    .toolbar {
      display: flex;
      gap: 8px;
      margin-top: 14px;
      flex-wrap: wrap;
      align-items: center;
    }
    .toolbar-btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      font-weight: 600;
      padding: 8px 14px;
      border-radius: var(--radius-sm);
      border: 1px solid var(--color-border);
      background: var(--color-surface-2);
      color: var(--color-text-muted);
      cursor: pointer;
      font-family: var(--font-body);
      transition: all 0.15s ease;
    }
    .toolbar-btn:hover {
      border-color: var(--color-orange);
      color: var(--color-orange);
    }
    .toolbar-btn svg {
      width: 14px;
      height: 14px;
    }
    .toolbar-btn--blue {
      border-color: rgba(59, 130, 246, 0.3);
      color: var(--color-blue);
    }
    .toolbar-btn--blue:hover {
      border-color: var(--color-blue);
      background: rgba(59, 130, 246, 0.08);
    }
    .toolbar-btn--green {
      border-color: rgba(34, 197, 94, 0.3);
      color: var(--color-green);
    }
    .toolbar-btn--green:hover {
      border-color: var(--color-green);
      background: rgba(34, 197, 94, 0.08);
    }
    .toolbar-btn--yellow {
      border-color: rgba(234, 179, 8, 0.3);
      color: var(--color-yellow);
    }
    .toolbar-btn--yellow:hover {
      border-color: var(--color-yellow);
      background: rgba(234, 179, 8, 0.08);
    }

    /* ── CSV Import panel ── */
    .csv-panel {
      background: var(--color-surface-1);
      border-bottom: 1px solid var(--color-border);
      padding: 0 var(--spacing-lg);
      max-height: 0;
      overflow: hidden;
      transition: max-height 0.35s ease, padding 0.35s ease;
    }
    .csv-panel.visible {
      max-height: 2000px;
      padding: var(--spacing-lg);
      padding-top: 0;
    }
    .csv-panel-header {
      font-size: 13px;
      font-weight: 700;
      color: var(--color-text);
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 8px;
      padding-top: var(--spacing-md);
      border-top: 1px solid var(--color-border);
    }
    .csv-panel-header svg {
      width: 16px;
      height: 16px;
      color: var(--color-blue);
    }
    .csv-panel-sub {
      font-size: 11px;
      color: var(--color-text-muted);
      margin-bottom: 14px;
    }
    .csv-form-row {
      display: flex;
      gap: 16px;
      align-items: flex-end;
      flex-wrap: wrap;
    }
    .csv-field {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .csv-field label {
      font-size: 11px;
      font-weight: 600;
      color: var(--color-text-muted);
    }
    .csv-field input[type="file"] {
      font-size: 12px;
      color: var(--color-text);
      background: var(--color-surface-2);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-sm);
      padding: 8px 12px;
      cursor: pointer;
    }
    .csv-field input[type="file"]::file-selector-button {
      background: var(--color-surface-3);
      border: 1px solid var(--color-border);
      color: var(--color-text);
      padding: 4px 10px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      margin-right: 8px;
    }
    .csv-select {
      background: var(--color-surface-2);
      border: 1px solid var(--color-border);
      color: var(--color-text);
      padding: 8px 12px;
      border-radius: var(--radius-sm);
      font-size: 12px;
      font-family: var(--font-body);
      cursor: pointer;
      outline: none;
    }
    .csv-select:focus {
      border-color: var(--color-orange);
    }
    .csv-import-btn {
      padding: 8px 18px;
      border-radius: var(--radius-sm);
      border: none;
      background: var(--color-blue);
      color: #fff;
      font-size: 12px;
      font-weight: 700;
      cursor: pointer;
      font-family: var(--font-body);
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .csv-import-btn:hover {
      background: #2563eb;
    }
    .csv-status {
      margin-top: 12px;
      font-size: 12px;
      color: var(--color-text-muted);
      font-family: var(--font-mono);
    }
    #csvSummary {
      margin-top: 12px;
      display: none;
      gap: 8px;
      flex-wrap: wrap;
    }
    #csvResults {
      margin-top: 12px;
    }

    /* ── Progress bar ── */
    .progress-panel {
      padding: 12px var(--spacing-lg);
      background: var(--color-surface-1);
      border-bottom: 1px solid var(--color-border);
      display: none;
    }
    .progress-panel.visible {
      display: block;
    }
    .progress-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }
    .progress-status {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .progress-spinner {
      width: 16px;
      height: 16px;
      border: 2px solid var(--color-border);
      border-top-color: var(--color-orange);
      border-radius: 50%;
      animation: spin 0.6s linear infinite;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    .progress-label {
      font-size: 13px;
      font-weight: 600;
      color: var(--color-text);
    }
    .progress-pct {
      font-size: 13px;
      font-weight: 700;
      color: var(--color-orange);
      font-family: var(--font-mono);
    }
    .progress-track {
      width: 100%;
      height: 6px;
      background: var(--color-surface-3);
      border-radius: 99px;
      overflow: hidden;
    }
    .progress-fill {
      height: 100%;
      background: linear-gradient(90deg, var(--color-orange), #fb923c);
      border-radius: 99px;
      transition: width 0.4s ease;
      width: 0%;
    }
    .progress-detail {
      font-size: 11px;
      color: var(--color-text-muted);
      margin-top: 6px;
      font-family: var(--font-mono);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    /* ── Summary dashboard ── */
    .summary-bar {
      display: none;
      gap: 12px;
      padding: 20px var(--spacing-lg);
      flex-wrap: wrap;
    }
    .summary-bar.visible {
      display: flex;
    }
    .summary-card {
      background: var(--color-surface-1);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      padding: 16px 22px;
      min-width: 120px;
      flex: 1;
      position: relative;
      overflow: hidden;
    }
    .summary-card::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
    }
    .summary-card--audited::before { background: var(--color-orange); }
    .summary-card--blockers::before { background: var(--color-red); }
    .summary-card--indexed::before { background: var(--color-green); }
    .summary-card--impressions::before { background: var(--color-blue); }
    .summary-card--clicks::before { background: var(--color-yellow); }
    .summary-card--snippets::before { background: #a855f7; }
    .summary-card--rating::before { background: #fbbf24; }
    .summary-value {
      font-size: 28px;
      font-weight: 800;
      font-family: var(--font-mono);
      line-height: 1.1;
    }
    .summary-value--orange { color: var(--color-orange); }
    .summary-value--red { color: var(--color-red); }
    .summary-value--green { color: var(--color-green); }
    .summary-value--blue { color: var(--color-blue); }
    .summary-value--yellow { color: var(--color-yellow); }
    .summary-value--purple { color: #a855f7; }
    .summary-value--gold { color: #fbbf24; }
    .summary-label {
      font-size: 11px;
      color: var(--color-text-muted);
      margin-top: 4px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .summary-sub {
      font-size: 10px;
      color: var(--color-text-muted);
      font-family: var(--font-mono);
      margin-top: 2px;
      opacity: 0.7;
    }

    /* ── Filter bar ── */
    .filter-bar {
      padding: 12px var(--spacing-lg);
      background: var(--color-surface-1);
      border-bottom: 1px solid var(--color-border);
      display: none;
      gap: 6px;
      align-items: center;
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
      scrollbar-width: none;
    }
    .filter-bar::-webkit-scrollbar {
      display: none;
    }
    .filter-bar.visible {
      display: flex;
    }
    .filter-label {
      font-size: 11px;
      font-weight: 700;
      color: var(--color-text-muted);
      margin-right: 6px;
      white-space: nowrap;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .filter-btn {
      font-size: 11px;
      font-weight: 600;
      padding: 6px 14px;
      border-radius: 99px;
      border: 1px solid var(--color-border);
      background: var(--color-surface-2);
      color: var(--color-text-muted);
      cursor: pointer;
      transition: all 0.15s ease;
      white-space: nowrap;
      font-family: var(--font-body);
    }
    .filter-btn:hover {
      border-color: var(--color-orange);
      color: var(--color-orange);
    }
    .filter-btn.active {
      background: var(--color-orange);
      color: #fff;
      border-color: var(--color-orange);
    }
    .filter-btn[onclick*="indexed"]:not([onclick*="notindexed"]).active {
      background: var(--color-green);
      border-color: var(--color-green);
    }
    .filter-btn[onclick*="notindexed"].active {
      background: var(--color-red);
      border-color: var(--color-red);
    }
    .filter-btn[onclick*="hassnippet"].active {
      background: #a855f7;
      border-color: #a855f7;
    }
    .filter-btn[onclick*="nosnippet"].active {
      background: #6b7280;
      border-color: #6b7280;
    }
    .filter-btn[onclick*="clean"].active {
      background: var(--color-green);
      border-color: var(--color-green);
    }
    .filter-btn[onclick*="'404'"].active {
      background: var(--color-red);
      border-color: var(--color-red);
    }
    .filter-btn .filter-count {
      font-family: var(--font-mono);
      font-size: 10px;
      margin-left: 4px;
      opacity: 0.7;
    }

    /* ── View toggle ── */
    .view-toggle {
      display: inline-flex;
      background: var(--color-surface-2);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-sm);
      overflow: hidden;
      margin-left: auto;
    }
    .view-toggle-btn {
      padding: 6px 14px;
      font-size: 11px;
      font-weight: 600;
      font-family: var(--font-body);
      border: none;
      background: transparent;
      color: var(--color-text-muted);
      cursor: pointer;
      transition: all 0.15s ease;
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }
    .view-toggle-btn:hover { color: var(--color-text); }
    .view-toggle-btn.active {
      background: var(--color-orange);
      color: #fff;
    }

    /* ── Card container ── */
    .cards-container {
      padding: var(--spacing-md) var(--spacing-lg) 60px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    /* ── Results table ── */
    .table-container {
      padding: var(--spacing-md) var(--spacing-lg) 60px;
      overflow-x: auto;
      display: none;
    }
    .results-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
      min-width: 900px;
    }
    .results-table thead th {
      position: sticky;
      top: 0;
      background: var(--color-surface-1);
      color: var(--color-text-muted);
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      padding: 10px 12px;
      border-bottom: 2px solid var(--color-border);
      text-align: left;
      cursor: pointer;
      white-space: nowrap;
      user-select: none;
    }
    .results-table thead th:hover {
      color: var(--color-orange);
    }
    .results-table thead th .sort-arrow {
      font-size: 9px;
      margin-left: 3px;
      opacity: 0.4;
    }
    .results-table thead th.sorted .sort-arrow {
      opacity: 1;
      color: var(--color-orange);
    }
    .results-table tbody tr {
      border-bottom: 1px solid var(--color-border);
      transition: background 0.1s ease;
    }
    .results-table tbody tr:hover {
      background: var(--color-surface-2);
    }
    .results-table td {
      padding: 10px 12px;
      color: var(--color-text);
      font-family: var(--font-mono);
      font-size: 11px;
      white-space: nowrap;
    }
    .results-table td.td-product {
      white-space: normal;
      max-width: 260px;
      font-family: var(--font-body);
      font-size: 12px;
    }
    .results-table td.td-product a {
      color: var(--color-text);
      text-decoration: none;
    }
    .results-table td.td-product a:hover {
      color: var(--color-orange);
    }
    .td-num { text-align: right; }

    /* ── Status pills ── */
    .status-pill {
      display: inline-block;
      padding: 3px 10px;
      border-radius: 99px;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.03em;
      white-space: nowrap;
    }
    .status-pill--indexed {
      background: rgba(20, 83, 45, 0.25);
      color: #4ade80;
    }
    .status-pill--discovered {
      background: rgba(120, 53, 15, 0.25);
      color: var(--color-orange);
    }
    .status-pill--crawled {
      background: rgba(120, 53, 15, 0.25);
      color: var(--color-yellow);
    }
    .status-pill--error {
      background: rgba(127, 29, 29, 0.25);
      color: var(--color-red);
    }
    .status-pill--unknown {
      background: rgba(45, 53, 72, 0.4);
      color: var(--color-text-muted);
    }
    .status-pill--processing {
      background: rgba(30, 58, 138, 0.3);
      color: var(--color-blue);
    }
    .snippet-badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 10px;
      font-weight: 600;
    }
    .snippet-badge--yes {
      background: rgba(20, 83, 45, 0.25);
      color: #4ade80;
    }
    .snippet-badge--no {
      background: rgba(127, 29, 29, 0.15);
      color: var(--color-text-muted);
    }
    .table-search {
      background: var(--color-surface-2);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-sm);
      padding: 7px 14px;
      color: var(--color-text);
      font-family: var(--font-body);
      font-size: 12px;
      width: 220px;
      outline: none;
      transition: border-color 0.15s ease;
    }
    .table-search:focus {
      border-color: var(--color-orange);
    }
    .table-search::placeholder {
      color: var(--color-text-muted);
    }
    .table-toolbar {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 14px;
      flex-wrap: wrap;
    }
    .table-toolbar-spacer { flex: 1; }
    .table-action-btn {
      padding: 6px 14px;
      border-radius: var(--radius-sm);
      border: 1px solid var(--color-border);
      background: transparent;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      font-family: var(--font-body);
      transition: all 0.15s ease;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      color: var(--color-text-muted);
    }
    .table-action-btn:hover {
      border-color: var(--color-orange);
      color: var(--color-orange);
    }
    .table-action-btn--blue {
      border-color: rgba(59, 130, 246, 0.3);
      color: var(--color-blue);
    }
    .table-action-btn--blue:hover {
      border-color: var(--color-blue);
      background: rgba(59, 130, 246, 0.08);
    }
    .table-action-btn--green {
      border-color: rgba(34, 197, 94, 0.3);
      color: var(--color-green);
    }
    .table-action-btn--green:hover {
      border-color: var(--color-green);
      background: rgba(34, 197, 94, 0.08);
    }
    .td-actions {
      white-space: nowrap;
    }
    .td-actions a, .td-actions button {
      padding: 3px 8px;
      border-radius: 4px;
      border: 1px solid var(--color-border);
      background: transparent;
      font-size: 10px;
      font-weight: 600;
      cursor: pointer;
      font-family: var(--font-body);
      transition: all 0.12s ease;
      color: var(--color-text-muted);
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 3px;
      margin-right: 4px;
    }
    .td-actions a:hover, .td-actions button:hover {
      border-color: var(--color-orange);
      color: var(--color-orange);
    }
    .td-product-title {
      font-size: 10px;
      color: var(--color-text-muted);
      margin-top: 2px;
      max-width: 240px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    @media (max-width: 640px) {
      .table-container {
        padding-left: var(--spacing-md);
        padding-right: var(--spacing-md);
      }
      .table-search { width: 100%; }
      .table-toolbar { gap: 6px; }
    }

    /* ── Result cards ── */
    .card {
      background: var(--color-surface-1);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      overflow: hidden;
      transition: border-color 0.15s ease;
    }
    .card:hover {
      border-color: var(--color-surface-3);
    }
    .card-head {
      display: flex;
      align-items: center;
      padding: 14px 18px;
      gap: 12px;
      cursor: pointer;
      flex-wrap: wrap;
    }
    .card-severity-dot {
      width: 12px;
      height: 12px;
      border-radius: 50%;
      flex-shrink: 0;
      box-shadow: 0 0 8px rgba(0, 0, 0, 0.3);
    }
    .card-slug {
      font-weight: 700;
      font-size: 13px;
      flex: 1;
      min-width: 200px;
      word-break: break-all;
      font-family: var(--font-mono);
    }
    .card-metrics {
      display: flex;
      gap: 16px;
    }
    .card-metric {
      text-align: center;
    }
    .card-metric-value {
      font-size: 16px;
      font-weight: 700;
      font-family: var(--font-mono);
      display: block;
      line-height: 1.2;
    }
    .card-metric-label {
      font-size: 10px;
      color: var(--color-text-muted);
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }
    .card-chevron {
      color: var(--color-text-muted);
      font-size: 14px;
      transition: transform 0.25s ease;
      margin-left: 8px;
      flex-shrink: 0;
    }
    .card.open .card-chevron {
      transform: rotate(180deg);
    }
    .card-body {
      display: none;
      padding: 0 18px 18px;
      border-top: 1px solid var(--color-border);
    }
    .card.open .card-body {
      display: block;
    }

    /* ── Mode badge ── */
    .mode-badge {
      font-size: 10px;
      font-weight: 700;
      padding: 3px 10px;
      border-radius: 99px;
      margin-left: 8px;
      display: inline-block;
      vertical-align: middle;
    }
    .mode-badge--preflight {
      background: rgba(249, 115, 22, 0.15);
      color: var(--color-orange);
      border: 1px solid var(--color-orange);
    }
    .mode-badge--full {
      background: rgba(34, 197, 94, 0.15);
      color: var(--color-green);
      border: 1px solid var(--color-green);
    }

    /* ── Status badges row ── */
    .badge-row {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      margin: 14px 0 6px;
    }
    .status-badge {
      font-size: 10px;
      font-weight: 700;
      padding: 4px 12px;
      border-radius: 99px;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .status-badge--neutral {
      background: var(--color-surface-2);
      color: var(--color-text-muted);
    }
    .status-badge--danger {
      background: rgba(239, 68, 68, 0.12);
      color: var(--color-red);
      border: 1px solid var(--color-red);
    }
    .status-badge--warning {
      background: rgba(249, 115, 22, 0.12);
      color: var(--color-orange);
      border: 1px solid var(--color-orange);
    }
    .status-badge--success {
      background: rgba(34, 197, 94, 0.12);
      color: var(--color-green);
      border: 1px solid var(--color-green);
    }
    .status-badge--info {
      background: rgba(59, 130, 246, 0.12);
      color: var(--color-blue);
      border: 1px solid var(--color-blue);
    }

    /* ── Detail grid ── */
    .detail-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 18px;
      margin-top: 14px;
    }
    @media (max-width: 700px) {
      .detail-grid {
        grid-template-columns: 1fr;
      }
    }
    .detail-section-title {
      font-size: 11px;
      font-weight: 700;
      color: var(--color-text-muted);
      margin-bottom: 10px;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }
    .detail-row {
      display: flex;
      justify-content: space-between;
      padding: 6px 0;
      border-bottom: 1px solid rgba(45, 53, 72, 0.5);
      font-size: 12px;
    }
    .detail-row:last-child {
      border-bottom: none;
    }
    .detail-key {
      color: var(--color-text-muted);
      flex-shrink: 0;
      width: 130px;
    }
    .detail-value {
      color: var(--color-text);
      text-align: right;
      word-break: break-all;
      font-family: var(--font-mono);
      font-size: 11px;
    }

    /* ── Issue / Action cards ── */
    .issue-card {
      border-left: 3px solid;
      border-radius: var(--radius-sm);
      padding: 12px 14px;
      margin-bottom: 8px;
      background: var(--color-surface-2);
    }
    .issue-card--p1 { border-color: var(--color-red); }
    .issue-card--p2 { border-color: var(--color-orange); }
    .issue-card--p3 { border-color: var(--color-yellow); }
    .issue-card--p4 { border-color: var(--color-green); }
    .issue-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
    }
    .issue-category {
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }
    .issue-priority {
      font-size: 9px;
      font-weight: 700;
      padding: 2px 8px;
      border-radius: 4px;
      background: var(--color-surface-3);
      color: var(--color-text-muted);
    }
    .issue-message {
      font-size: 12px;
      font-weight: 600;
      margin-bottom: 4px;
      line-height: 1.5;
    }
    .issue-fix {
      font-size: 11px;
      color: var(--color-text-muted);
      line-height: 1.5;
    }

    /* ── Schema tags ── */
    .schema-tags {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      margin-top: 10px;
    }
    .schema-tag {
      font-size: 10px;
      font-weight: 600;
      padding: 3px 10px;
      border-radius: 4px;
    }
    .schema-tag--ok {
      background: rgba(20, 83, 45, 0.25);
      color: #4ade80;
    }
    .schema-tag--warn {
      background: rgba(120, 53, 15, 0.25);
      color: var(--color-orange);
    }
    .schema-tag--err {
      background: rgba(127, 29, 29, 0.25);
      color: var(--color-red);
    }

    /* ── Query table ── */
    .query-table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 6px;
    }
    .query-table th,
    .query-table td {
      padding: 7px 10px;
      text-align: left;
      font-size: 11px;
      border-bottom: 1px solid var(--color-border);
    }
    .query-table th {
      color: var(--color-text-muted);
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.03em;
      font-size: 10px;
    }
    .query-table td {
      font-family: var(--font-mono);
      font-size: 11px;
    }
    .query-table tbody tr:hover {
      background: var(--color-surface-2);
    }

    /* ── Quick-win callout ── */
    .quick-win {
      background: rgba(30, 58, 95, 0.5);
      border: 1px solid var(--color-blue);
      border-radius: var(--radius-sm);
      padding: 10px 14px;
      margin-top: 8px;
      font-size: 12px;
      color: var(--color-blue);
      display: flex;
      gap: 8px;
      align-items: flex-start;
    }
    .quick-win svg {
      width: 16px;
      height: 16px;
      flex-shrink: 0;
      margin-top: 1px;
    }

    /* ── Card action buttons ── */
    .card-actions {
      display: flex;
      gap: 8px;
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px solid var(--color-border);
      flex-wrap: wrap;
    }
    .action-btn {
      padding: 7px 14px;
      border-radius: var(--radius-sm);
      border: 1px solid var(--color-border);
      background: transparent;
      font-size: 11px;
      font-weight: 700;
      cursor: pointer;
      font-family: var(--font-body);
      transition: all 0.15s ease;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      text-decoration: none;
    }
    .action-btn:hover {
      text-decoration: none;
    }
    .action-btn--default {
      color: var(--color-text-muted);
    }
    .action-btn--default:hover {
      border-color: var(--color-orange);
      color: var(--color-orange);
    }
    .action-btn--yellow {
      color: var(--color-yellow);
      border-color: rgba(234, 179, 8, 0.4);
    }
    .action-btn--yellow:hover {
      border-color: var(--color-yellow);
      background: rgba(234, 179, 8, 0.08);
    }
    .action-btn--blue {
      color: var(--color-blue);
      border-color: rgba(59, 130, 246, 0.4);
    }
    .action-btn--blue:hover {
      border-color: var(--color-blue);
      background: rgba(59, 130, 246, 0.08);
    }
    .action-btn--green {
      color: var(--color-green);
      border-color: rgba(34, 197, 94, 0.4);
    }
    .action-btn--green:hover {
      border-color: var(--color-green);
      background: rgba(34, 197, 94, 0.08);
    }

    /* ── Fix panel ── */
    .fix-panel {
      display: none;
      margin-top: 10px;
      padding: 14px;
      background: var(--color-surface-2);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
    }

    /* ── GSC locked box ── */
    .gsc-locked {
      margin-top: 14px;
      padding: 14px;
      background: var(--color-surface-2);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
    }
    .gsc-locked-title {
      font-size: 12px;
      font-weight: 700;
      color: var(--color-orange);
      margin-bottom: 4px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .gsc-locked-text {
      font-size: 11px;
      color: var(--color-text-muted);
      line-height: 1.6;
    }

    /* ── Empty state ── */
    .empty-state {
      text-align: center;
      padding: 80px var(--spacing-lg);
      color: var(--color-text-muted);
    }
    .empty-icon {
      width: 64px;
      height: 64px;
      margin: 0 auto 16px;
      background: var(--color-surface-2);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .empty-icon svg {
      width: 32px;
      height: 32px;
      color: var(--color-text-muted);
    }
    .empty-title {
      font-size: 16px;
      font-weight: 700;
      color: var(--color-text);
      margin-bottom: 6px;
    }
    .empty-sub {
      font-size: 13px;
      max-width: 460px;
      margin: 0 auto;
      line-height: 1.6;
    }

    /* ── CSV results badges (shared) ── */
    .csv-verdict-badge {
      font-size: 10px;
      font-weight: 700;
      padding: 3px 10px;
      border-radius: 99px;
      display: inline-block;
      margin: 2px;
    }

    /* ── No-issues state ── */
    .no-issues {
      color: var(--color-green);
      font-size: 12px;
      font-weight: 600;
      padding: 10px 0;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    /* ── Responsive ── */
    @media (max-width: 640px) {
      .header {
        padding: 0 var(--spacing-md);
        gap: 8px;
      }
      .input-panel,
      .csv-panel.visible,
      .progress-panel,
      .summary-bar,
      .filter-bar,
      .cards-container,
      .table-container {
        padding-left: var(--spacing-md);
        padding-right: var(--spacing-md);
      }
      .card-head {
        padding: 12px 14px;
      }
      .card-body {
        padding: 0 14px 14px;
      }
      .summary-card {
        min-width: 80px;
        padding: 10px 12px;
      }
      .summary-value {
        font-size: 20px;
      }
      .summary-label {
        font-size: 9px;
      }
      .summary-sub {
        display: none;
      }
      .header-version,
      .header-divider {
        display: none;
      }
      .input-row {
        flex-direction: column;
      }
      .audit-btn {
        width: 100%;
        justify-content: center;
      }
      .view-toggle {
        display: none;
      }
    }
    @media (min-width: 641px) and (max-width: 900px) {
      .summary-card {
        min-width: 100px;
        padding: 12px 14px;
      }
      .summary-value {
        font-size: 22px;
      }
    }
  </style>
</head>
<body>

<!-- Toast container -->
<div id="toast-container"></div>

<!-- Header -->
<div class="header">
  <div class="header-logo">
    <svg viewBox="0 0 28 28" fill="none">
      <rect width="28" height="28" rx="6" fill="#f97316"/>
      <path d="M8 10h12l-2 10H10L8 10z" fill="#fff" opacity="0.9"/>
      <circle cx="14" cy="8" r="3" fill="#fff"/>
    </svg>
    <span class="header-logo-text">GSC Auditor</span>
  </div>
  <div class="header-divider"></div>
  <span class="header-site">{{ site }}</span>
  <span class="header-version">v3</span>
  <div class="header-spacer"></div>
  <div class="connection-status">
    <div class="connection-dot" id="authDot" style="background: var(--color-red)"></div>
    <span class="connection-label" id="authLabel">Not connected</span>
  </div>
  <button class="header-connect-btn" id="authBtn" onclick="doAuth()">Connect GSC</button>
</div>

<!-- Input panel -->
<div class="input-panel">
  <div class="input-area">
    <div class="input-label">
      <span class="input-label-text">Product URLs (one per line)</span>
      <span class="url-count" id="urlCount">0 URLs</span>
    </div>
    <div class="input-row">
      <div class="input-group">
        <textarea class="url-input" id="urlInput"
          placeholder="https://YOUR_DOMAIN_HERE/products/product-name-here&#10;https://YOUR_DOMAIN_HERE/products/another-product&#10;&#10;Paste one URL per line. Works with or without GSC authentication."
          oninput="updateUrlCount()"></textarea>
      </div>
      <button class="audit-btn" id="auditBtn" onclick="startAudit()">
        <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="8" cy="8" r="5.5"/><path d="M12 12l4 4"/>
        </svg>
        Start Audit
      </button>
    </div>
    <div class="toolbar">
      <button class="toolbar-btn" onclick="loadSample()">
        <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 3h10M2 7h7M2 11h5"/></svg>
        Load Samples
      </button>
      <button class="toolbar-btn" onclick="clearAll()">
        <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 3l8 8M11 3l-8 8"/></svg>
        Clear
      </button>
      <button class="toolbar-btn--green toolbar-btn" onclick="exportCSV()">
        <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M7 2v8M4 7l3 3 3-3M2 12h10"/></svg>
        Export CSV
      </button>
      <button class="toolbar-btn--yellow toolbar-btn" onclick="sitemapGap()">
        <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="2" width="10" height="10" rx="1.5"/><path d="M5 5h4M5 7h2M5 9h3"/></svg>
        Sitemap Gap
      </button>
      <button class="toolbar-btn--blue toolbar-btn" onclick="toggleCsvPanel()">
        <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M7 2v10M2 7h10"/></svg>
        Import GSC CSV
      </button>
    </div>
  </div>
</div>

<!-- CSV Import panel -->
<div class="csv-panel" id="csvPanel">
  <div class="csv-panel-header">
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 2h8l2 4v8H2V6l2-4z"/><path d="M2 6h12"/></svg>
    Import GSC CSV Export
  </div>
  <div class="csv-panel-sub">Cross-validates each URL from the CSV against the live page. Supports Table.csv and optional Metadata.csv from GSC exports.</div>
  <div class="csv-form-row">
    <div class="csv-field">
      <label>Table.csv (required)</label>
      <input type="file" id="csvTable" accept=".csv">
    </div>
    <div class="csv-field">
      <label>Metadata.csv (optional -- auto-detects issue type)</label>
      <input type="file" id="csvMeta" accept=".csv">
    </div>
    <div class="csv-field">
      <label>Verify limit</label>
      <select id="csvLimit" class="csv-select">
        <option value="10">First 10 URLs</option>
        <option value="25">First 25</option>
        <option value="50">First 50</option>
        <option value="100">First 100</option>
        <option value="all">All URLs</option>
      </select>
    </div>
    <button class="csv-import-btn" onclick="importCSV()">
      <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M7 10V2M4 7l3 3 3-3M2 12h10"/></svg>
      Import &amp; Verify
    </button>
  </div>
  <div class="csv-status" id="csvStatus"></div>
  <div id="csvSummary"></div>
  <div id="csvResults"></div>
</div>

<!-- Progress panel -->
<div class="progress-panel" id="statusBar">
  <div class="progress-header">
    <div class="progress-status">
      <div class="progress-spinner"></div>
      <span class="progress-label">Auditing URLs...</span>
    </div>
    <span class="progress-pct" id="progressPct">0%</span>
  </div>
  <div class="progress-track">
    <div class="progress-fill" id="progressFill"></div>
  </div>
  <div class="progress-detail" id="statusText">Starting...</div>
</div>

<!-- Summary dashboard -->
<div class="summary-bar" id="summaryBar">
  <div class="summary-card summary-card--audited">
    <div class="summary-value summary-value--orange" id="sumTotal">0</div>
    <div class="summary-label">Audited</div>
  </div>
  <div class="summary-card summary-card--blockers">
    <div class="summary-value summary-value--red" id="sumP1">0</div>
    <div class="summary-label">P1 Blockers</div>
  </div>
  <div class="summary-card summary-card--indexed">
    <div class="summary-value summary-value--green" id="sumIdx">0</div>
    <div class="summary-label" id="sumIdxL">Indexed</div>
    <div class="summary-sub" id="sumIdxSub"></div>
  </div>
  <div class="summary-card summary-card--snippets">
    <div class="summary-value summary-value--purple" id="sumSnip">0</div>
    <div class="summary-label">Snippets</div>
    <div class="summary-sub" id="sumSnipSub"></div>
  </div>
  <div class="summary-card summary-card--rating">
    <div class="summary-value summary-value--gold" id="sumRating">0</div>
    <div class="summary-label">Has Rating</div>
    <div class="summary-sub" id="sumRatingSub"></div>
  </div>
  <div class="summary-card summary-card--impressions">
    <div class="summary-value summary-value--blue" id="sumImpr">0</div>
    <div class="summary-label" id="sumImprL">Impressions</div>
  </div>
  <div class="summary-card summary-card--clicks">
    <div class="summary-value summary-value--yellow" id="sumClk">0</div>
    <div class="summary-label" id="sumClkL">Clicks (90d)</div>
  </div>
</div>

<!-- Filter bar -->
<div class="filter-bar" id="filterBar">
  <span class="filter-label">Filter:</span>
  <button class="filter-btn active" onclick="setFilter('all')">All<span class="filter-count" id="fc-all"></span></button>
  <button class="filter-btn" onclick="setFilter('indexed')">Indexed<span class="filter-count" id="fc-indexed"></span></button>
  <button class="filter-btn" onclick="setFilter('notindexed')">Not Indexed<span class="filter-count" id="fc-notindexed"></span></button>
  <button class="filter-btn" onclick="setFilter('hassnippet')">Has Snippet<span class="filter-count" id="fc-hassnippet"></span></button>
  <button class="filter-btn" onclick="setFilter('nosnippet')">No Snippet<span class="filter-count" id="fc-nosnippet"></span></button>
  <button class="filter-btn" onclick="setFilter('noindex')">Noindex<span class="filter-count" id="fc-noindex"></span></button>
  <button class="filter-btn" onclick="setFilter('schema')">Schema<span class="filter-count" id="fc-schema"></span></button>
  <button class="filter-btn" onclick="setFilter('crawled')">Crawled Not Indexed<span class="filter-count" id="fc-crawled"></span></button>
  <button class="filter-btn" onclick="setFilter('404')">404 / Error<span class="filter-count" id="fc-404"></span></button>
  <button class="filter-btn" onclick="setFilter('ctr')">Low CTR<span class="filter-count" id="fc-ctr"></span></button>
  <button class="filter-btn" onclick="setFilter('clean')">Clean<span class="filter-count" id="fc-clean"></span></button>
  <div class="view-toggle" id="viewToggle">
    <button class="view-toggle-btn active" onclick="setView('cards')" id="vt-cards">
      <svg viewBox="0 0 14 14" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="1" y="1" width="12" height="5" rx="1"/><rect x="1" y="8" width="12" height="5" rx="1"/></svg>Cards
    </button>
    <button class="view-toggle-btn" onclick="setView('table')" id="vt-table">
      <svg viewBox="0 0 14 14" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M1 3h12M1 7h12M1 11h12"/><path d="M5 1v12"/></svg>Table
    </button>
  </div>
</div>

<!-- Card results -->
<div class="cards-container" id="cardContainer">
  <div class="empty-state" id="emptyState">
    <div class="empty-icon">
      <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="14" cy="14" r="9"/>
        <path d="M21 21l7 7"/>
        <path d="M11 14h6M14 11v6" stroke-width="1.5"/>
      </svg>
    </div>
    <div class="empty-title">Paste product URLs and click Start Audit</div>
    <div class="empty-sub">
      Runs 33 checks: schema markup, content quality, images, OG tags, indexing status,
      coverage state, and search performance metrics. Works without GSC login (pre-flight mode).
    </div>
  </div>
</div>

<!-- Table results -->
<div class="table-container" id="tableContainer">
  <div class="table-toolbar">
    <input type="text" class="table-search" id="tableSearch" placeholder="Search products..." oninput="renderTable()">
    <span style="font-size:11px;color:var(--color-text-muted);font-family:var(--font-mono)" id="tableCount"></span>
    <div class="table-toolbar-spacer"></div>
    <button class="table-action-btn--green table-action-btn" onclick="exportCSV()">
      <svg viewBox="0 0 14 14" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M7 2v8M4 7l3 3 3-3M2 12h10"/></svg>
      Export CSV
    </button>
    <button class="table-action-btn--blue table-action-btn" id="bulkReindexBtn" onclick="bulkReindex()">
      <svg viewBox="0 0 14 14" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M7 2v10M2 7l5 5 5-5"/></svg>
      Reindex Non-Indexed
    </button>
  </div>
  <table class="results-table" id="resultsTable">
    <thead>
      <tr>
        <th onclick="sortTable(0)">#<span class="sort-arrow">▼</span></th>
        <th onclick="sortTable(1)">Product<span class="sort-arrow">▼</span></th>
        <th onclick="sortTable(2)">Status<span class="sort-arrow">▼</span></th>
        <th onclick="sortTable(3)">Snippet<span class="sort-arrow">▼</span></th>
        <th onclick="sortTable(4)">Rating<span class="sort-arrow">▼</span></th>
        <th onclick="sortTable(5)">Impr<span class="sort-arrow">▼</span></th>
        <th onclick="sortTable(6)">Clicks<span class="sort-arrow">▼</span></th>
        <th onclick="sortTable(7)">Pos<span class="sort-arrow">▼</span></th>
        <th onclick="sortTable(8)">CTR<span class="sort-arrow">▼</span></th>
        <th onclick="sortTable(9)">Crawled<span class="sort-arrow">▼</span></th>
        <th onclick="sortTable(10)">Issues<span class="sort-arrow">▼</span></th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody id="tableBody"></tbody>
  </table>
</div>

<script>
// =============================================
// STATE
// =============================================
const results = [];
let authenticated = false;

// =============================================
// INITIALIZATION
// =============================================
fetch('/api/status')
  .then(r => r.json())
  .then(d => { if (d.authenticated) setAuth(true); });

// =============================================
// TOAST NOTIFICATIONS
// =============================================
function showToast(message, type) {
  type = type || 'info';
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = 'toast toast-' + type;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(function() {
    if (toast.parentNode) toast.remove();
  }, 4000);
}

// =============================================
// URL COUNT
// =============================================
function updateUrlCount() {
  var raw = document.getElementById('urlInput').value.trim();
  var count = raw ? raw.split('\n').filter(function(u) { return u.trim() && u.trim().startsWith('http'); }).length : 0;
  document.getElementById('urlCount').textContent = count + ' URL' + (count !== 1 ? 's' : '');
}

// =============================================
// CSV PANEL TOGGLE
// =============================================
function toggleCsvPanel() {
  document.getElementById('csvPanel').classList.toggle('visible');
}

// =============================================
// AUTH
// =============================================
function setAuth(ok) {
  authenticated = ok;
  document.getElementById('authDot').style.background = ok ? 'var(--color-green)' : 'var(--color-red)';
  document.getElementById('authLabel').textContent = ok ? 'Connected' : 'Not connected';
  document.getElementById('authBtn').textContent = ok ? 'Connected' : 'Connect GSC';
}

function doAuth() {
  document.getElementById('authBtn').disabled = true;
  document.getElementById('authBtn').textContent = 'Connecting...';
  fetch('/api/auth', { method: 'POST' })
    .then(r => r.json())
    .then(d => {
      setAuth(d.ok);
      if (!d.ok) showToast('Auth failed: ' + (d.error || ''), 'error');
      else showToast('Connected to GSC successfully', 'success');
      document.getElementById('authBtn').disabled = false;
    })
    .catch(e => {
      showToast('Connection error: ' + e, 'error');
      document.getElementById('authBtn').disabled = false;
      document.getElementById('authBtn').textContent = 'Connect GSC';
    });
}

// =============================================
// SAMPLE & CLEAR
// =============================================
function loadSample() {
  document.getElementById('urlInput').value =
    'https://YOUR_DOMAIN_HERE/products/365-days-of-colorado-2026-weekly-engagement-calendar-by-todd-caudle\n' +
    'https://YOUR_DOMAIN_HERE/products/colorado-fourteeners-2026-deluxe-wall-calendar-by-todd-caudle\n' +
    'https://YOUR_DOMAIN_HERE/products/guts-glitter-glory-finding-hope-in-hopelessness\n' +
    'https://YOUR_DOMAIN_HERE/products/hy-ko-vinyl-numbers-and-letters-mm-8\n' +
    'https://YOUR_DOMAIN_HERE/products/number-1-all-systems-botanical-conditioner-concentrated-16-ounce\n' +
    'https://YOUR_DOMAIN_HERE/products/1-all-systems-super-rich-protein-lotion-pet-conditioner-16-ounce';
  updateUrlCount();
  showToast('6 sample URLs loaded', 'info');
}

function clearAll() {
  results.length = 0;
  renderCards();
  renderTable();
  document.getElementById('summaryBar').classList.remove('visible');
  document.getElementById('filterBar').classList.remove('visible');
  document.getElementById('emptyState').style.display = '';
  document.getElementById('urlInput').value = '';
  if (activeView === 'table') setView('cards');
  updateUrlCount();
  showToast('Cleared all results', 'info');
}

// =============================================
// SITEMAP GAP
// =============================================
function sitemapGap() {
  fetch('/api/sitemap-gap')
    .then(r => {
      if (!r.ok) throw new Error('Connect GSC first');
      return r.json();
    })
    .then(d => {
      let msg = 'Sitemap Gap Report:\n\n';
      d.forEach(s => {
        msg += s.path + '\nSubmitted: ' + s.submitted.toLocaleString() +
          ' | Indexed: ' + s.indexed.toLocaleString() +
          ' | Gap: ' + s.gap.toLocaleString() + '\n\n';
      });
      alert(msg);
    })
    .catch(e => showToast(e.message, 'error'));
}

// =============================================
// START AUDIT
// =============================================
async function startAudit() {
  const raw = document.getElementById('urlInput').value.trim();
  if (!raw) { showToast('Paste URLs first', 'error'); return; }

  const urls = raw.split('\n').map(u => u.trim()).filter(u => u && u.startsWith('http'));
  if (!urls.length) { showToast('No valid URLs found', 'error'); return; }

  document.getElementById('auditBtn').disabled = true;
  document.getElementById('statusBar').classList.add('visible');
  document.getElementById('emptyState').style.display = 'none';
  document.getElementById('progressFill').style.width = '0%';
  document.getElementById('progressPct').textContent = '0%';

  for (let i = 0; i < urls.length; i++) {
    const pct = Math.round(((i + 1) / urls.length) * 100);
    const slug = urls[i].split('/products/')[1] || urls[i];
    document.getElementById('statusText').textContent = '[' + (i + 1) + '/' + urls.length + '] ' + slug;
    document.getElementById('progressFill').style.width = pct + '%';
    document.getElementById('progressPct').textContent = pct + '%';

    try {
      const resp = await fetch('/api/audit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: urls[i] })
      });
      const d = await resp.json();
      if (d.error) { console.error(d.error); continue; }
      results.push(d);
      if (activeView === 'table') renderTable();
      else renderCards();
      updateSummary();
      updateFilterCounts();
    } catch (e) { console.error(e); }
  }

  document.getElementById('statusBar').classList.remove('visible');
  document.getElementById('auditBtn').disabled = false;
  showToast('Audit complete: ' + results.length + ' URLs processed', 'success');
}

// =============================================
// UPDATE SUMMARY
// =============================================
function updateSummary() {
  document.getElementById('summaryBar').classList.add('visible');
  const af = results.some(r => r.mode === 'full');
  const total = results.length;

  document.getElementById('sumTotal').textContent = total;
  document.getElementById('sumP1').textContent = results.filter(r => r.actions.some(a => a.p === 1)).length;

  const indexedCount = results.filter(r =>
    (r.gsc.coverage || '').toLowerCase().includes('indexed') &&
    !(r.gsc.coverage || '').toLowerCase().includes('not indexed')
  ).length;

  const snippetCount = results.filter(r =>
    (r.sa.appearances || []).includes('PRODUCT_SNIPPETS')
  ).length;

  const ratingCount = results.filter(r => r.pf.has_aggregate_rating).length;

  if (af) {
    document.getElementById('sumIdx').textContent = indexedCount;
    document.getElementById('sumIdxSub').textContent = total ? Math.round(indexedCount / total * 100) + '% of total' : '';
    document.getElementById('sumSnip').textContent = snippetCount;
    document.getElementById('sumSnipSub').textContent = indexedCount ? Math.round(snippetCount / indexedCount * 100) + '% of indexed' : '';
    document.getElementById('sumRating').textContent = ratingCount;
    document.getElementById('sumRatingSub').textContent = total ? Math.round(ratingCount / total * 100) + '% of total' : '';
    document.getElementById('sumImpr').textContent = results.reduce((s, r) => s + (r.sa.impr || 0), 0).toLocaleString();
    document.getElementById('sumClk').textContent = results.reduce((s, r) => s + (r.sa.clicks || 0), 0).toLocaleString();
  } else {
    document.getElementById('sumIdx').textContent = '-';
    document.getElementById('sumSnip').textContent = '-';
    document.getElementById('sumRating').textContent = ratingCount;
    document.getElementById('sumRatingSub').textContent = total ? Math.round(ratingCount / total * 100) + '%' : '';
    document.getElementById('sumImprL').textContent = 'Total issues';
    document.getElementById('sumImpr').textContent = results.reduce((s, r) => s + r.actions.length, 0);
    document.getElementById('sumClkL').textContent = 'Noindex';
    document.getElementById('sumClk').textContent = results.filter(r => r.pf.noindex).length;
  }
}

// =============================================
// PRIORITY COLORS
// =============================================
const PC = {
  1: ['#ef4444', 'P1'],
  2: ['#f97316', 'P2'],
  3: ['#eab308', 'P3'],
  4: ['#22c55e', 'P4']
};

// =============================================
// ESCAPE HTML
// =============================================
function esc(s) {
  const d = document.createElement('div');
  d.textContent = s || '';
  return d.innerHTML;
}

// =============================================
// CLASSIFY RESULTS INTO FILTER CATEGORIES
// =============================================
function classify(r) {
  const cats = new Set();
  const pf = r.pf, gsc = r.gsc, sa = r.sa, acts = r.actions;

  const cov = (gsc.coverage || '').toLowerCase();
  const isIndexed = cov.includes('indexed') && !cov.includes('not indexed');

  if (isIndexed) cats.add('indexed');
  else cats.add('notindexed');

  if ((sa.appearances || []).includes('PRODUCT_SNIPPETS')) cats.add('hassnippet');
  else cats.add('nosnippet');

  if (pf.noindex) cats.add('noindex');
  if (pf.http_status >= 400) cats.add('404');

  if (cov.includes('crawled') && cov.includes('not indexed')) cats.add('crawled');
  if (cov.includes('server error') || pf.http_status >= 500) cats.add('404');
  if (cov.includes('not found') || cov.includes('soft 404')) cats.add('404');
  if (cov.includes('blocked') || cov.includes('robots') || cov.includes('403') || gsc.robots === 'DISALLOWED') { cats.add('404'); }
  if (acts.some(a => a.cat === 'SCHEMA' || (a.cat === 'CTR' && a.msg.includes('aggregateRating')) || a.cat === 'RISK')) cats.add('schema');
  if (sa.pos >= 5 && sa.pos <= 15 && sa.ctr < 2 && sa.impr > 50) cats.add('ctr');
  if (acts.length === 0) cats.add('clean');

  return cats;
}

// =============================================
// FILTER
// =============================================
let activeFilter = 'all';

function setFilter(f) {
  activeFilter = f;
  document.querySelectorAll('.filter-btn').forEach(b => {
    const match = b.getAttribute('onclick');
    if (match && match.includes("'" + f + "'")) b.classList.add('active');
    else b.classList.remove('active');
  });
  if (activeView === 'table') renderTable();
  else renderCards();
}

function updateFilterCounts() {
  const counts = { all: results.length, indexed: 0, notindexed: 0, hassnippet: 0, nosnippet: 0, noindex: 0, '404': 0, schema: 0, crawled: 0, ctr: 0, clean: 0 };
  results.forEach(r => {
    const cats = classify(r);
    cats.forEach(c => { if (counts[c] !== undefined) counts[c]++; });
  });
  Object.keys(counts).forEach(k => {
    const el = document.getElementById('fc-' + k);
    if (el) el.textContent = counts[k] ? ' ' + counts[k] : '';
  });
  document.getElementById('filterBar').classList.add('visible');
}

// =============================================
// RE-AUDIT SINGLE URL
// =============================================
async function reAudit(idx) {
  const url = results[idx].pf.url;
  const btn = document.getElementById('rebtn-' + idx);
  if (btn) { btn.disabled = true; btn.textContent = 'Auditing...'; }
  try {
    const resp = await fetch('/api/audit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url })
    });
    const d = await resp.json();
    if (!d.error) {
      results[idx] = d;
      renderCards();
      updateSummary();
      updateFilterCounts();
      showToast('Re-audit complete', 'success');
    }
  } catch (e) { console.error(e); }
  if (btn) { btn.disabled = false; btn.textContent = 'Re-audit'; }
}

// =============================================
// RENDER CARDS
// =============================================
function renderCards() {
  const c = document.getElementById('cardContainer');
  let html = '';
  const sorted = [...results].sort((a, b) => b.score - a.score);

  sorted.forEach((r, i) => {
    const cats = classify(r);
    if (activeFilter !== 'all' && !cats.has(activeFilter)) return;

    const origIdx = results.indexOf(r);
    const pf = r.pf, gsc = r.gsc, sa = r.sa, acts = r.actions, isPf = r.mode === 'preflight';
    const worst = acts.length ? Math.min(...acts.map(a => a.p)) : 4;
    const [col] = PC[worst] || ['#6b7280'];
    const slug = pf.url.includes('/products/') ? pf.url.split('/products/')[1] : pf.url;

    // Build issues HTML
    let actHtml = '';
    acts.forEach(a => {
      const [ac] = PC[a.p] || ['#6b7280'];
      actHtml += '<div class="issue-card issue-card--p' + a.p + '">' +
        '<div class="issue-header">' +
          '<span class="issue-category" style="color:' + ac + '">' + esc(a.cat) + '</span>' +
          '<span class="issue-priority">P' + a.p + '</span>' +
        '</div>' +
        '<div class="issue-message">' + esc(a.msg) + '</div>' +
        '<div class="issue-fix">&#8594; ' + esc(a.fix) + '</div>' +
      '</div>';
    });
    if (!actHtml) actHtml = '<div class="no-issues"><svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="8" cy="8" r="6"/><path d="M5.5 8l2 2 3-3"/></svg> No issues found</div>';

    // Build query rows
    let qHtml = '';
    (sa.queries || []).forEach(q => {
      const cc = q.ctr < 2 && q.pos <= 15 ? 'var(--color-red)' : 'var(--color-green)';
      qHtml += '<tr><td>' + esc(q.q) + '</td><td>' + q.impr.toLocaleString() + '</td><td>' + q.clicks + '</td><td>' + q.pos + '</td><td style="color:' + cc + '">' + q.ctr + '%</td></tr>';
    });

    // Build quick-win HTML
    let qwHtml = '';
    (sa.quick_wins || []).forEach(q => {
      qwHtml += '<div class="quick-win">' +
        '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="6"/><path d="M8 5v3l2 1.5"/></svg>' +
        '<span><strong>Quick win:</strong> "' + esc(q.q) + '" -- pos ' + q.pos + ', ' + q.impr + ' impressions. Almost page 1!</span>' +
      '</div>';
    });

    // Coverage color
    const covColor = !isPf && (gsc.coverage || '').toLowerCase().includes('indexed') && !(gsc.coverage || '').toLowerCase().includes('not indexed') ? 'var(--color-green)' : 'var(--color-red)';

    // Card start
    html += '<div class="card" id="card' + i + '" onclick="this.classList.toggle(\'open\')">';

    // Card header
    html += '<div class="card-head">';
    html += '<div class="card-severity-dot" style="background:' + col + '"></div>';
    html += '<div class="card-slug">' + esc(slug) +
      '<span class="mode-badge ' + (isPf ? 'mode-badge--preflight' : 'mode-badge--full') + '">' + (isPf ? 'Pre-flight' : 'Full audit') + '</span></div>';

    // Card metrics
    if (isPf) {
      html += '<div class="card-metrics">' +
        '<div class="card-metric"><span class="card-metric-value">HTTP ' + (pf.http_status || '?') + '</span><span class="card-metric-label">status</span></div>' +
        '<div class="card-metric"><span class="card-metric-value">' + pf.page_kb + '</span><span class="card-metric-label">KB</span></div>' +
        '<div class="card-metric"><span class="card-metric-value">' + acts.length + '</span><span class="card-metric-label">issues</span></div>' +
      '</div>';
    } else {
      html += '<div class="card-metrics">' +
        '<div class="card-metric"><span class="card-metric-value">' + (sa.impr || 0).toLocaleString() + '</span><span class="card-metric-label">impr</span></div>' +
        '<div class="card-metric"><span class="card-metric-value">' + (sa.clicks || 0) + '</span><span class="card-metric-label">clicks</span></div>' +
        '<div class="card-metric"><span class="card-metric-value">' + (sa.pos || '-') + '</span><span class="card-metric-label">pos</span></div>' +
        '<div class="card-metric"><span class="card-metric-value">' + (sa.ctr || 0) + '%</span><span class="card-metric-label">CTR</span></div>' +
        (sa.mobile_pct ? '<div class="card-metric"><span class="card-metric-value">' + sa.mobile_pct + '%</span><span class="card-metric-label">mobile</span></div>' : '') +
      '</div>';
    }

    html += '<span class="card-chevron">&#9660;</span></div>';

    // Card body
    html += '<div class="card-body" onclick="event.stopPropagation()">';

    // Status badges
    html += '<div class="badge-row">';
    html += '<span class="status-badge status-badge--neutral">HTTP ' + pf.http_status + '</span>';
    html += '<span class="status-badge status-badge--neutral">' + pf.page_kb + 'KB</span>';
    if (pf.noindex) html += '<span class="status-badge status-badge--danger">NOINDEX</span>';
    if (!pf.canonical_self) html += '<span class="status-badge status-badge--warning">Canonical != self</span>';
    if (!isPf) {
      html += '<span class="status-badge" style="background:' + covColor + '18;color:' + covColor + ';border:1px solid ' + covColor + '">' + esc(gsc.coverage || '?') + '</span>';
      html += '<span class="status-badge status-badge--neutral">' + esc(gsc.crawled_as || '?') + '</span>';
      html += '<span class="status-badge status-badge--neutral">Last: ' + esc(gsc.last_crawl || 'Never') + '</span>';
      if (gsc.in_sitemap) html += '<span class="status-badge status-badge--success">Sitemap</span>';
      if ((sa.appearances || []).length) html += '<span class="status-badge status-badge--info">' + (sa.appearances || []).join(', ') + '</span>';
      if (gsc.link) html += '<a href="' + esc(gsc.link) + '" target="_blank" class="status-badge status-badge--info" style="text-decoration:none">GSC</a>';
    }
    html += '</div>';

    // Detail grid
    html += '<div class="detail-grid">';

    // Left column: Issues & Fixes
    html += '<div class="detail-section">';
    html += '<div class="detail-section-title">Issues &amp; Fixes (' + acts.length + ')</div>';
    html += actHtml;
    html += qwHtml;
    html += '</div>';

    // Right column: Pre-flight checks
    html += '<div class="detail-section">';
    html += '<div class="detail-section-title">Pre-flight (' + 20 + ' checks)</div>';
    html += '<div class="detail-row"><span class="detail-key">Title</span><span class="detail-value">' + esc((pf.title || '-').substring(0, 55)) + '</span></div>';
    html += '<div class="detail-row"><span class="detail-key">Title length</span><span class="detail-value" style="color:' + (pf.title_len > 60 ? 'var(--color-yellow)' : 'var(--color-green)') + '">' + pf.title_len + ' chars</span></div>';
    html += '<div class="detail-row"><span class="detail-key">Meta desc</span><span class="detail-value">' + pf.desc_len + ' chars</span></div>';
    html += '<div class="detail-row"><span class="detail-key">Description</span><span class="detail-value" style="color:' + (pf.desc_word_count < 50 ? 'var(--color-red)' : pf.desc_word_count < 100 ? 'var(--color-yellow)' : 'var(--color-green)') + '">' + pf.desc_word_count + ' words</span></div>';
    html += '<div class="detail-row"><span class="detail-key">Brand</span><span class="detail-value" style="color:' + (pf.brand_unknown ? 'var(--color-red)' : 'var(--color-text)') + '">' + esc(pf.brand || '-') + '</span></div>';
    html += '<div class="detail-row"><span class="detail-key">Return days</span><span class="detail-value" style="color:' + ((pf.return_days || 0) > 3 ? 'var(--color-red)' : (pf.return_days ? 'var(--color-green)' : 'var(--color-text-muted)')) + '">' + (pf.return_days ? pf.return_days + ' (actual: 3)' : '-') + '</span></div>';
    html += '<div class="detail-row"><span class="detail-key">Canonical</span><span class="detail-value" style="color:' + (pf.canonical_self ? 'var(--color-green)' : 'var(--color-orange)') + '">' + (pf.canonical_self ? 'Self' : 'Diff') + '</span></div>';
    html += '<div class="detail-row"><span class="detail-key">Images</span><span class="detail-value">' + pf.img_count + ' (' + pf.img_no_alt + ' no alt)</span></div>';
    html += '<div class="detail-row"><span class="detail-key">Internal links</span><span class="detail-value" style="color:' + (pf.internal_links < 5 ? 'var(--color-orange)' : 'var(--color-green)') + '">' + pf.internal_links + '</span></div>';
    html += '<div class="detail-row"><span class="detail-key">Currency</span><span class="detail-value" style="color:' + (pf.price_currency && pf.price_currency !== 'INR' ? 'var(--color-orange)' : 'var(--color-green)') + '">' + (pf.price_currency || '-') + '</span></div>';

    // Schema tags
    html += '<div class="schema-tags">';
    html += '<span class="schema-tag ' + (pf.has_product_jsonld ? 'schema-tag--ok' : 'schema-tag--err') + '">Product' + (pf.product_jsonld_count > 1 ? 'x' + pf.product_jsonld_count : '') + ' ' + (pf.has_product_jsonld ? 'Y' : 'N') + '</span>';
    html += '<span class="schema-tag ' + (pf.has_aggregate_rating ? 'schema-tag--ok' : 'schema-tag--warn') + '">Rating ' + (pf.has_aggregate_rating ? 'Y' : 'N') + '</span>';
    html += '<span class="schema-tag ' + (pf.gtin ? 'schema-tag--ok' : 'schema-tag--warn') + '">GTIN ' + (pf.gtin ? 'Y' : 'N') + '</span>';
    html += '<span class="schema-tag ' + (pf.has_price ? 'schema-tag--ok' : 'schema-tag--err') + '">Price ' + (pf.has_price ? 'Y' : 'N') + '</span>';
    html += '<span class="schema-tag ' + (pf.has_availability ? 'schema-tag--ok' : 'schema-tag--warn') + '">Avail ' + (pf.has_availability ? 'Y' : 'N') + '</span>';
    html += '<span class="schema-tag ' + (pf.has_image_in_schema ? 'schema-tag--ok' : 'schema-tag--warn') + '">Img ' + (pf.has_image_in_schema ? 'Y' : 'N') + '</span>';
    html += '<span class="schema-tag ' + (pf.has_breadcrumb ? 'schema-tag--ok' : 'schema-tag--warn') + '">Bread ' + (pf.has_breadcrumb ? 'Y' : 'N') + '</span>';
    html += '<span class="schema-tag ' + (pf.has_og_title && pf.has_og_image ? 'schema-tag--ok' : 'schema-tag--warn') + '">OG ' + (pf.has_og_title && pf.has_og_image ? 'Y' : 'N') + '</span>';
    if (pf.faq_count > 0) html += '<span class="schema-tag schema-tag--warn">FAQx' + pf.faq_count + '</span>';
    html += '<span class="schema-tag ' + (pf.page_kb > 800 ? 'schema-tag--warn' : 'schema-tag--ok') + '">' + pf.page_kb + 'KB</span>';
    html += '</div>';

    // GSC locked or query data
    if (isPf) {
      html += '<div class="gsc-locked">' +
        '<div class="gsc-locked-title"><svg viewBox="0 0 14 14" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="7" width="8" height="5" rx="1"/><path d="M5 7V5a2 2 0 014 0v2"/></svg> GSC data locked</div>' +
        '<div class="gsc-locked-text">Connect GSC for: coverage state, crawl info, rich result errors, queries, impressions, clicks, position, CTR, device split, search appearance, quick-win keywords</div>' +
      '</div>';
    } else {
      if (qHtml) {
        html += '<div class="detail-section-title" style="margin-top:14px">Top Queries (90d)</div>';
        html += '<table class="query-table"><thead><tr><th>Query</th><th>Impr</th><th>Clicks</th><th>Pos</th><th>CTR</th></tr></thead><tbody>' + qHtml + '</tbody></table>';
      } else {
        html += '<div style="color:var(--color-text-muted);font-size:11px;margin-top:14px">No search data</div>';
      }
    }

    html += '</div>'; // end right column
    html += '</div>'; // end detail-grid

    // Action buttons
    html += '<div class="card-actions">';
    html += '<button class="action-btn action-btn--default" id="rebtn-' + origIdx + '" onclick="event.stopPropagation();reAudit(' + origIdx + ')"><svg viewBox="0 0 14 14" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M1 7a6 6 0 0111.5-2M13 7A6 6 0 011.5 9"/><path d="M12 2v3h-3M2 12V9h3"/></svg> Re-audit</button>';
    if (pf.url.includes('/products/')) {
      html += '<button class="action-btn action-btn--yellow" id="fixbtn-' + origIdx + '" onclick="event.stopPropagation();previewFix(' + origIdx + ')"><svg viewBox="0 0 14 14" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M8 2l4 4-7 7H1v-4l7-7z"/></svg> Preview Shopify Fix</button>';
    }
    html += '<button class="action-btn action-btn--blue" id="rixbtn-' + origIdx + '" onclick="event.stopPropagation();requestReindex(' + origIdx + ')"><svg viewBox="0 0 14 14" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M7 2v10M2 7l5 5 5-5"/></svg> Request Reindex</button>';
    html += '<a href="https://search.google.com/test/rich-results?url=' + encodeURIComponent(pf.url) + '" target="_blank" class="action-btn action-btn--green" onclick="event.stopPropagation()"><svg viewBox="0 0 14 14" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="7" cy="7" r="5"/><path d="M5 7l1.5 1.5L9 5.5"/></svg> Rich Results Test</a>';
    html += '</div>';

    // Fix panel
    html += '<div class="fix-panel" id="fixpanel-' + origIdx + '"></div>';

    html += '</div>'; // card-body
    html += '</div>'; // card
  });

  const empty = document.getElementById('emptyState');
  c.innerHTML = html;
  if (!results.length && empty) c.appendChild(empty);
}

// =============================================
// VIEW TOGGLE
// =============================================
let activeView = 'cards';

function setView(v) {
  activeView = v;
  document.querySelectorAll('.view-toggle-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('vt-' + v).classList.add('active');
  document.getElementById('cardContainer').style.display = v === 'cards' ? 'flex' : 'none';
  document.getElementById('tableContainer').style.display = v === 'table' ? 'block' : 'none';
  if (v === 'table') renderTable();
}

// =============================================
// TABLE SORT STATE
// =============================================
let tableSortCol = 6;
let tableSortAsc = false;

function sortTable(col) {
  if (tableSortCol === col) {
    tableSortAsc = !tableSortAsc;
  } else {
    tableSortCol = col;
    tableSortAsc = false;
  }
  document.querySelectorAll('.results-table thead th').forEach((th, i) => {
    th.classList.toggle('sorted', i === col);
    const arrow = th.querySelector('.sort-arrow');
    if (arrow) arrow.textContent = i === col ? (tableSortAsc ? '▲' : '▼') : '▼';
  });
  renderTable();
}

// =============================================
// RENDER TABLE
// =============================================
function renderTable() {
  const tbody = document.getElementById('tableBody');
  const searchVal = (document.getElementById('tableSearch').value || '').toLowerCase();

  const filtered = results.filter(r => {
    if (activeFilter !== 'all' && !classify(r).has(activeFilter)) return false;
    if (searchVal) {
      const slug = r.pf.url.includes('/products/') ? r.pf.url.split('/products/')[1] : r.pf.url;
      const title = r.pf.title || '';
      return slug.toLowerCase().includes(searchVal) || title.toLowerCase().includes(searchVal);
    }
    return true;
  });

  const getVal = (r, col) => {
    const pf = r.pf, gsc = r.gsc, sa = r.sa;
    switch(col) {
      case 0: return results.indexOf(r);
      case 1: return (pf.url.includes('/products/') ? pf.url.split('/products/')[1] : pf.url).toLowerCase();
      case 2: return gsc.coverage || '';
      case 3: return (sa.appearances || []).includes('PRODUCT_SNIPPETS') ? 1 : 0;
      case 4: return pf.has_aggregate_rating ? 1 : 0;
      case 5: return sa.impr || 0;
      case 6: return sa.clicks || 0;
      case 7: return sa.pos || 999;
      case 8: return sa.ctr || 0;
      case 9: return gsc.last_crawl || '';
      case 10: return r.actions.length;
      default: return 0;
    }
  };

  filtered.sort((a, b) => {
    let va = getVal(a, tableSortCol), vb = getVal(b, tableSortCol);
    if (typeof va === 'string') {
      va = va.toLowerCase(); vb = (vb || '').toLowerCase();
      return tableSortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    }
    return tableSortAsc ? va - vb : vb - va;
  });

  let html = '';
  filtered.forEach((r, i) => {
    const pf = r.pf, gsc = r.gsc, sa = r.sa, acts = r.actions;
    const origIdx = results.indexOf(r);
    const slug = pf.url.includes('/products/') ? pf.url.split('/products/')[1] : pf.url;
    const isPf = r.mode === 'preflight';
    const title = (pf.title || '').replace(/ – Rudra Retail$| \| Rudra Retail$/i, '').substring(0, 50);

    const cov = (gsc.coverage || '').toLowerCase();
    let pillClass = 'status-pill--unknown', pillText = 'Unknown';
    if (cov.includes('submitted and indexed') || (cov.includes('indexed') && !cov.includes('not indexed'))) {
      pillClass = 'status-pill--indexed'; pillText = 'Indexed';
    } else if (cov.includes('discovered')) {
      pillClass = 'status-pill--discovered'; pillText = 'Discovered';
    } else if (cov.includes('crawled') && cov.includes('not indexed')) {
      pillClass = 'status-pill--crawled'; pillText = 'Crawled';
    } else if (cov.includes('error') || cov.includes('server')) {
      pillClass = 'status-pill--error'; pillText = 'Error';
    } else if (cov.includes('blocked') || cov.includes('robots')) {
      pillClass = 'status-pill--error'; pillText = 'Blocked';
    } else if (cov.includes('not found') || cov.includes('soft 404')) {
      pillClass = 'status-pill--error'; pillText = '404';
    } else if (isPf) {
      pillClass = 'status-pill--processing'; pillText = 'Pre-flight';
    } else if (cov) {
      pillText = gsc.coverage.length > 18 ? gsc.coverage.substring(0, 16) + '..' : gsc.coverage;
    }

    const hasSnippet = (sa.appearances || []).includes('PRODUCT_SNIPPETS');
    const snippetHtml = hasSnippet
      ? '<span class="snippet-badge snippet-badge--yes">Yes</span>'
      : '<span class="snippet-badge snippet-badge--no">No</span>';

    const ratingHtml = pf.has_aggregate_rating
      ? '<span style="color:#fbbf24">★</span>'
      : '<span style="color:var(--color-text-muted)">—</span>';

    const worst = acts.length ? Math.min(...acts.map(a => a.p)) : 0;
    let issueHtml = '';
    if (acts.length === 0) {
      issueHtml = '<span style="color:var(--color-green)">✓</span>';
    } else {
      const [issCol] = PC[worst] || ['var(--color-text-muted)'];
      issueHtml = '<span style="color:' + issCol + ';font-weight:700">' + acts.length + '</span>';
    }

    const posColor = sa.pos ? (sa.pos <= 3 ? 'var(--color-green)' : sa.pos <= 10 ? 'var(--color-yellow)' : sa.pos <= 20 ? 'var(--color-orange)' : 'var(--color-red)') : 'var(--color-text-muted)';
    const ctrColor = sa.ctr ? (sa.ctr >= 5 ? 'var(--color-green)' : sa.ctr >= 2 ? 'var(--color-yellow)' : 'var(--color-red)') : 'var(--color-text-muted)';

    html += '<tr>' +
      '<td class="td-num">' + (i + 1) + '</td>' +
      '<td class="td-product"><a href="' + esc(pf.url) + '" target="_blank">' + esc(slug) + '</a>' +
        (title ? '<div class="td-product-title">' + esc(title) + '</div>' : '') + '</td>' +
      '<td><span class="status-pill ' + pillClass + '">' + esc(pillText) + '</span></td>' +
      '<td>' + snippetHtml + '</td>' +
      '<td style="text-align:center">' + ratingHtml + '</td>' +
      '<td class="td-num">' + (sa.impr || 0).toLocaleString() + '</td>' +
      '<td class="td-num">' + (sa.clicks || 0) + '</td>' +
      '<td class="td-num" style="color:' + posColor + '">' + (sa.pos ? sa.pos : '—') + '</td>' +
      '<td class="td-num" style="color:' + ctrColor + '">' + (sa.ctr ? sa.ctr + '%' : '—') + '</td>' +
      '<td>' + esc(gsc.last_crawl ? gsc.last_crawl.substring(0, 10) : '—') + '</td>' +
      '<td style="text-align:center">' + issueHtml + '</td>' +
      '<td class="td-actions">' +
        '<button onclick="event.stopPropagation();reAudit(' + origIdx + ')" title="Re-audit">↻</button>' +
        '<button onclick="event.stopPropagation();requestReindex(' + origIdx + ')" title="Request Reindex">↓</button>' +
        '<a href="https://search.google.com/test/rich-results?url=' + encodeURIComponent(pf.url) + '" target="_blank" title="Rich Results Test">✓</a>' +
      '</td>' +
    '</tr>';
  });

  tbody.innerHTML = html;

  const idxCount = filtered.filter(r => {
    const c = (r.gsc.coverage || '').toLowerCase();
    return c.includes('indexed') && !c.includes('not indexed');
  }).length;
  const notIdx = filtered.length - idxCount;
  document.getElementById('tableCount').textContent = filtered.length + ' products' +
    (results.some(r => r.mode === 'full') ? ' · ' + idxCount + ' indexed · ' + notIdx + ' not indexed' : '');
}

async function bulkReindex() {
  const nonIndexed = results.filter(r => {
    const c = (r.gsc.coverage || '').toLowerCase();
    return !(c.includes('indexed') && !c.includes('not indexed'));
  });
  if (!nonIndexed.length) { showToast('All products are indexed!', 'success'); return; }
  const btn = document.getElementById('bulkReindexBtn');
  btn.disabled = true;
  btn.textContent = 'Reindexing 0/' + nonIndexed.length + '...';
  let done = 0, ok = 0;
  for (const r of nonIndexed) {
    try {
      const resp = await fetch('/api/reindex', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: r.pf.url })
      });
      const d = await resp.json();
      if (d.success) ok++;
    } catch (e) {}
    done++;
    btn.textContent = 'Reindexing ' + done + '/' + nonIndexed.length + '...';
  }
  btn.disabled = false;
  btn.innerHTML = '<svg viewBox="0 0 14 14" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M7 2v10M2 7l5 5 5-5"/></svg> Reindex Non-Indexed';
  showToast('Reindex requested for ' + ok + '/' + nonIndexed.length + ' products', ok > 0 ? 'success' : 'error');
}

// =============================================
// CSV IMPORT & VERIFY
// =============================================
async function importCSV() {
  const tableFile = document.getElementById('csvTable').files[0];
  if (!tableFile) { showToast('Select Table.csv first', 'error'); return; }

  const fd = new FormData();
  fd.append('table', tableFile);
  const metaFile = document.getElementById('csvMeta').files[0];
  if (metaFile) fd.append('metadata', metaFile);

  document.getElementById('csvStatus').textContent = 'Parsing CSV...';
  const resp = await fetch('/api/import-csv', { method: 'POST', body: fd });
  const data = await resp.json();
  if (data.error) { showToast(data.error, 'error'); return; }

  const limit = document.getElementById('csvLimit').value;
  const urls = limit === 'all' ? data.urls : data.urls.slice(0, parseInt(limit));
  document.getElementById('csvStatus').textContent = 'Issue: ' + data.issue_type + ' | ' + data.total + ' URLs in file | Verifying ' + urls.length + '...';
  document.getElementById('csvPanel').style.display = 'block';

  const counts = { FIXED: 0, STILL_BROKEN: 0, STILL_WEAK: 0, CONTENT_OK: 0, NEEDS_WORK: 0, LIVE: 0, NOW_DEAD: 0, CHANGED: 0, ACCESSIBLE: 0, BROKEN: 0, DEAD: 0, CHECK: 0, STILL_REDIRECTING: 0, UNKNOWN: 0 };
  const vResults = [];
  const rDiv = document.getElementById('csvResults');

  for (let i = 0; i < urls.length; i++) {
    document.getElementById('csvStatus').textContent = 'Verifying ' + (i + 1) + '/' + urls.length + ': ' + (urls[i].url.split('/products/')[1] || urls[i].url.split('/').pop());
    try {
      const r = await fetch('/api/verify-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(urls[i])
      });
      const v = await r.json();
      vResults.push(v);
      counts[v.verdict] = (counts[v.verdict] || 0) + 1;
      renderCSVResults(vResults, counts, data.issue_type);
    } catch (e) { console.error(e); }
  }
  document.getElementById('csvStatus').textContent = 'Done -- ' + urls.length + ' URLs verified';
  showToast('CSV verification complete', 'success');
}

function renderCSVResults(vResults, counts, issueType) {
  const vc = {
    FIXED: 'var(--color-green)', STILL_BROKEN: 'var(--color-red)', STILL_WEAK: 'var(--color-orange)',
    CONTENT_OK: 'var(--color-green)', NEEDS_WORK: 'var(--color-yellow)', NOW_DEAD: 'var(--color-text-muted)',
    LIVE: 'var(--color-blue)', CHANGED: 'var(--color-yellow)', ACCESSIBLE: 'var(--color-blue)',
    BROKEN: 'var(--color-red)', DEAD: 'var(--color-text-muted)', CHECK: 'var(--color-yellow)',
    STILL_REDIRECTING: 'var(--color-orange)', UNKNOWN: 'var(--color-text-muted)',
    COLLECTION_OK: 'var(--color-green)', COLLECTION_EMPTY: 'var(--color-orange)',
    SHOPIFY_DELETED: 'var(--color-red)', BLOG_OK: 'var(--color-green)', BLOG_THIN: 'var(--color-yellow)'
  };
  const typeIcon = { product: 'P', collection: 'C', blog: 'B', page: 'G', other: 'O' };

  // Summary badges
  const sDiv = document.getElementById('csvSummary');
  sDiv.style.display = 'flex';
  let badges = '<span style="font-size:11px;font-weight:700;color:var(--color-text-muted);margin-right:4px">' + issueType + ' (' + vResults.length + '):</span>';
  const ordered = ['FIXED', 'CONTENT_OK', 'COLLECTION_OK', 'BLOG_OK', 'NEEDS_WORK', 'STILL_WEAK', 'COLLECTION_EMPTY', 'NOW_DEAD', 'SHOPIFY_DELETED', 'STILL_BROKEN', 'BROKEN', 'DEAD'];
  ordered.forEach(k => {
    if ((counts[k] || 0) > 0) {
      badges += '<span class="csv-verdict-badge" style="background:' + (vc[k] || 'var(--color-text-muted)') + '20;color:' + (vc[k] || 'var(--color-text-muted)') + ';border:1px solid ' + (vc[k] || 'var(--color-text-muted)') + '">' + k.replace(/_/g, ' ') + ' ' + counts[k] + '</span>';
    }
  });
  // Add counts for any not in ordered list
  for (const [k, v] of Object.entries(counts)) {
    if (v > 0 && !ordered.includes(k)) {
      badges += '<span class="csv-verdict-badge" style="background:' + (vc[k] || 'var(--color-text-muted)') + '20;color:' + (vc[k] || 'var(--color-text-muted)') + ';border:1px solid ' + (vc[k] || 'var(--color-text-muted)') + '">' + k.replace(/_/g, ' ') + ' ' + v + '</span>';
    }
  }
  badges += '<button class="toolbar-btn" style="margin-left:8px;padding:5px 12px" onclick="exportVerifyCSV()"><svg viewBox="0 0 14 14" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M7 2v8M4 7l3 3 3-3M2 12h10"/></svg> Export CSV</button>';
  sDiv.innerHTML = badges;

  // Results table
  const rDiv = document.getElementById('csvResults');
  let html = '<table class="query-table" style="margin-top:8px"><thead><tr><th style="width:30px">Type</th><th>URL</th><th style="width:40px">HTTP</th><th style="width:50px">Words</th><th style="width:120px">Verdict</th><th>Detail</th><th>Action</th></tr></thead><tbody>';
  vResults.forEach(v => {
    const slug = v.url.includes('/products/') ? v.url.split('/products/')[1] : (v.url.includes('/collections/') ? v.url.split('/collections/')[1] : v.url.split('/').pop());
    const col = vc[v.verdict] || 'var(--color-text-muted)';
    const icon = typeIcon[v.url_type || 'other'] || 'O';
    const httpCol = v.live_status === 200 ? 'var(--color-green)' : v.live_status === 404 ? 'var(--color-red)' : 'var(--color-orange)';
    const wordsCol = v.desc_words < 50 ? 'var(--color-red)' : v.desc_words < 100 ? 'var(--color-yellow)' : 'var(--color-green)';
    const shopifyBadge = v.shopify_exists === false ? '<span style="color:var(--color-red);font-size:9px"> X Shopify</span>' : (v.shopify_exists === true ? '' : '');
    html += '<tr style="border-bottom:1px solid var(--color-border)">' +
      '<td style="text-align:center">' + icon + '</td>' +
      '<td><a href="' + esc(v.url) + '" target="_blank" style="font-family:var(--font-mono);font-size:10px">' + esc((slug || '').substring(0, 45)) + '</a>' + shopifyBadge + '</td>' +
      '<td style="color:' + httpCol + ';font-weight:700;text-align:center">' + v.live_status + '</td>' +
      '<td style="color:' + wordsCol + ';text-align:center;font-family:var(--font-mono)">' + (v.desc_words || '-') + '</td>' +
      '<td><span style="color:' + col + ';font-weight:700;font-size:10px;padding:2px 6px;border-radius:4px;background:' + col + '15">' + (v.verdict || '').replace(/_/g, ' ') + '</span></td>' +
      '<td style="font-size:10px">' + esc(v.detail || '') + '</td>' +
      '<td style="font-size:10px;color:var(--color-orange)">' + esc(v.action || '') + '</td>' +
    '</tr>';
  });
  html += '</tbody></table>';
  rDiv.innerHTML = html;

  // Store for export
  window._verifyResults = vResults;
}

// =============================================
// EXPORT FUNCTIONS
// =============================================
function exportVerifyCSV() {
  if (!window._verifyResults || !window._verifyResults.length) { showToast('No results to export', 'error'); return; }
  let csv = 'URL,Type,HTTP,Words,Verdict,Shopify_Exists,Detail,Action\\n';
  window._verifyResults.forEach(v => {
    csv += '"' + v.url + '",' + (v.url_type || '') + ',' + v.live_status + ',' + (v.desc_words || 0) + ',' + v.verdict + ',' + (v.shopify_exists === true ? 'YES' : v.shopify_exists === false ? 'NO' : '?') + ',"' + (v.detail || '').replace(/"/g, "'") + '","' + (v.action || '').replace(/"/g, "'") + '"\n';
  });
  const b = new Blob([csv], { type: 'text/csv' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(b);
  a.download = 'gsc-verify-' + new Date().toISOString().slice(0, 10) + '.csv';
  a.click();
  showToast('CSV exported', 'success');
}

function exportCSV() {
  if (!results.length) { showToast('No results to export', 'error'); return; }
  let csv = 'URL,HTTP,Coverage,Impressions,Clicks,Position,CTR,Title_Len,Desc_Words,GTIN,Rating,Price,Availability,Brand,Images,Internal_Links,OG,Breadcrumb,Issues\n';
  results.forEach(r => {
    const iss = r.actions.map(a => '[P' + a.p + ']' + a.cat + ':' + a.msg).join(' | ');
    csv += '"' + r.pf.url + '",' + r.pf.http_status + ',"' + (r.gsc.coverage || '?') + '",' + (r.sa.impr || 0) + ',' + (r.sa.clicks || 0) + ',' + (r.sa.pos || 0) + ',' + (r.sa.ctr || 0) + ',' + r.pf.title_len + ',' + r.pf.desc_word_count + ',' + (r.pf.gtin ? 'Y' : 'N') + ',' + (r.pf.has_aggregate_rating ? 'Y' : 'N') + ',' + (r.pf.has_price ? 'Y' : 'N') + ',' + (r.pf.has_availability ? 'Y' : 'N') + ',"' + (r.pf.brand || '') + '",' + r.pf.img_count + ',' + r.pf.internal_links + ',' + (r.pf.has_og_title ? 'Y' : 'N') + ',' + (r.pf.has_breadcrumb ? 'Y' : 'N') + ',"' + iss + '"\n';
  });
  const b = new Blob([csv], { type: 'text/csv' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(b);
  a.download = 'rudra-retail-gsc-audit-' + new Date().toISOString().slice(0, 10) + '.csv';
  a.click();
  showToast('Audit CSV exported', 'success');
}

// =============================================
// SHOPIFY FIX: Preview -> Confirm -> Apply
// =============================================
async function previewFix(idx) {
  const r = results[idx];
  const btn = document.getElementById('fixbtn-' + idx);
  const panel = document.getElementById('fixpanel-' + idx);
  if (!r || !r.pf.url.includes('/products/')) { showToast('Not a product URL', 'error'); return; }
  btn.disabled = true;
  btn.textContent = 'Loading...';
  try {
    const resp = await fetch('/api/shopify-preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: r.pf.url, audit: r })
    });
    const d = await resp.json();
    if (d.error) {
      panel.innerHTML = '<div style="color:var(--color-red);font-size:12px;padding:8px">' + esc(d.error) + '</div>';
      panel.style.display = 'block';
      return;
    }
    if (!d.has_changes) {
      panel.innerHTML = '<div style="color:var(--color-green);font-size:12px;padding:8px;display:flex;align-items:center;gap:6px"><svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="8" cy="8" r="6"/><path d="M5.5 8l2 2 3-3"/></svg> No auto-fixes needed for this product.</div>';
      panel.style.display = 'block';
      return;
    }
    let html = '<div style="font-size:12px;font-weight:700;color:var(--color-yellow);margin-bottom:10px;display:flex;align-items:center;gap:6px"><svg viewBox="0 0 14 14" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M8 2l4 4-7 7H1v-4l7-7z"/></svg> Preview: ' + d.changes.length + ' fix(es) for "' + esc(d.product_title) + '"</div>';
    html += '<table class="query-table"><thead><tr><th>Field</th><th>Current</th><th>New</th><th>Reason</th></tr></thead><tbody>';
    d.changes.forEach(c => {
      html += '<tr><td style="font-weight:700">' + esc(c.field) + '</td><td style="color:var(--color-red)">' + esc(c.old) + '</td><td style="color:var(--color-green)">' + esc(c.new) + '</td><td style="color:var(--color-text-muted);font-size:10px">' + esc(c.reason) + '</td></tr>';
    });
    html += '</tbody></table>';
    html += '<div style="margin-top:12px;display:flex;gap:8px">';
    html += '<button class="action-btn" onclick="applyFix(' + idx + ')" id="applybtn-' + idx + '" style="background:var(--color-green);color:#fff;border-color:var(--color-green)">Apply to Shopify</button>';
    html += '<button class="action-btn action-btn--default" onclick="document.getElementById(\'fixpanel-' + idx + '\').style.display=\'none\'">Cancel</button>';
    html += '</div>';
    panel.innerHTML = html;
    panel.style.display = 'block';
  } catch (e) {
    panel.innerHTML = '<div style="color:var(--color-red);font-size:12px;padding:8px">Error: ' + e.message + '</div>';
    panel.style.display = 'block';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Preview Shopify Fix';
  }
}

async function applyFix(idx) {
  const r = results[idx];
  const panel = document.getElementById('fixpanel-' + idx);
  const btn = document.getElementById('applybtn-' + idx);
  if (btn) { btn.disabled = true; btn.textContent = 'Applying...'; }
  try {
    const resp = await fetch('/api/shopify-fix', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: r.pf.url, audit: r })
    });
    const d = await resp.json();
    if (d.error) {
      panel.innerHTML += '<div style="color:var(--color-red);font-size:12px;margin-top:8px;padding:8px;background:rgba(239,68,68,0.08);border:1px solid var(--color-red);border-radius:6px">Error: ' + esc(d.error) + '</div>';
      return;
    }
    let msg = '';
    if (d.success) {
      const changeCount = Object.keys(d.changes || {}).length;
      msg = '<div style="color:var(--color-green);font-size:12px;margin-top:10px;padding:12px;background:rgba(34,197,94,0.08);border:1px solid var(--color-green);border-radius:8px">';
      msg += '<strong>Applied ' + changeCount + ' fix(es) to Shopify</strong>';
      for (const [k, v] of Object.entries(d.changes || {})) {
        msg += '<br><span style="color:var(--color-text-muted)">' + esc(k) + ':</span> ' + esc(v);
      }
      msg += '<br><br><button class="action-btn action-btn--blue" onclick="requestReindex(' + idx + ')"><svg viewBox="0 0 14 14" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M7 2v10M2 7l5 5 5-5"/></svg> Request Reindex Now</button></div>';
      showToast('Shopify fix applied successfully', 'success');
    } else {
      msg = '<div style="color:var(--color-orange);font-size:12px;margin-top:8px">' + esc(JSON.stringify(d.changes || {})) + '</div>';
    }
    panel.innerHTML += msg;
  } catch (e) {
    panel.innerHTML += '<div style="color:var(--color-red);font-size:12px;margin-top:8px">Error: ' + e.message + '</div>';
  }
}

async function requestReindex(idx) {
  const r = results[idx];
  const btn = document.getElementById('rixbtn-' + idx);
  if (btn) { btn.disabled = true; btn.textContent = 'Requesting...'; }
  try {
    const resp = await fetch('/api/reindex', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: r.pf.url })
    });
    const d = await resp.json();
    if (d.error) { showToast('Reindex error: ' + d.error, 'error'); return; }
    if (d.success) {
      if (btn) {
        btn.textContent = 'Requested';
        btn.style.color = 'var(--color-green)';
        btn.style.borderColor = 'var(--color-green)';
      }
      showToast('Reindex requested successfully', 'success');
    } else {
      showToast('Reindex failed: ' + (d.error || 'unknown'), 'error');
    }
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  } finally {
    if (btn && btn.textContent === 'Requesting...') {
      btn.disabled = false;
      btn.textContent = 'Request Reindex';
    }
  }
}
</script></body></html>"""


# =============================================
# STARTUP
# =============================================
if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("Rudra Retail GSC Auditor v3.1 -- Starting")
    logger.info(f"   Site: {SITE_URL}")
    logger.info(f"   Workers: {MAX_WORKERS}")
    logger.info(f"   Port: {PORT}")
    logger.info(f"   Timeout: {REQUEST_TIMEOUT}s")
    logger.info("=" * 70)

    # Try to authenticate with GSC
    if os.path.exists("token.json"):
        success, msg = init_google()
        logger.info(f"GSC Auth: {msg}")
    else:
        logger.info("PRE-FLIGHT MODE (no credentials). 20 checks active.")
        logger.info("   Click 'Connect GSC' in UI for full 33-check audit.")

    logger.info(f"Open http://localhost:{PORT}")

    try:
        app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        exit(1)
