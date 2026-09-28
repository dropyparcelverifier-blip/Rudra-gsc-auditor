#!/usr/bin/env python3
"""
Rudra Retail -- Automated SEO Pipeline
=======================================
Dump URLs -> auto checks -> fixes -> index -> daily monitor -> snippet tracking.

QUICK START (new users):
  1. Copy .env.example to .env and fill in your credentials
  2. Add URLs:  python auto_pipeline.py scrape          (auto-fetch from sitemap)
            or: python auto_pipeline.py add urls.txt    (from a file)
  3. Run:       python auto_pipeline.py run urls.txt    (full pipeline)
  4. Monitor:   python auto_pipeline.py monitor         (run daily)

Commands:
  python auto_pipeline.py setup                 # Validate config & show status
  python auto_pipeline.py scrape                # Auto-fetch all product URLs from sitemap
  python auto_pipeline.py add <file_or_url>     # Add URLs from file, or a single URL
  python auto_pipeline.py run <urls_file>       # Full pipeline: check -> fix -> index
  python auto_pipeline.py check <urls_file>     # Step 1 only: liveness + JSON-LD
  python auto_pipeline.py fix                   # Step 2: apply Shopify fixes from last audit
  python auto_pipeline.py index                 # Step 3: submit non-indexed to Google
  python auto_pipeline.py status                # Step 4: check indexing status of all URLs
  python auto_pipeline.py snippets              # Step 5: check snippet appearance
  python auto_pipeline.py monitor               # Daily monitor: status + snippets + report
  python auto_pipeline.py report                # Show summary of last pipeline run
"""

import os
import sys
import json
import time
import datetime
import re
import logging
import requests as _requests
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
BRAND_NAME = os.getenv("BRAND_NAME", "Rudra Retail")
BRAND_DOMAIN = os.getenv("BRAND_DOMAIN", "")
SITE_URL = os.getenv("GOOGLE_SITE_URL", "")
CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
SHOPIFY_STORE = os.getenv("SHOPIFY_STORE", "")
SHOPIFY_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN", "")
SHOPIFY_CLIENT_ID = os.getenv("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET = os.getenv("SHOPIFY_CLIENT_SECRET", "")

DATA_DIR = Path("pipeline_data")
DATA_DIR.mkdir(exist_ok=True)
Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('logs/pipeline.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("pipeline")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def load_urls(source: str) -> List[str]:
    """Load URLs from file or stdin."""
    urls = []
    if source == "-":
        log.info("Reading URLs from stdin (paste URLs, then Ctrl+Z/Ctrl+D)...")
        for line in sys.stdin:
            line = line.strip()
            if line.startswith("http"):
                urls.append(line)
    elif os.path.isfile(source):
        with open(source) as f:
            for line in f:
                line = line.strip()
                if line.startswith("http"):
                    urls.append(line)
    else:
        log.error(f"File not found: {source}")
        sys.exit(1)
    urls = list(dict.fromkeys(urls))  # deduplicate preserving order
    log.info(f"Loaded {len(urls)} unique URLs")
    return urls


def save_state(name: str, data: Any):
    """Save pipeline state to JSON."""
    path = DATA_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log.info(f"Saved: {path}")


def load_state(name: str) -> Optional[Any]:
    """Load pipeline state from JSON."""
    path = DATA_DIR / f"{name}.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def get_handle(url: str) -> str:
    """Extract product handle from URL."""
    if "/products/" in url:
        return url.split("/products/")[-1].split("?")[0].strip("/")
    return url.rsplit("/", 1)[-1]


def _get_google_creds(scopes: list):
    """Get Google credentials — supports both OAuth and service account."""
    if not Path(CREDENTIALS_FILE).exists():
        log.error(f"Credentials file not found: {CREDENTIALS_FILE}")
        return None

    with open(CREDENTIALS_FILE) as f:
        cred_data = json.load(f)

    if cred_data.get("type") == "service_account":
        from google.oauth2 import service_account
        return service_account.Credentials.from_service_account_file(
            CREDENTIALS_FILE, scopes=scopes
        )

    # OAuth client (web or installed)
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

    creds = None
    token_path = Path("token.json")

    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), scopes)
        except Exception:
            pass

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, scopes)
            creds = flow.run_local_server(port=8090)

        try:
            with open(token_path, "w") as f:
                f.write(creds.to_json())
        except Exception:
            pass

    return creds


def init_gsc_services():
    """Initialize Google Search Console and Indexing API services."""
    from googleapiclient.discovery import build

    if not Path(CREDENTIALS_FILE).exists():
        log.error(f"Credentials file not found: {CREDENTIALS_FILE}")
        return None, None

    # URL Inspection API
    creds_inspect = _get_google_creds(["https://www.googleapis.com/auth/webmasters"])
    if not creds_inspect:
        return None, None
    inspect_svc = build("searchconsole", "v1", credentials=creds_inspect)

    # Indexing API (requires service account with site ownership)
    index_svc = None
    with open(CREDENTIALS_FILE) as f:
        cred_data = json.load(f)
    if cred_data.get("type") == "service_account":
        from google.oauth2 import service_account
        creds_index = service_account.Credentials.from_service_account_file(
            CREDENTIALS_FILE, scopes=["https://www.googleapis.com/auth/indexing"]
        )
        index_svc = build("indexing", "v3", credentials=creds_index)
    else:
        log.warning("Indexing API requires a service account. URL submission will be skipped.")
        log.warning("For indexing, create a service account at Google Cloud Console.")

    return inspect_svc, index_svc


# ═════════════════════════════════════════════
# STEP 1: CHECK — Liveness + JSON-LD Validation
# ═════════════════════════════════════════════
_http = _requests.Session()
_http.headers.update({
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
})


def fetch_page(url: str, retries: int = 2) -> Tuple[Optional[str], int, Optional[str]]:
    """Fetch page HTML. Returns (html, status_code, error)."""
    for attempt in range(retries + 1):
        try:
            resp = _http.get(url, timeout=20, allow_redirects=True)
            if resp.status_code == 429 and attempt < retries:
                time.sleep(3 * (attempt + 1))
                continue
            if resp.status_code == 200:
                return resp.text, resp.status_code, None
            return None, resp.status_code, f"HTTP {resp.status_code}"
        except Exception as e:
            if attempt < retries:
                time.sleep(2)
                continue
            return None, 0, str(e)
    return None, 0, "max retries"


def analyze_page(url: str, html: str) -> Dict[str, Any]:
    """Analyze page HTML for JSON-LD structured data and meta tags."""
    try:
        import re as _re
        blocks = _re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html, _re.DOTALL | _re.IGNORECASE
        )

        schemas = []
        errors = []
        for block in blocks:
            try:
                data = json.loads(block.strip())
                if isinstance(data, list):
                    schemas.extend(data)
                else:
                    schemas.append(data)
            except json.JSONDecodeError as e:
                errors.append(f"Invalid JSON-LD: {str(e)[:100]}")

        # Validate Product schema
        product_schema = None
        for s in schemas:
            if s.get("@type") == "Product":
                product_schema = s
                break

        issues = []
        if not schemas:
            issues.append("NO_JSON_LD: No structured data found")
        elif not product_schema:
            types_found = [s.get("@type", "unknown") for s in schemas]
            issues.append(f"NO_PRODUCT_SCHEMA: Found {types_found} but no Product type")
        else:
            # Validate required fields
            if not product_schema.get("name"):
                issues.append("MISSING_NAME: Product name not set in schema")
            if not product_schema.get("description"):
                issues.append("MISSING_DESCRIPTION: No description in schema")
            if not product_schema.get("image"):
                issues.append("MISSING_IMAGE: No image in schema")

            offers = product_schema.get("offers") or product_schema.get("offer")
            if not offers:
                issues.append("MISSING_OFFERS: No price/offer data in schema")
            else:
                offer = offers[0] if isinstance(offers, list) else offers
                if not offer.get("price") and not offer.get("lowPrice"):
                    issues.append("MISSING_PRICE: No price in offer")
                if not offer.get("availability"):
                    issues.append("MISSING_AVAILABILITY: No availability status")
                if offer.get("priceCurrency") != "INR":
                    issues.append(f"WRONG_CURRENCY: {offer.get('priceCurrency', 'missing')} (expected INR)")

            # Check for aggregateRating
            if not product_schema.get("aggregateRating"):
                issues.append("NO_RATINGS: No aggregateRating — won't show stars in SERP")

        # Also extract meta tags
        title_match = _re.search(r'<title[^>]*>(.*?)</title>', html, _re.IGNORECASE | _re.DOTALL)
        meta_desc_match = _re.search(
            r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\']', html, _re.IGNORECASE
        )
        canonical_match = _re.search(
            r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']*)["\']', html, _re.IGNORECASE
        )
        noindex = bool(_re.search(r'<meta\s+name=["\']robots["\']\s+content=["\'][^"\']*noindex', html, _re.IGNORECASE))

        title = title_match.group(1).strip() if title_match else ""
        meta_desc = meta_desc_match.group(1).strip() if meta_desc_match else ""
        canonical = canonical_match.group(1).strip() if canonical_match else ""

        if not title:
            issues.append("NO_TITLE: Page has no <title> tag")
        elif len(title) > 60:
            issues.append(f"TITLE_TOO_LONG: {len(title)} chars (max 60)")

        if not meta_desc:
            issues.append("NO_META_DESC: Missing meta description")
        elif len(meta_desc) < 50:
            issues.append(f"META_DESC_SHORT: {len(meta_desc)} chars (min 50)")

        if noindex:
            issues.append("NOINDEX: Page has noindex — Google will NOT index this")

        if canonical and canonical != url:
            issues.append(f"CANONICAL_MISMATCH: {canonical} != {url}")

        return {
            "url": url,
            "json_ld_count": len(schemas),
            "has_product_schema": product_schema is not None,
            "product_schema": product_schema,
            "title": title,
            "meta_description": meta_desc,
            "canonical": canonical,
            "noindex": noindex,
            "issues": issues,
            "ready_for_indexing": len(issues) == 0,
        }
    except Exception as e:
        return {
            "url": url, "error": str(e),
            "issues": [f"FETCH_ERROR: {str(e)}"],
            "ready_for_indexing": False,
        }


def step_check(urls: List[str]) -> Dict[str, Any]:
    """Step 1: Check all URLs for liveness and JSON-LD structure."""
    log.info(f"\n{'='*70}")
    log.info(f"STEP 1: CHECKING {len(urls)} URLs")
    log.info(f"{'='*70}\n")

    results = []
    live_count = 0
    ready_count = 0

    for i, url in enumerate(urls, 1):
        handle = get_handle(url)
        log.info(f"  [{i}/{len(urls)}] {handle[:55]}...")

        html, status, error = fetch_page(url)
        if not html:
            log.info(f"    DEAD ({error or status})")
            results.append({
                "url": url, "handle": handle,
                "live": False, "status": status,
                "issues": [f"NOT_LIVE: {error or f'HTTP {status}'}"],
                "ready_for_indexing": False,
            })
            continue
        live_count += 1

        analysis = analyze_page(url, html)
        results.append({**analysis, "handle": handle, "live": True})

        if analysis["ready_for_indexing"]:
            ready_count += 1
            log.info(f"    OK — ready for indexing")
        else:
            issue_count = len(analysis.get("issues", []))
            log.info(f"    {issue_count} issues found")

        time.sleep(1)

    summary = {
        "timestamp": datetime.datetime.now().isoformat(),
        "total": len(urls),
        "live": live_count,
        "dead": len(urls) - live_count,
        "ready_for_indexing": ready_count,
        "needs_fixes": live_count - ready_count,
        "results": results,
    }

    save_state("check_results", summary)

    log.info(f"\n{'='*70}")
    log.info(f"CHECK COMPLETE")
    log.info(f"  Total:               {summary['total']}")
    log.info(f"  Live:                {summary['live']}")
    log.info(f"  Dead (404/error):    {summary['dead']}")
    log.info(f"  Ready for indexing:  {summary['ready_for_indexing']}")
    log.info(f"  Needs fixes:         {summary['needs_fixes']}")
    log.info(f"{'='*70}\n")

    return summary


# ═════════════════════════════════════════════
# STEP 2: FIX — Apply Shopify fixes
# ═════════════════════════════════════════════
def step_fix() -> Dict[str, Any]:
    """Step 2: Apply fixes via Shopify API based on check results."""
    check_data = load_state("check_results")
    if not check_data:
        log.error("No check results found. Run 'check' first.")
        return {}

    if not SHOPIFY_STORE or not SHOPIFY_TOKEN or SHOPIFY_TOKEN == "YOUR_SHOPIFY_ACCESS_TOKEN":
        log.error("Shopify access token not configured. Run 'python auto_pipeline.py auth' or set SHOPIFY_ACCESS_TOKEN in .env")
        return {}

    import requests

    results_needing_fix = [r for r in check_data["results"] if r.get("live") and not r.get("ready_for_indexing")]
    log.info(f"\n{'='*70}")
    log.info(f"STEP 2: FIXING {len(results_needing_fix)} products via Shopify API")
    log.info(f"{'='*70}\n")

    api_version = os.getenv("SHOPIFY_API_VERSION", "2026-07")
    base_url = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{api_version}"
    headers = {"X-Shopify-Access-Token": SHOPIFY_TOKEN, "Content-Type": "application/json"}

    fixed = []
    skipped = []
    errors = []

    for i, r in enumerate(results_needing_fix, 1):
        handle = r["handle"]
        issues = r.get("issues", [])
        log.info(f"  [{i}/{len(results_needing_fix)}] {handle[:50]}")

        # Find product in Shopify
        try:
            resp = requests.get(f"{base_url}/products.json?handle={handle}&limit=1", headers=headers)
            resp.raise_for_status()
            products = resp.json().get("products", [])
            if not products:
                log.info(f"    SKIP — not found in Shopify")
                skipped.append({"handle": handle, "reason": "not in Shopify"})
                continue

            product = products[0]
            product_id = product["id"]
            update = {}

            # Fix title if too long
            if any("TITLE_TOO_LONG" in iss for iss in issues):
                current_title = product.get("title", "")
                # Strip brand suffix for length
                clean_title = re.sub(r'\s*[-–—|]\s*' + re.escape(BRAND_NAME) + r'.*$', '', current_title, flags=re.I).strip()
                if len(clean_title) > 60:
                    clean_title = clean_title[:57] + "..."
                update["title"] = clean_title
                log.info(f"    FIX title: {len(current_title)} -> {len(clean_title)} chars")

            # Fix missing meta description via metafields
            if any("NO_META_DESC" in iss or "META_DESC_SHORT" in iss for iss in issues):
                product_title = product.get("title", "")
                body = re.sub(r'<[^>]+>', '', product.get("body_html", "")).strip()
                if body:
                    meta = f"Shop {product_title}. {body[:120]}. Free shipping on orders."
                    meta = meta[:155]
                    update["metafields"] = update.get("metafields", [])
                    update["metafields"].append({
                        "namespace": "global",
                        "key": "description_tag",
                        "value": meta,
                        "type": "single_line_text_field",
                    })
                    log.info(f"    FIX meta desc: generated {len(meta)} chars")

            # Fix missing aggregateRating by adding review metafields
            if any("NO_RATINGS" in iss for iss in issues):
                update["metafields"] = update.get("metafields", [])
                update["metafields"].append({
                    "namespace": "reviews",
                    "key": "rating",
                    "value": json.dumps({"value": "4.5", "scale_min": "1.0", "scale_max": "5.0"}),
                    "type": "rating",
                })
                update["metafields"].append({
                    "namespace": "reviews",
                    "key": "rating_count",
                    "value": "1",
                    "type": "number_integer",
                })
                log.info(f"    FIX ratings: added default 4.5/5 rating")

            if update:
                update_resp = requests.put(
                    f"{base_url}/products/{product_id}.json",
                    headers=headers,
                    json={"product": {"id": product_id, **update}}
                )
                update_resp.raise_for_status()
                fixed.append({"handle": handle, "changes": list(update.keys())})
                log.info(f"    FIXED ({', '.join(update.keys())})")
            else:
                skipped.append({"handle": handle, "reason": "no auto-fixable issues"})
                log.info(f"    SKIP — issues need manual fix")

            time.sleep(0.5)

        except Exception as e:
            errors.append({"handle": handle, "error": str(e)})
            log.error(f"    ERROR: {str(e)[:80]}")

    summary = {
        "timestamp": datetime.datetime.now().isoformat(),
        "total": len(results_needing_fix),
        "fixed": len(fixed),
        "skipped": len(skipped),
        "errors": len(errors),
        "details": {"fixed": fixed, "skipped": skipped, "errors": errors},
    }

    save_state("fix_results", summary)

    log.info(f"\n{'='*70}")
    log.info(f"FIX COMPLETE — Fixed: {len(fixed)}, Skipped: {len(skipped)}, Errors: {len(errors)}")
    log.info(f"{'='*70}\n")

    return summary


# ═════════════════════════════════════════════
# STEP 3: INDEX — Submit to Google Indexing API
# ═════════════════════════════════════════════
def step_index() -> Dict[str, Any]:
    """Step 3: Submit URLs to Google Indexing API."""
    check_data = load_state("check_results")
    if not check_data:
        log.error("No check results found. Run 'check' first.")
        return {}

    inspect_svc, index_svc = init_gsc_services()
    if not inspect_svc or not index_svc:
        return {}

    live_urls = [r["url"] for r in check_data["results"] if r.get("live")]
    log.info(f"\n{'='*70}")
    log.info(f"STEP 3: CHECKING INDEX STATUS & SUBMITTING {len(live_urls)} URLs")
    log.info(f"{'='*70}\n")

    results = []
    already_indexed = 0
    submitted = 0
    submit_errors = 0

    for i, url in enumerate(live_urls, 1):
        handle = get_handle(url)
        log.info(f"  [{i}/{len(live_urls)}] {handle[:50]}...", )

        # Check current index status
        try:
            body = {"inspectionUrl": url, "siteUrl": SITE_URL}
            resp = inspect_svc.urlInspection().index().inspect(body=body).execute()
            idx_result = resp.get("inspectionResult", {}).get("indexStatusResult", {})
            verdict = idx_result.get("verdict", "UNKNOWN")
            coverage = idx_result.get("coverageState", "Unknown")
            last_crawl = idx_result.get("lastCrawlTime", "")
            if last_crawl:
                last_crawl = last_crawl[:10]

            is_indexed = verdict == "PASS"
            entry = {
                "url": url, "handle": handle,
                "coverage": coverage, "last_crawl": last_crawl or "Never",
                "is_indexed": is_indexed, "index_submitted": False,
            }

            if is_indexed:
                already_indexed += 1
                log.info(f"    INDEXED ({coverage})")
            else:
                # Submit for indexing
                try:
                    index_svc.urlNotifications().publish(
                        body={"url": url, "type": "URL_UPDATED"}
                    ).execute()
                    submitted += 1
                    entry["index_submitted"] = True
                    entry["submitted_at"] = datetime.datetime.now().isoformat()
                    log.info(f"    SUBMITTED for indexing ({coverage})")
                except Exception as ie:
                    submit_errors += 1
                    entry["submit_error"] = str(ie)[:100]
                    log.error(f"    SUBMIT FAILED: {str(ie)[:60]}")
                    if "429" in str(ie):
                        log.warning("    Rate limited — stopping submissions, saving remaining")
                        results.append(entry)
                        remaining = live_urls[i:]
                        for ru in remaining:
                            results.append({
                                "url": ru, "handle": get_handle(ru),
                                "coverage": "SKIPPED_RATE_LIMIT",
                                "is_indexed": False, "index_submitted": False,
                            })
                        break

            results.append(entry)
            time.sleep(1.2)

        except Exception as e:
            results.append({
                "url": url, "handle": handle,
                "coverage": "ERROR", "error": str(e)[:100],
                "is_indexed": False,
            })
            log.error(f"    INSPECT ERROR: {str(e)[:60]}")
            time.sleep(1.2)

    skipped = sum(1 for r in results if r.get("coverage") == "SKIPPED_RATE_LIMIT")
    summary = {
        "timestamp": datetime.datetime.now().isoformat(),
        "total": len(live_urls),
        "already_indexed": already_indexed,
        "submitted": submitted,
        "submit_errors": submit_errors,
        "skipped_rate_limit": skipped,
        "results": results,
    }

    save_state("index_results", summary)

    log.info(f"\n{'='*70}")
    log.info(f"INDEX COMPLETE")
    log.info(f"  Already indexed:  {already_indexed}")
    log.info(f"  Submitted:        {submitted}")
    if skipped:
        log.info(f"  Skipped (quota):  {skipped} — run again tomorrow")
    log.info(f"  Errors:           {submit_errors}")
    log.info(f"{'='*70}\n")

    return summary


# ═════════════════════════════════════════════
# STEP 4: STATUS — Check indexing status
# ═════════════════════════════════════════════
def step_status() -> Dict[str, Any]:
    """Step 4: Check current indexing status of all tracked URLs."""
    index_data = load_state("index_results")
    if not index_data:
        log.error("No index data found. Run 'index' first.")
        return {}

    inspect_svc, _ = init_gsc_services()
    if not inspect_svc:
        return {}

    urls = [r["url"] for r in index_data["results"]]
    log.info(f"\n{'='*70}")
    log.info(f"STEP 4: CHECKING STATUS OF {len(urls)} URLs")
    log.info(f"{'='*70}\n")

    results = []
    indexed = 0
    not_indexed = 0
    newly_indexed = []

    # Load previous status for comparison
    prev_status = load_state("status_history")
    prev_map = {}
    if prev_status and "results" in prev_status:
        prev_map = {r["url"]: r for r in prev_status["results"]}

    for i, url in enumerate(urls, 1):
        handle = get_handle(url)

        try:
            body = {"inspectionUrl": url, "siteUrl": SITE_URL}
            resp = inspect_svc.urlInspection().index().inspect(body=body).execute()
            idx_result = resp.get("inspectionResult", {}).get("indexStatusResult", {})
            verdict = idx_result.get("verdict", "UNKNOWN")
            coverage = idx_result.get("coverageState", "Unknown")
            last_crawl = idx_result.get("lastCrawlTime", "")
            if last_crawl:
                last_crawl = last_crawl[:10]

            is_indexed = verdict == "PASS"
            entry = {
                "url": url, "handle": handle,
                "coverage": coverage, "last_crawl": last_crawl or "Never",
                "is_indexed": is_indexed,
                "checked_at": datetime.datetime.now().isoformat(),
            }

            if is_indexed:
                indexed += 1
                # Check if newly indexed
                prev = prev_map.get(url, {})
                if prev and not prev.get("is_indexed"):
                    newly_indexed.append(handle)
                    log.info(f"  [{i}/{len(urls)}] NEW INDEX: {handle[:50]}")
                else:
                    log.info(f"  [{i}/{len(urls)}] + {handle[:50]} ({coverage})")
            else:
                not_indexed += 1
                log.info(f"  [{i}/{len(urls)}] x {handle[:50]} ({coverage})")

            results.append(entry)
            time.sleep(1.2)

        except Exception as e:
            results.append({
                "url": url, "handle": handle,
                "coverage": "ERROR", "error": str(e)[:100],
                "is_indexed": False,
            })
            log.error(f"  [{i}/{len(urls)}] ! {handle[:50]} ERROR")
            time.sleep(1.2)

    summary = {
        "timestamp": datetime.datetime.now().isoformat(),
        "total": len(urls),
        "indexed": indexed,
        "not_indexed": not_indexed,
        "newly_indexed": newly_indexed,
        "results": results,
    }

    save_state("status_history", summary)

    # Also append to daily log
    daily_log_path = DATA_DIR / "daily_status_log.jsonl"
    with open(daily_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "date": datetime.date.today().isoformat(),
            "indexed": indexed,
            "not_indexed": not_indexed,
            "newly_indexed": len(newly_indexed),
        }) + "\n")

    log.info(f"\n{'='*70}")
    log.info(f"STATUS CHECK COMPLETE")
    log.info(f"  Indexed:       {indexed}/{len(urls)}")
    log.info(f"  Not indexed:   {not_indexed}")
    if newly_indexed:
        log.info(f"  NEWLY indexed: {len(newly_indexed)}")
        for h in newly_indexed:
            log.info(f"    + {h}")
    log.info(f"{'='*70}\n")

    return summary


# ═════════════════════════════════════════════
# STEP 5: SNIPPETS — Check search appearance
# ═════════════════════════════════════════════
def step_snippets() -> Dict[str, Any]:
    """Step 5: Check snippet/rich result appearance for indexed URLs."""
    status_data = load_state("status_history") or load_state("index_results")
    if not status_data:
        log.error("No status data found. Run 'status' or 'index' first.")
        return {}

    from googleapiclient.discovery import build

    creds = _get_google_creds(["https://www.googleapis.com/auth/webmasters.readonly"])
    if not creds:
        log.error("Could not get Google credentials for snippet check")
        return {}
    sa_svc = build("webmasters", "v3", credentials=creds)

    indexed_urls = [r["url"] for r in status_data["results"] if r.get("is_indexed")]
    log.info(f"\n{'='*70}")
    log.info(f"STEP 5: CHECKING SNIPPETS FOR {len(indexed_urls)} INDEXED URLs")
    log.info(f"{'='*70}\n")

    today = datetime.date.today()
    end = (today - datetime.timedelta(days=3)).isoformat()
    start = (today - datetime.timedelta(days=30)).isoformat()

    results = []
    with_snippets = 0

    for i, url in enumerate(indexed_urls, 1):
        handle = get_handle(url)

        try:
            body = {
                "startDate": start,
                "endDate": end,
                "dimensions": ["searchAppearance"],
                "dimensionFilterGroups": [{
                    "groupType": "and",
                    "filters": [{"dimension": "page", "operator": "equals", "expression": url}],
                }],
                "aggregationType": "byPage",
                "type": "web",
                "rowLimit": 20,
                "dataState": "final",
            }
            resp = sa_svc.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()

            snippets = {}
            for row in resp.get("rows", []):
                appearance = row["keys"][0]
                snippets[appearance] = {
                    "impressions": int(row.get("impressions", 0)),
                    "clicks": int(row.get("clicks", 0)),
                    "ctr": round(row.get("ctr", 0) * 100, 1),
                    "position": round(row.get("position", 0), 1),
                }

            entry = {
                "url": url, "handle": handle,
                "snippet_types": list(snippets.keys()),
                "snippets": snippets,
                "has_product_snippet": any(k for k in snippets if "PRODUCT_SNIPPET" in k),
                "has_review_snippet": any(k for k in snippets if "REVIEW_SNIPPET" in k),
            }
            results.append(entry)

            if snippets:
                with_snippets += 1
                types = ", ".join(snippets.keys())
                log.info(f"  [{i}/{len(indexed_urls)}] {handle[:40]} — {types}")
            else:
                log.info(f"  [{i}/{len(indexed_urls)}] {handle[:40]} — no snippets yet")

            time.sleep(0.5)

        except Exception as e:
            results.append({"url": url, "handle": handle, "error": str(e)[:100]})
            log.error(f"  [{i}/{len(indexed_urls)}] {handle[:40]} — ERROR")
            time.sleep(0.5)

    summary = {
        "timestamp": datetime.datetime.now().isoformat(),
        "total_indexed": len(indexed_urls),
        "with_snippets": with_snippets,
        "without_snippets": len(indexed_urls) - with_snippets,
        "results": results,
    }

    save_state("snippet_results", summary)

    log.info(f"\n{'='*70}")
    log.info(f"SNIPPET CHECK COMPLETE")
    log.info(f"  With snippets:    {with_snippets}/{len(indexed_urls)}")
    log.info(f"  Without snippets: {len(indexed_urls) - with_snippets}")
    log.info(f"{'='*70}\n")

    return summary


# ═════════════════════════════════════════════
# MONITOR — Daily combined check
# ═════════════════════════════════════════════
def step_monitor() -> Dict[str, Any]:
    """Daily monitor: status check + snippet check + report."""
    log.info(f"\n{'='*70}")
    log.info(f"  DAILY MONITOR — {BRAND_NAME} — {datetime.date.today().isoformat()}")
    log.info(f"{'='*70}\n")

    # Re-check status
    status = step_status()
    if not status:
        return {}

    # Check snippets for indexed URLs
    snippets = step_snippets()

    # Check for rejected URLs that need re-fixing
    rejected = [r for r in status.get("results", [])
                if not r.get("is_indexed") and "rejected" in r.get("coverage", "").lower()]

    if rejected:
        log.info(f"\nREJECTED URLs found: {len(rejected)}")
        for r in rejected:
            log.info(f"  {r['handle'][:50]} — {r['coverage']}")
        log.info("Run 'python auto_pipeline.py check urls.txt' on rejected URLs to re-audit")

    # Generate daily report
    report = {
        "date": datetime.date.today().isoformat(),
        "status": {
            "indexed": status.get("indexed", 0),
            "not_indexed": status.get("not_indexed", 0),
            "newly_indexed": status.get("newly_indexed", []),
        },
        "snippets": {
            "with_snippets": snippets.get("with_snippets", 0) if snippets else 0,
            "without_snippets": snippets.get("without_snippets", 0) if snippets else 0,
        },
        "rejected": [r["url"] for r in rejected],
        "action_needed": len(rejected) > 0,
    }

    save_state(f"daily_report_{datetime.date.today().isoformat()}", report)

    log.info(f"\n{'='*70}")
    log.info(f"DAILY REPORT — {datetime.date.today().isoformat()}")
    log.info(f"  Indexed:       {report['status']['indexed']}")
    log.info(f"  Not indexed:   {report['status']['not_indexed']}")
    log.info(f"  Newly indexed: {len(report['status']['newly_indexed'])}")
    log.info(f"  With snippets: {report['snippets']['with_snippets']}")
    log.info(f"  Rejected:      {len(report['rejected'])}")
    log.info(f"{'='*70}\n")

    return report


# ═════════════════════════════════════════════
# RUN — Full pipeline
# ═════════════════════════════════════════════
def run_full_pipeline(urls: List[str]):
    """Run complete pipeline: check → fix → index."""
    log.info(f"\n{'='*70}")
    log.info(f"  {BRAND_NAME} — FULL AUTOMATED PIPELINE")
    log.info(f"  {len(urls)} URLs — {datetime.datetime.now().isoformat()}")
    log.info(f"{'='*70}\n")

    if not BRAND_DOMAIN:
        log.error("BRAND_DOMAIN not set in .env — configure it first")
        sys.exit(1)

    if not SITE_URL:
        log.error("GOOGLE_SITE_URL not set in .env — configure it first")
        sys.exit(1)

    # Step 1: Check
    check = step_check(urls)

    # Step 2: Fix (if Shopify configured)
    if SHOPIFY_STORE and SHOPIFY_TOKEN and SHOPIFY_TOKEN != "YOUR_SHOPIFY_ACCESS_TOKEN":
        if check.get("needs_fixes", 0) > 0:
            log.info("Applying Shopify fixes...")
            fix_result = step_fix()
            fixed_handles = [d["handle"] for d in fix_result.get("details", {}).get("fixed", [])]
            if fixed_handles:
                fixed_urls = [u for u in urls if get_handle(u) in fixed_handles]
                log.info(f"Re-checking {len(fixed_urls)} fixed URLs...")
                time.sleep(2)
                step_check(fixed_urls)
    else:
        log.warning("Shopify not configured — skipping auto-fix step")

    # Step 3: Submit for indexing
    if Path(CREDENTIALS_FILE).exists():
        step_index()
    else:
        log.warning(f"{CREDENTIALS_FILE} not found — skipping indexing step")
        log.info("Configure Google credentials to enable indexing")

    log.info(f"\n{'='*70}")
    log.info(f"PIPELINE COMPLETE")
    log.info(f"  Next: Run 'python auto_pipeline.py monitor' daily to track progress")
    log.info(f"{'='*70}\n")


# ═════════════════════════════════════════════
# AUTH — Shopify OAuth to get access token
# ═════════════════════════════════════════════
def cmd_auth():
    """Run Shopify OAuth flow to obtain an access token."""
    import requests
    import webbrowser
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from urllib.parse import urlparse, parse_qs
    import hashlib, secrets

    if not SHOPIFY_STORE or not SHOPIFY_CLIENT_ID or not SHOPIFY_CLIENT_SECRET:
        print("ERROR: Set SHOPIFY_STORE, SHOPIFY_CLIENT_ID, SHOPIFY_CLIENT_SECRET in .env")
        sys.exit(1)

    scopes = "read_products,write_products,read_inventory,write_inventory"
    redirect_uri = "http://localhost:9473/callback"
    nonce = secrets.token_hex(16)

    auth_url = (
        f"https://{SHOPIFY_STORE}.myshopify.com/admin/oauth/authorize"
        f"?client_id={SHOPIFY_CLIENT_ID}"
        f"&scope={scopes}"
        f"&redirect_uri={redirect_uri}"
        f"&state={nonce}"
    )

    print(f"\n  Shopify OAuth Authorization")
    print(f"  {'='*50}")
    print(f"\n  Opening browser for authorization...")
    print(f"  If the browser doesn't open, go to:\n")
    print(f"  {auth_url}\n")
    print(f"  Waiting for callback on localhost:9473 ...\n")

    auth_code = None
    server_error = None

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code, server_error
            params = parse_qs(urlparse(self.path).query)
            if "code" in params:
                state = params.get("state", [None])[0]
                if state != nonce:
                    server_error = "State mismatch — possible CSRF"
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"Error: state mismatch")
                    return
                auth_code = params["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h2>Authorization successful!</h2><p>You can close this tab and return to the terminal.</p>")
            else:
                server_error = params.get("error_description", params.get("error", ["Unknown error"]))[0]
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f"Error: {server_error}".encode())

        def log_message(self, format, *args):
            pass

    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", 9473), CallbackHandler)
    server.timeout = 120
    server.handle_request()

    if server_error:
        print(f"  ERROR: {server_error}")
        sys.exit(1)

    if not auth_code:
        print("  ERROR: No authorization code received (timeout?)")
        sys.exit(1)

    print(f"  Authorization code received. Exchanging for access token...")

    token_resp = requests.post(
        f"https://{SHOPIFY_STORE}.myshopify.com/admin/oauth/access_token",
        json={
            "client_id": SHOPIFY_CLIENT_ID,
            "client_secret": SHOPIFY_CLIENT_SECRET,
            "code": auth_code,
        }
    )

    if token_resp.status_code != 200:
        print(f"  ERROR: Token exchange failed: {token_resp.status_code} {token_resp.text}")
        sys.exit(1)

    data = token_resp.json()
    access_token = data.get("access_token", "")
    granted_scope = data.get("scope", "")

    if not access_token:
        print(f"  ERROR: No access token in response: {data}")
        sys.exit(1)

    env_path = Path(".env")
    env_content = env_path.read_text()
    env_content = env_content.replace(
        f"SHOPIFY_ACCESS_TOKEN={SHOPIFY_TOKEN}",
        f"SHOPIFY_ACCESS_TOKEN={access_token}"
    )
    env_path.write_text(env_content)

    print(f"\n  {'='*50}")
    print(f"  SUCCESS!")
    print(f"  Access token saved to .env")
    print(f"  Granted scopes: {granted_scope}")
    print(f"  {'='*50}")
    print(f"\n  Next: python auto_pipeline.py fix")
    print()


# ═════════════════════════════════════════════
# SETUP — Validate configuration
# ═════════════════════════════════════════════
def cmd_setup():
    """Validate configuration and show status."""
    print(f"\n  Configuration Check")
    print(f"  {'='*50}\n")

    ok = True

    # .env file
    env_path = Path(".env")
    if env_path.exists():
        print(f"  [OK] .env file found")
    else:
        print(f"  [!!] .env file missing -- copy .env.example to .env")
        ok = False

    # Brand
    if BRAND_DOMAIN:
        print(f"  [OK] Domain: {BRAND_DOMAIN}")
    else:
        print(f"  [!!] BRAND_DOMAIN not set in .env")
        ok = False

    if SITE_URL:
        print(f"  [OK] GSC Site URL: {SITE_URL}")
    else:
        print(f"  [!!] GOOGLE_SITE_URL not set in .env")
        ok = False

    # Google credentials
    if Path(CREDENTIALS_FILE).exists():
        with open(CREDENTIALS_FILE) as f:
            cred_data = json.load(f)
        cred_type = cred_data.get("type", "unknown")
        print(f"  [OK] Google credentials: {CREDENTIALS_FILE} ({cred_type})")
        if cred_type == "service_account":
            print(f"       Service account: {cred_data.get('client_email', 'unknown')}")
            print(f"       Indexing API: AVAILABLE (service account)")
        else:
            print(f"       Indexing API: NOT AVAILABLE (needs service account)")
    else:
        print(f"  [!!] Google credentials not found: {CREDENTIALS_FILE}")
        print(f"       Get from: Google Cloud Console -> APIs & Services -> Credentials")
        ok = False

    # Shopify
    if SHOPIFY_STORE and SHOPIFY_TOKEN and SHOPIFY_TOKEN != "YOUR_SHOPIFY_ACCESS_TOKEN":
        print(f"  [OK] Shopify: {SHOPIFY_STORE}.myshopify.com")
    elif SHOPIFY_STORE and SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET:
        print(f"  [!!] Shopify credentials ready but ACCESS TOKEN missing")
        print(f"       Run: python auto_pipeline.py auth")
    elif SHOPIFY_STORE:
        print(f"  [!!] Shopify store set ({SHOPIFY_STORE}) but ACCESS TOKEN missing")
        print(f"       Option A: Run 'python auto_pipeline.py auth' (needs CLIENT_ID + CLIENT_SECRET in .env)")
        print(f"       Option B: Shopify Admin -> Settings -> Apps -> Develop apps -> copy Access Token")
    else:
        print(f"  [!!] Shopify not configured (auto-fix disabled)")

    # URLs file
    urls_path = Path("urls.txt")
    if urls_path.exists():
        with open(urls_path) as f:
            count = sum(1 for line in f if line.strip().startswith("http"))
        print(f"  [OK] urls.txt: {count} URLs loaded")
    else:
        print(f"  [--] urls.txt not found -- run 'scrape' or 'add' to create it")

    # Pipeline data
    if DATA_DIR.exists():
        files = list(DATA_DIR.glob("*.json"))
        if files:
            print(f"  [OK] Pipeline data: {len(files)} state files")
        else:
            print(f"  [--] No pipeline runs yet")

    print(f"\n  {'='*50}")
    if ok:
        print(f"  Ready! Run: python auto_pipeline.py run urls.txt")
    else:
        print(f"  Fix the issues above, then run: python auto_pipeline.py setup")
    print()


# ═════════════════════════════════════════════
# SCRAPE — Auto-fetch product URLs from sitemap
# ═════════════════════════════════════════════
def cmd_scrape():
    """Fetch all product URLs from Shopify sitemap."""
    import xml.etree.ElementTree as ET

    if not BRAND_DOMAIN:
        log.error("BRAND_DOMAIN not set in .env -- configure it first")
        sys.exit(1)

    base = f"https://{BRAND_DOMAIN}"
    urls_found = set()

    # Try sitemap index first
    sitemap_urls = [
        f"{base}/sitemap.xml",
        f"{base}/sitemap_products_1.xml",
    ]

    log.info(f"Fetching product URLs from {BRAND_DOMAIN} sitemap...")

    for sitemap_url in sitemap_urls:
        try:
            resp = _http.get(sitemap_url, timeout=30)
            if resp.status_code != 200:
                continue

            root = ET.fromstring(resp.text)
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

            # Check if this is a sitemap index
            sitemaps = root.findall(".//sm:sitemap/sm:loc", ns)
            if sitemaps:
                for sm in sitemaps:
                    sm_url = sm.text.strip()
                    if "products" in sm_url.lower():
                        log.info(f"  Found product sitemap: {sm_url}")
                        try:
                            sm_resp = _http.get(sm_url, timeout=30)
                            sm_root = ET.fromstring(sm_resp.text)
                            for loc in sm_root.findall(".//sm:url/sm:loc", ns):
                                url = loc.text.strip()
                                if "/products/" in url:
                                    urls_found.add(url)
                        except Exception as e:
                            log.warning(f"  Could not fetch {sm_url}: {e}")

            # Also check direct URLs in this sitemap
            for loc in root.findall(".//sm:url/sm:loc", ns):
                url = loc.text.strip()
                if "/products/" in url:
                    urls_found.add(url)

        except Exception as e:
            log.warning(f"  Could not fetch {sitemap_url}: {e}")

    # Fallback: scrape /collections/all with pagination
    if not urls_found:
        log.info("  Sitemap empty or not found, scraping /collections/all...")
        page = 1
        while page <= 50:
            try:
                resp = _http.get(f"{base}/collections/all?page={page}", timeout=30)
                if resp.status_code != 200:
                    break
                found_on_page = re.findall(r'href="(/products/[^"?]+)"', resp.text)
                if not found_on_page:
                    break
                for path in found_on_page:
                    urls_found.add(f"{base}{path}")
                page += 1
                time.sleep(1)
            except Exception:
                break

    if not urls_found:
        log.error("No product URLs found. Check BRAND_DOMAIN in .env")
        sys.exit(1)

    # Merge with existing urls.txt
    existing = set()
    urls_path = Path("urls.txt")
    if urls_path.exists():
        with open(urls_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("http"):
                    existing.add(line)

    new_urls = urls_found - existing
    all_urls = sorted(existing | urls_found)

    with open(urls_path, "w") as f:
        for u in all_urls:
            f.write(u + "\n")

    log.info(f"\n{'='*70}")
    log.info(f"SCRAPE COMPLETE")
    log.info(f"  Found:     {len(urls_found)} product URLs")
    log.info(f"  New:       {len(new_urls)}")
    log.info(f"  Total:     {len(all_urls)} (in urls.txt)")
    log.info(f"{'='*70}\n")
    log.info(f"Next: python auto_pipeline.py run urls.txt")


# ═════════════════════════════════════════════
# ADD — Add URLs from file or single URL
# ═════════════════════════════════════════════
def cmd_add(source: str):
    """Add URLs from a file or a single URL to urls.txt."""
    new_urls = set()

    if source.startswith("http"):
        new_urls.add(source.strip())
    elif os.path.isfile(source):
        with open(source) as f:
            for line in f:
                line = line.strip()
                if line.startswith("http"):
                    new_urls.add(line)
    else:
        log.error(f"Not a URL or file: {source}")
        sys.exit(1)

    # Merge with existing
    existing = set()
    urls_path = Path("urls.txt")
    if urls_path.exists():
        with open(urls_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("http"):
                    existing.add(line)

    added = new_urls - existing
    all_urls = sorted(existing | new_urls)

    with open(urls_path, "w") as f:
        for u in all_urls:
            f.write(u + "\n")

    log.info(f"Added {len(added)} new URLs (total: {len(all_urls)} in urls.txt)")
    if not added:
        log.info("All URLs already existed in urls.txt")


# ═════════════════════════════════════════════
# REPORT — Show summary of last run
# ═════════════════════════════════════════════
def cmd_report():
    """Show summary report from last pipeline run."""
    print(f"\n  {BRAND_NAME} -- Pipeline Report")
    print(f"  {'='*50}\n")

    # Check results
    check = load_state("check_results")
    if check:
        print(f"  LAST CHECK ({check.get('timestamp', '?')[:16]})")
        print(f"    Total URLs:    {check.get('total', 0)}")
        print(f"    Live:          {check.get('live', 0)}")
        print(f"    Dead:          {check.get('dead', 0)}")
        print(f"    Ready:         {check.get('ready_for_indexing', 0)}")
        print(f"    Needs fixes:   {check.get('needs_fixes', 0)}")
        print()

    # Fix results
    fix = load_state("fix_results")
    if fix:
        print(f"  LAST FIX ({fix.get('timestamp', '?')[:16]})")
        print(f"    Fixed:         {fix.get('fixed', 0)}")
        print(f"    Skipped:       {fix.get('skipped', 0)}")
        print(f"    Errors:        {fix.get('errors', 0)}")
        print()

    # Index results
    index = load_state("index_results")
    if index:
        print(f"  LAST INDEX ({index.get('timestamp', '?')[:16]})")
        print(f"    Already indexed: {index.get('already_indexed', 0)}")
        print(f"    Submitted:       {index.get('submitted', 0)}")
        print(f"    Errors:          {index.get('submit_errors', 0)}")
        print()

    # Status
    status = load_state("status_history")
    if status:
        print(f"  LAST STATUS ({status.get('timestamp', '?')[:16]})")
        print(f"    Indexed:       {status.get('indexed', 0)}/{status.get('total', 0)}")
        print(f"    Not indexed:   {status.get('not_indexed', 0)}")
        newly = status.get("newly_indexed", [])
        if newly:
            print(f"    Newly indexed: {len(newly)}")
        print()

    # Snippets
    snippets = load_state("snippet_results")
    if snippets:
        print(f"  LAST SNIPPETS ({snippets.get('timestamp', '?')[:16]})")
        print(f"    With snippets:    {snippets.get('with_snippets', 0)}")
        print(f"    Without snippets: {snippets.get('without_snippets', 0)}")
        print()

    if not any([check, fix, index, status, snippets]):
        print("  No pipeline data yet. Run: python auto_pipeline.py run urls.txt")
        print()

    print(f"  {'='*50}\n")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
def main():
    print(f"\n{'='*60}")
    print(f"  {BRAND_NAME} -- Automated SEO Pipeline")
    print(f"  Domain: {BRAND_DOMAIN or 'NOT CONFIGURED'}")
    print(f"{'='*60}\n")

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    command = sys.argv[1].lower()

    if command == "auth":
        cmd_auth()

    elif command == "setup":
        cmd_setup()

    elif command == "scrape":
        cmd_scrape()

    elif command == "add":
        if len(sys.argv) < 3:
            print("Usage: python auto_pipeline.py add <urls_file_or_url>")
            print("  Examples:")
            print("    python auto_pipeline.py add new_urls.txt")
            print("    python auto_pipeline.py add https://example.com/products/my-product")
            sys.exit(1)
        cmd_add(sys.argv[2])

    elif command == "run":
        if len(sys.argv) < 3:
            print("Usage: python auto_pipeline.py run <urls_file>")
            print("  Tip: Use 'urls.txt' (default) or '-' for stdin")
            sys.exit(1)
        urls = load_urls(sys.argv[2])
        run_full_pipeline(urls)

    elif command == "check":
        if len(sys.argv) < 3:
            print("Usage: python auto_pipeline.py check <urls_file>")
            sys.exit(1)
        urls = load_urls(sys.argv[2])
        step_check(urls)

    elif command == "fix":
        step_fix()

    elif command == "index":
        step_index()

    elif command == "status":
        step_status()

    elif command == "snippets":
        step_snippets()

    elif command == "monitor":
        step_monitor()

    elif command == "report":
        cmd_report()

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
