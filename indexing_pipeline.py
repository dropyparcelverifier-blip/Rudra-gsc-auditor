#!/usr/bin/env python3
"""
Indexing Pipeline CLI — Rudra Retail GSC Auditor
=================================================
Batch URL inspection and indexing submission with multi-account support.

Commands:
    check    — Inspect URLs via URL Inspection API (multi-account round-robin)
    submit   — Submit non-indexed URLs to Google Indexing API
    daily    — Full daily run (check + submit + snapshot)
    accounts — Show service account status/quota

Usage:
    python indexing_pipeline.py check --source urls_all_sitemap.txt --limit 2000
    python indexing_pipeline.py submit --limit 200 --status unknown
    python indexing_pipeline.py daily
    python indexing_pipeline.py accounts --add credentials2.json
"""

import argparse
import csv
import glob
import json
import os
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
SITE_URL = os.getenv("GOOGLE_SITE_URL", "https://rudraretails.com/")

INDEX_STATUS_FILE = DATA_DIR / "index_status.json"
ACCOUNT_QUOTAS_FILE = DATA_DIR / "account_quotas.json"
DAILY_HISTORY_FILE = DATA_DIR / "daily_history.json"
GSC_REPORTS_FILE = DATA_DIR / "gsc_reports.json"
CHANGE_LOG_FILE = DATA_DIR / "change_log.json"

LEGACY_PROGRESS_FILE = PROJECT_ROOT / "pipeline_data" / "product_status_progress.json"
DEFAULT_URL_SOURCE = PROJECT_ROOT / "urls_all_sitemap.txt"
URL_CLASSIFICATIONS_FILE = DATA_DIR / "url_classifications.json"

PIPELINE_STATUS_FILE = DATA_DIR / "pipeline_status.json"

INSPECT_DAILY_LIMIT = 2000
INDEX_DAILY_LIMIT = 200
SAVE_EVERY = 25
API_DELAY = 0.3
PARALLEL_DELAY = 3.0  # per-worker delay when running parallel (avoids burst rate limits)
MAX_RETRIES = 3
RATE_LIMIT_MAX_WAIT = 600  # max total seconds to spend retrying 429s before giving up on account

# URL types that should NOT be inspected/indexed (waste of quota)
SKIP_PATTERNS = [
    "/cart", "/checkout", "/account", "/account/login", "/account/register",
    "/search", "/policies/", "/apps/", "?variant=", "?page=",
    "/collections/all", "#",
]

# Coverage states that should NOT be submitted for indexing
NO_SUBMIT_COVERAGES = {
    "Submitted and indexed",
    "Indexed, not submitted in sitemap",
    "Page with redirect",
    "Alternate page with proper canonical tag",
    "Duplicate without user-selected canonical",
    "Duplicate, Google chose different canonical than user",
    "Blocked by robots.txt",
    "Blocked due to other 4xx issue",
    "Blocked due to access forbidden (403)",
    "Blocked due to unauthorized request (401)",
}

# Coverage states eligible for indexing submission (high priority first)
SUBMIT_PRIORITY_COVERAGES = [
    "URL is unknown to Google",
    "Discovered - currently not indexed",
    "Crawled - currently not indexed",
]

# Pacific Time offset (UTC-7 during PDT, UTC-8 during PST).
# Google quotas reset at midnight PT.  We use UTC-7 as a safe approximation
# since India is always past midnight PT when IST rolls past ~12:30 PM.
PT_OFFSET = timezone(timedelta(hours=-7))

# ---------------------------------------------------------------------------
# ANSI colors
# ---------------------------------------------------------------------------
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"


def cprint(color: str, text: str, end: str = "\n"):
    try:
        print(f"{color}{text}{C.RESET}", end=end, flush=True)
    except OSError:
        pass


def safe_print(*args, **kwargs):
    try:
        kwargs.setdefault("flush", True)
        print(*args, **kwargs)
    except OSError:
        pass


def _ts():
    return datetime.now().strftime("%H:%M:%S")

def progress_bar(current: int, total: int, width: int = 30) -> str:
    if total == 0:
        return "[" + " " * width + "]  0%"
    pct = current / total
    filled = int(width * pct)
    bar = "=" * filled
    if filled < width:
        bar += ">"
        bar += " " * (width - filled - 1)
    return f"[{bar}] {pct:>4.0%} ({current}/{total})"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------
def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default: Any = None) -> Any:
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            backup = path.with_suffix(".bak")
            if path.exists():
                path.rename(backup)
            return default if default is not None else {}
    return default if default is not None else {}


def save_json(path: Path, data: Any):
    ensure_data_dir()
    tmp = path.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
        tmp.replace(path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def today_pt() -> str:
    """Current date in Pacific Time as YYYY-MM-DD."""
    return datetime.now(PT_OFFSET).strftime("%Y-%m-%d")


def update_pipeline_status(phase: str, state: str, **kwargs):
    """Write pipeline run status to disk so the dashboard can poll it."""
    status = load_json(PIPELINE_STATUS_FILE, {})
    status.update({
        "phase": phase,
        "state": state,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "date": today_pt(),
    })
    status.update(kwargs)
    save_json(PIPELINE_STATUS_FILE, status)


# ---------------------------------------------------------------------------
# URL Classification — smart filtering
# ---------------------------------------------------------------------------
class URLClassifier:
    """Classify URLs to decide: inspect? submit for indexing? track snippets? skip?"""

    @staticmethod
    def url_type(url: str) -> str:
        if "/products/" in url:
            return "product"
        if "/collections/" in url:
            return "collection"
        if "/blogs/" in url:
            return "blog"
        if "/pages/" in url:
            return "page"
        url_path = url.split("//", 1)[-1].split("/", 1)[-1] if "//" in url else url
        if not url_path or url_path == "/" or url_path.rstrip("/") == "":
            return "homepage"
        return "other"

    @staticmethod
    def should_skip(url: str) -> bool:
        for pat in SKIP_PATTERNS:
            if pat in url:
                return True
        return False

    @staticmethod
    def should_inspect(url: str, status: Optional[Dict] = None) -> bool:
        if URLClassifier.should_skip(url):
            return False
        if status is None:
            return True
        coverage = status.get("coverage", "")
        cov_lower = coverage.lower()
        if "blocked by robots" in cov_lower:
            return False
        if "blocked due to access forbidden" in cov_lower:
            return False
        if "blocked due to unauthorized" in cov_lower:
            return False
        return True

    @staticmethod
    def should_submit_for_indexing(url: str, status: Optional[Dict] = None) -> bool:
        if URLClassifier.should_skip(url):
            return False
        if status is None:
            return False
        if status.get("is_indexed"):
            return False
        coverage = status.get("coverage", "")
        if coverage in NO_SUBMIT_COVERAGES:
            return False
        # Only submit if coverage is one we know benefits from submission
        cov_lower = coverage.lower()
        if "unknown" in cov_lower or "discovered" in cov_lower or "crawled" in cov_lower:
            return True
        return False

    @staticmethod
    def needs_snippet_tracking(url: str, status: Optional[Dict] = None) -> bool:
        url_type = URLClassifier.url_type(url)
        if url_type != "product":
            return False
        if status and status.get("is_indexed"):
            return True
        return False

    @staticmethod
    def needs_search_analytics(url: str, status: Optional[Dict] = None) -> bool:
        if URLClassifier.should_skip(url):
            return False
        if status and status.get("is_indexed"):
            return True
        url_type = URLClassifier.url_type(url)
        if url_type in ("product", "collection", "blog", "page", "homepage"):
            return True
        return False

    @staticmethod
    def classify_all(urls: List[str], index_status: Dict) -> Dict[str, Dict]:
        """Classify all URLs, return classification map.

        Returns:
            {url: {type, skip, inspect, submit, snippet, search, reason}}
        """
        result = {}
        for url in urls:
            status = index_status.get(url)
            utype = URLClassifier.url_type(url)
            skip = URLClassifier.should_skip(url)

            if skip:
                result[url] = {
                    "type": utype, "skip": True, "inspect": False,
                    "submit": False, "snippet": False, "search": False,
                    "reason": "Skipped (non-indexable URL pattern)",
                }
                continue

            result[url] = {
                "type": utype,
                "skip": False,
                "inspect": URLClassifier.should_inspect(url, status),
                "submit": URLClassifier.should_submit_for_indexing(url, status),
                "snippet": URLClassifier.needs_snippet_tracking(url, status),
                "search": URLClassifier.needs_search_analytics(url, status),
                "reason": _classify_reason(url, status, utype),
            }
        return result


def _classify_reason(url: str, status: Optional[Dict], utype: str) -> str:
    if status is None:
        return "Never checked"
    coverage = status.get("coverage", "")
    is_indexed = status.get("is_indexed", False)
    if is_indexed:
        return f"Indexed ({coverage})"
    if "blocked" in coverage.lower():
        return f"Blocked ({coverage})"
    return coverage if coverage else "Unknown status"


def cmd_classify(args):
    """Classify all URLs and show what actions apply to each."""
    source_file = Path(args.source) if args.source else DEFAULT_URL_SOURCE

    cprint(C.BOLD + C.CYAN, "\n=== URL Classification ===\n")

    if not source_file.exists():
        cprint(C.RED, f"Source file not found: {source_file}")
        sys.exit(1)

    with open(source_file, "r", encoding="utf-8") as f:
        all_urls = []
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if line.startswith("http"):
                    all_urls.append(line.split()[0].rstrip("/"))
                else:
                    handle = line.split()[0].strip("/")
                    all_urls.append(f"https://rudraretails.com/products/{handle}")

    index_status = load_json(INDEX_STATUS_FILE, {})
    classifications = URLClassifier.classify_all(all_urls, index_status)

    # Summary
    counts = {
        "total": len(all_urls),
        "skip": sum(1 for c in classifications.values() if c["skip"]),
        "inspect": sum(1 for c in classifications.values() if c["inspect"]),
        "submit": sum(1 for c in classifications.values() if c["submit"]),
        "snippet": sum(1 for c in classifications.values() if c["snippet"]),
        "search": sum(1 for c in classifications.values() if c["search"]),
    }

    # Type breakdown
    type_counts: Dict[str, int] = {}
    for c in classifications.values():
        type_counts[c["type"]] = type_counts.get(c["type"], 0) + 1

    cprint(C.WHITE, f"  Total URLs:              {counts['total']:>8}")
    cprint(C.RED,   f"  Skip (non-indexable):     {counts['skip']:>8}")
    cprint(C.CYAN,  f"  Need inspection:         {counts['inspect']:>8}")
    cprint(C.MAGENTA, f"  Submit for indexing:      {counts['submit']:>8}")
    cprint(C.GREEN, f"  Track product snippets:  {counts['snippet']:>8}")
    cprint(C.BLUE,  f"  Track search analytics:  {counts['search']:>8}")

    cprint(C.BOLD, "\n  URL Type Breakdown:")
    for utype, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
        cprint(C.WHITE, f"    {utype:<20} {cnt:>8}")

    # Save classification for the dashboard
    save_json(URL_CLASSIFICATIONS_FILE, {
        "counts": counts,
        "type_breakdown": type_counts,
        "classified_at": today_pt(),
    })

    cprint(C.GREEN, f"\n  Classification saved to {URL_CLASSIFICATIONS_FILE}")
    print()
    return classifications


# ---------------------------------------------------------------------------
# Migration: import legacy data
# ---------------------------------------------------------------------------
def migrate_legacy_data():
    """Import pipeline_data/product_status_progress.json into data/index_status.json."""
    if INDEX_STATUS_FILE.exists():
        return  # already migrated
    if not LEGACY_PROGRESS_FILE.exists():
        return

    cprint(C.YELLOW, "Migrating legacy data from pipeline_data/product_status_progress.json ...")
    legacy = load_json(LEGACY_PROGRESS_FILE, {})

    index_status: Dict[str, Dict] = {}
    for handle, info in legacy.items():
        url = f"https://rudraretails.com/products/{handle}"
        index_status[url] = {
            "coverage": info.get("coverage", ""),
            "last_crawl": info.get("last_crawl", ""),
            "rich_results": info.get("rich_results", []),
            "is_indexed": info.get("is_indexed", False),
            "checked_at": today_pt(),
            "submitted_at": "",
        }

    save_json(INDEX_STATUS_FILE, index_status)
    cprint(C.GREEN, f"  Migrated {len(index_status)} URLs to data/index_status.json")


# ---------------------------------------------------------------------------
# Account / credential management
# ---------------------------------------------------------------------------
def discover_credential_files() -> List[str]:
    """Find all credentials*.json files in project root."""
    pattern = str(PROJECT_ROOT / "credentials*.json")
    files = sorted(glob.glob(pattern))
    return [os.path.basename(f) for f in files]


def load_account_quotas() -> Dict:
    """Load or initialize account_quotas.json."""
    data = load_json(ACCOUNT_QUOTAS_FILE, {"accounts": []})

    # Auto-discover new credential files
    known_files = {a["credentials_file"] for a in data["accounts"]}
    for cred_file in discover_credential_files():
        if cred_file not in known_files:
            idx = len(data["accounts"]) + 1
            data["accounts"].append({
                "name": f"account-{idx}",
                "credentials_file": cred_file,
                "inspect_used": 0,
                "inspect_limit": INSPECT_DAILY_LIMIT,
                "index_used": 0,
                "index_limit": INDEX_DAILY_LIMIT,
                "last_reset": today_pt(),
            })
            cprint(C.CYAN, f"  Auto-discovered: {cred_file} -> account-{idx}")

    # Reset quotas if date changed
    today = today_pt()
    for acct in data["accounts"]:
        if acct.get("last_reset") != today:
            acct["inspect_used"] = 0
            acct["index_used"] = 0
            acct["last_reset"] = today

    save_json(ACCOUNT_QUOTAS_FILE, data)
    return data


def save_account_quotas(data: Dict):
    save_json(ACCOUNT_QUOTAS_FILE, data)


# ---------------------------------------------------------------------------
# Google API helpers
# ---------------------------------------------------------------------------
def build_service(credentials_file: str, api: str = "searchconsole"):
    """Build a Google API service object."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    cred_path = PROJECT_ROOT / credentials_file
    if not cred_path.exists():
        raise FileNotFoundError(f"Credentials file not found: {cred_path}")

    if api == "searchconsole":
        scopes = ["https://www.googleapis.com/auth/webmasters.readonly"]
        creds = service_account.Credentials.from_service_account_file(
            str(cred_path), scopes=scopes)
        return build("searchconsole", "v1", credentials=creds,
                      cache_discovery=False)
    elif api == "indexing":
        scopes = ["https://www.googleapis.com/auth/indexing"]
        creds = service_account.Credentials.from_service_account_file(
            str(cred_path), scopes=scopes)
        return build("indexing", "v3", credentials=creds,
                      cache_discovery=False)
    else:
        raise ValueError(f"Unknown API: {api}")


class AccountPool:
    """Round-robin pool of service accounts with quota tracking."""

    def __init__(self, quota_data: Dict, api: str = "searchconsole"):
        self.quota_data = quota_data
        self.api = api
        self.services: Dict[str, Any] = {}  # credentials_file -> service
        self.current_idx = 0
        self._quota_key = "inspect_used" if api == "searchconsole" else "index_used"
        self._limit_key = "inspect_limit" if api == "searchconsole" else "index_limit"

    def _get_service(self, credentials_file: str):
        if credentials_file not in self.services:
            try:
                self.services[credentials_file] = build_service(
                    credentials_file, self.api)
            except Exception as e:
                cprint(C.RED, f"  Failed to load {credentials_file}: {e}")
                return None
        return self.services[credentials_file]

    def total_remaining(self) -> int:
        """Total remaining quota across all accounts."""
        return sum(
            max(0, a[self._limit_key] - a[self._quota_key])
            for a in self.quota_data["accounts"]
        )

    def get_next(self) -> Optional[Tuple[Any, Dict]]:
        """Get next available service + account info.  Returns None if all exhausted."""
        accounts = self.quota_data["accounts"]
        if not accounts:
            return None

        tried = 0
        while tried < len(accounts):
            acct = accounts[self.current_idx % len(accounts)]
            self.current_idx += 1
            tried += 1

            remaining = acct[self._limit_key] - acct[self._quota_key]
            if remaining <= 0:
                continue

            svc = self._get_service(acct["credentials_file"])
            if svc is None:
                continue

            return svc, acct

        return None

    def record_use(self, acct: Dict):
        acct[self._quota_key] += 1

    def save(self):
        save_account_quotas(self.quota_data)


# ---------------------------------------------------------------------------
# URL Inspection API
# ---------------------------------------------------------------------------
def inspect_url(svc, url: str, site_url: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Inspect a single URL with retries on 500/503."""
    for attempt in range(MAX_RETRIES):
        try:
            result = svc.urlInspection().index().inspect(
                body={"inspectionUrl": url, "siteUrl": site_url}
            ).execute()
            return result, None
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower() or "rate" in err.lower():
                return None, "RATE_LIMITED"
            if ("500" in err or "503" in err) and attempt < MAX_RETRIES - 1:
                wait = 5 * (attempt + 1)
                safe_print(f"    {C.DIM}[{_ts()}] Retry {attempt+1}/{MAX_RETRIES} in {wait}s ...{C.RESET}")
                time.sleep(wait)
                continue
            return None, err
    return None, "MAX_RETRIES"


def parse_inspection_result(result: Dict) -> Dict:
    """Parse URL Inspection API response into our status dict."""
    ir = result.get("inspectionResult", {})
    idx_status = ir.get("indexStatusResult", {})
    rich = ir.get("richResultsResult", {})
    mobile = ir.get("mobileUsabilityResult", {})

    coverage = idx_status.get("coverageState", "Unknown")
    verdict = idx_status.get("verdict", "")
    last_crawl = idx_status.get("lastCrawlTime", "")
    if last_crawl:
        last_crawl = last_crawl[:10]

    is_indexed = verdict == "PASS" or (
        "indexed" in coverage.lower() and "not indexed" not in coverage.lower()
    )

    # Rich results: type + per-item verdict
    rich_results = []
    rich_details = []
    for item in rich.get("detectedItems", []):
        rr_type = item.get("richResultType", "")
        if rr_type:
            rich_results.append(rr_type)
            issues = []
            for sub in item.get("items", []):
                for iss in sub.get("issues", []):
                    issues.append(iss.get("issueMessage", ""))
            rich_details.append({
                "type": rr_type,
                "issues": issues,
            })

    return {
        "coverage": coverage,
        "last_crawl": last_crawl,
        "rich_results": rich_results,
        "rich_verdict": rich.get("verdict", ""),
        "rich_details": rich_details,
        "mobile_verdict": mobile.get("verdict", ""),
        "is_indexed": is_indexed,
        "checked_at": today_pt(),
    }


# ---------------------------------------------------------------------------
# Indexing API (submit for indexing)
# ---------------------------------------------------------------------------
def submit_url_for_indexing(svc, url: str) -> Tuple[bool, str]:
    """Submit a URL via the Indexing API.  Returns (success, message)."""
    for attempt in range(MAX_RETRIES):
        try:
            body = {"url": url, "type": "URL_UPDATED"}
            svc.urlNotifications().publish(body=body).execute()
            return True, "OK"
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower() or "rate" in err.lower():
                return False, "RATE_LIMITED"
            if ("500" in err or "503" in err) and attempt < MAX_RETRIES - 1:
                time.sleep(5 * (attempt + 1))
                continue
            return False, err
    return False, "MAX_RETRIES"


# ---------------------------------------------------------------------------
# CSV export helpers
# ---------------------------------------------------------------------------
def export_status_csvs(index_status: Dict[str, Dict]):
    """Write per-status CSV files to data/."""
    ensure_data_dir()
    buckets: Dict[str, List[str]] = {}
    for url, info in index_status.items():
        coverage = info.get("coverage", "Unknown")
        # Normalize to filename-safe key
        key = coverage.lower().replace(" ", "_").replace("-", "_").replace("__", "_")
        buckets.setdefault(key, []).append(url)

    for key, urls in buckets.items():
        csv_path = DATA_DIR / f"{key}.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["url"])
            for u in sorted(urls):
                writer.writerow([u])
        cprint(C.DIM, f"  Exported {len(urls):>6} URLs -> data/{key}.csv")


# ---------------------------------------------------------------------------
# Command: check
# ---------------------------------------------------------------------------
def cmd_check(args):
    """Inspect URLs via URL Inspection API with multi-account round-robin."""
    source_file = Path(args.source) if args.source else DEFAULT_URL_SOURCE

    cprint(C.BOLD + C.CYAN, "\n=== URL Inspection Check ===\n")

    # Load URLs from source
    if not source_file.exists():
        cprint(C.RED, f"Source file not found: {source_file}")
        sys.exit(1)

    with open(source_file, "r", encoding="utf-8") as f:
        all_urls = []
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                # Handle lines that might have extra content around the URL
                if line.startswith("http"):
                    url = line.split()[0].rstrip("/")
                    # Ensure trailing slash consistency — Google treats the
                    # property URL with a trailing slash, but individual page
                    # URLs should NOT have one.
                    all_urls.append(url)
                else:
                    # Could be just a handle
                    handle = line.split()[0].strip("/")
                    all_urls.append(f"https://rudraretails.com/products/{handle}")

    cprint(C.WHITE, f"  Source: {source_file}")
    cprint(C.WHITE, f"  Total URLs in file: {len(all_urls)}")

    # Migrate legacy data if needed
    migrate_legacy_data()

    # Load existing status
    index_status = load_json(INDEX_STATUS_FILE, {})
    already_checked = set(index_status.keys())

    # Smart filter: skip non-indexable URLs
    skippable = [u for u in all_urls if URLClassifier.should_skip(u)]
    inspectable = [u for u in all_urls if not URLClassifier.should_skip(u)]
    cprint(C.WHITE, f"  Skipped (non-indexable): {len(skippable)}")
    cprint(C.WHITE, f"  Inspectable URLs:    {len(inspectable)}")

    # Filter: new unchecked URLs first, then stale re-checks
    unchecked = [u for u in inspectable if u not in already_checked]
    cprint(C.WHITE, f"  Already checked: {len(already_checked)}")
    cprint(C.WHITE, f"  Never checked:   {len(unchecked)}")

    # Apply limit
    limit = args.limit if args.limit is not None else len(all_urls)

    if unchecked:
        urls_to_check = unchecked[:limit]
        cprint(C.WHITE, f"  Mode: Initial scan ({len(urls_to_check)} new URLs)")
    else:
        urls_to_check = prioritize_urls(inspectable, index_status, limit)
        cprint(C.WHITE, f"  Mode: Monitoring re-check ({len(urls_to_check)} stale URLs)")

    cprint(C.WHITE, f"  Will check this run: {len(urls_to_check)}")

    if not urls_to_check:
        cprint(C.GREEN, "\n  All URLs already checked!")
        return index_status

    # Set up account pool
    quota_data = load_account_quotas()
    pool = AccountPool(quota_data, api="searchconsole")
    available = pool.total_remaining()
    cprint(C.WHITE, f"  Available inspection quota: {available}")

    if available == 0:
        cprint(C.RED, "\n  No inspection quota remaining across any account.")
        cprint(C.YELLOW, "  Quotas reset at midnight Pacific Time (~12:30 PM IST).")
        return index_status

    actual_limit = min(len(urls_to_check), available)
    urls_to_check = urls_to_check[:actual_limit]

    # Counters
    counts: Dict[str, int] = {}
    checked = 0
    errors = 0
    rate_limited = False

    # Build per-account services and split URLs across accounts
    accounts = quota_data["accounts"]
    active_accounts = []
    for acct in accounts:
        remaining = acct["inspect_limit"] - acct["inspect_used"]
        if remaining <= 0:
            continue
        svc = pool._get_service(acct["credentials_file"])
        if svc is None:
            continue
        active_accounts.append((svc, acct, remaining))

    if not active_accounts:
        cprint(C.RED, "\n  No accounts with remaining quota.")
        return index_status

    num_workers = len(active_accounts)
    cprint(C.BOLD, f"\n  Starting parallel inspection of {len(urls_to_check)} URLs across {num_workers} accounts ...\n")

    # Distribute URLs round-robin across accounts
    account_queues: List[List[Tuple[int, str]]] = [[] for _ in range(num_workers)]
    for i, url in enumerate(urls_to_check):
        worker_idx = i % num_workers
        account_queues[worker_idx].append((i, url))

    # Shared state with locks
    _print_lock = Lock()
    _status_lock = Lock()

    def _inspect_one_url(svc, acct, url, _print_lock):
        """Try to inspect a URL, retrying on 429 with exponential backoff."""
        handle = url.split("/products/")[-1] if "/products/" in url else url[-60:]
        short = handle[:50]
        total_waited = 0
        backoff = 10

        while True:
            result, err = inspect_url(svc, url, SITE_URL)

            if err != "RATE_LIMITED":
                return result, err, short

            total_waited += backoff
            if total_waited > RATE_LIMIT_MAX_WAIT:
                with _print_lock:
                    safe_print(f"  {C.DIM}{_ts()} [{acct['name']}]{C.RESET} {short} {C.RED}429 — gave up after {total_waited}s total backoff{C.RESET}")
                return None, "RATE_LIMITED_EXHAUSTED", short

            with _print_lock:
                safe_print(f"  {C.DIM}{_ts()} [{acct['name']}]{C.RESET} {short} {C.YELLOW}429 — waiting {backoff}s (total {total_waited}s){C.RESET}")
            time.sleep(backoff)
            backoff = min(backoff * 2, 120)

    def _inspect_worker(worker_idx, svc, acct, url_batch):
        """Worker: inspect a batch of URLs using one account."""
        local_results = []
        account_dead = False
        for seq, url in url_batch:
            if account_dead:
                break

            result, err, short = _inspect_one_url(svc, acct, url, _print_lock)

            if err == "RATE_LIMITED_EXHAUSTED":
                local_results.append((seq, url, None, "RATE_LIMITED"))
                account_dead = True
                with _print_lock:
                    safe_print(f"  {C.DIM}{_ts()} [{acct['name']}]{C.RESET} {C.RED}Account quota exhausted — stopping worker{C.RESET}")
                continue
            elif err:
                with _print_lock:
                    safe_print(f"  {C.DIM}{_ts()} [{acct['name']}]{C.RESET} {short} {C.RED}ERR: {err[:60]}{C.RESET}")
                local_results.append((seq, url, None, err))
                time.sleep(PARALLEL_DELAY)
                continue

            with _status_lock:
                acct["inspect_used"] += 1
            parsed = parse_inspection_result(result)
            coverage = parsed["coverage"]
            if parsed["is_indexed"]:
                color = C.GREEN
            elif "unknown" in coverage.lower():
                color = C.RED
            else:
                color = C.YELLOW
            with _print_lock:
                safe_print(f"  {C.DIM}{_ts()} [{acct['name']}]{C.RESET} {short} {color}{coverage}{C.RESET}")
            local_results.append((seq, url, parsed, None))

            time.sleep(PARALLEL_DELAY)
        return local_results

    # Launch parallel workers
    all_results = []
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {}
        for w_idx, (svc, acct, _remaining) in enumerate(active_accounts):
            if account_queues[w_idx]:
                fut = executor.submit(_inspect_worker, w_idx, svc, acct, account_queues[w_idx])
                futures[fut] = w_idx

        for fut in as_completed(futures):
            try:
                results = fut.result()
                all_results.extend(results)
            except Exception as e:
                cprint(C.RED, f"  Worker error: {e}")

    # Process results into index_status (sorted by original order)
    all_results.sort(key=lambda r: r[0])
    for seq, url, parsed, err in all_results:
        if err:
            errors += 1
            if err == "RATE_LIMITED":
                rate_limited = True
            continue

        old_entry = index_status.get(url, {})
        if old_entry.get("submitted_at"):
            parsed["submitted_at"] = old_entry["submitted_at"]
        else:
            parsed["submitted_at"] = ""

        if old_entry and old_entry.get("coverage"):
            log_change(url, old_entry, parsed)
            if old_entry.get("coverage") != parsed["coverage"]:
                handle_short = (url.split("/products/")[-1] if "/products/" in url else url[-40:])[:35]
                cprint(C.MAGENTA, f"    CHANGE: {handle_short}: {old_entry['coverage']} -> {parsed['coverage']}")

        parsed["check_count"] = old_entry.get("check_count", 0) + 1
        index_status[url] = parsed
        checked += 1

        coverage = parsed["coverage"]
        counts[coverage] = counts.get(coverage, 0) + 1

        if checked % SAVE_EVERY == 0:
            save_json(INDEX_STATUS_FILE, index_status)
            pool.save()
            update_pipeline_status("inspect", "running",
                                   inspected=checked, inspect_total=len(urls_to_check),
                                   inspect_errors=errors)
            cprint(C.DIM, f"    [{_ts()}] Saved checkpoint — {checked}/{len(urls_to_check)} inspected, {errors} errors")

    # Final save
    save_json(INDEX_STATUS_FILE, index_status)
    pool.save()

    # Summary
    cprint(C.BOLD + C.CYAN, "\n\n=== Inspection Summary ===\n")
    cprint(C.WHITE, f"  Checked:  {checked}")
    cprint(C.WHITE, f"  Errors:   {errors}")
    if rate_limited:
        cprint(C.YELLOW, "  Stopped:  Rate limited (quota exhausted)")
    print()

    total_indexed = sum(1 for v in index_status.values() if v.get("is_indexed"))
    total_not = len(index_status) - total_indexed
    cprint(C.WHITE, f"  Total tracked:   {len(index_status)}")
    cprint(C.GREEN, f"  Total indexed:   {total_indexed}")
    cprint(C.RED,   f"  Total not indexed: {total_not}")
    print()

    # Coverage breakdown
    cprint(C.BOLD, "  Coverage Breakdown (this run):")
    for cov, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        cprint(C.WHITE, f"    {cov:<45} {cnt:>6}")

    # Rich results / enhancements summary
    rich_counts: Dict[str, int] = {}
    rich_verdict_counts: Dict[str, int] = {"PASS": 0, "FAIL": 0, "": 0}
    mobile_counts: Dict[str, int] = {"PASS": 0, "FAIL": 0, "": 0}
    for v in index_status.values():
        for rr in v.get("rich_results", []):
            rich_counts[rr] = rich_counts.get(rr, 0) + 1
        rv = v.get("rich_verdict", "")
        rich_verdict_counts[rv] = rich_verdict_counts.get(rv, 0) + 1
        mv = v.get("mobile_verdict", "")
        mobile_counts[mv] = mobile_counts.get(mv, 0) + 1

    if rich_counts:
        cprint(C.BOLD, "\n  Rich Results / Enhancements:")
        for rr, cnt in sorted(rich_counts.items(), key=lambda x: -x[1]):
            cprint(C.GREEN, f"    {rr:<45} {cnt:>6}")
        rr_pass = rich_verdict_counts.get("PASS", 0)
        rr_fail = rich_verdict_counts.get("FAIL", 0)
        cprint(C.WHITE, f"    Rich verdict PASS: {rr_pass}  FAIL: {rr_fail}")

    mob_pass = mobile_counts.get("PASS", 0)
    mob_fail = mobile_counts.get("FAIL", 0)
    if mob_pass or mob_fail:
        cprint(C.BOLD, "\n  Mobile Usability:")
        cprint(C.GREEN if mob_fail == 0 else C.YELLOW, f"    PASS: {mob_pass}  FAIL: {mob_fail}")

    # Export CSVs
    print()
    export_status_csvs(index_status)

    return index_status


# ---------------------------------------------------------------------------
# Command: submit
# ---------------------------------------------------------------------------
def cmd_submit(args):
    """Submit non-indexed URLs to Google Indexing API."""
    cprint(C.BOLD + C.MAGENTA, "\n=== Indexing Submission ===\n")

    # Migrate if needed
    migrate_legacy_data()

    index_status = load_json(INDEX_STATUS_FILE, {})
    if not index_status:
        cprint(C.RED, "  No index_status.json found.  Run 'check' first.")
        sys.exit(1)

    # Smart filter: only submit URLs that benefit from indexing submission
    status_filter = args.status if args.status else "all"
    candidates = []
    skipped_reasons: Dict[str, int] = {}

    for url, info in index_status.items():
        if info.get("is_indexed"):
            continue

        # Smart classification check
        if not URLClassifier.should_submit_for_indexing(url, info):
            coverage = info.get("coverage", "skipped")
            skipped_reasons[coverage] = skipped_reasons.get(coverage, 0) + 1
            continue

        coverage = info.get("coverage", "").lower()

        if status_filter == "unknown" and "unknown" not in coverage:
            continue
        elif status_filter == "crawled" and "crawled" not in coverage:
            continue
        elif status_filter == "discovered" and "discovered" not in coverage:
            continue

        candidates.append(url)

    # Sort by priority: unknown > discovered > crawled
    def _submit_priority(url: str) -> int:
        cov = index_status.get(url, {}).get("coverage", "").lower()
        if "unknown" in cov:
            return 0
        if "discovered" in cov:
            return 1
        if "crawled" in cov:
            return 2
        return 3

    candidates.sort(key=_submit_priority)

    cprint(C.WHITE, f"  Non-indexed URLs eligible for submission: {len(candidates)}")
    if skipped_reasons:
        cprint(C.DIM, f"  Skipped from submission:")
        for reason, cnt in sorted(skipped_reasons.items(), key=lambda x: -x[1])[:5]:
            cprint(C.DIM, f"    {reason:<45} {cnt:>6}")

    # Apply limit
    limit = args.limit if args.limit is not None else 200
    candidates = candidates[:limit]
    cprint(C.WHITE, f"  Will submit: {len(candidates)}")

    if not candidates:
        cprint(C.GREEN, "\n  Nothing to submit!")
        return

    # Set up account pool for Indexing API
    quota_data = load_account_quotas()
    pool = AccountPool(quota_data, api="indexing")
    available = pool.total_remaining()
    cprint(C.WHITE, f"  Available indexing quota: {available}")

    if available == 0:
        cprint(C.RED, "\n  No indexing quota remaining.")
        return

    actual = min(len(candidates), available)
    candidates = candidates[:actual]

    submitted = 0
    errors = 0

    # Build per-account services for parallel submission
    accounts = quota_data["accounts"]
    active_submit = []
    for acct in accounts:
        remaining = acct["index_limit"] - acct["index_used"]
        if remaining <= 0:
            continue
        svc = pool._get_service(acct["credentials_file"])
        if svc is None:
            continue
        active_submit.append((svc, acct, remaining))

    if not active_submit:
        cprint(C.RED, "\n  No accounts with remaining index quota.")
        return

    num_workers = len(active_submit)
    cprint(C.BOLD, f"\n  Submitting {len(candidates)} URLs across {num_workers} accounts in parallel ...\n")

    # Distribute URLs round-robin
    submit_queues: List[List[Tuple[int, str]]] = [[] for _ in range(num_workers)]
    for i, url in enumerate(candidates):
        submit_queues[i % num_workers].append((i, url))

    _print_lock = Lock()
    _status_lock = Lock()

    def _submit_one_url(svc, acct, url, _print_lock):
        """Try to submit a URL, retrying on 429 with exponential backoff."""
        handle = url.split("/products/")[-1] if "/products/" in url else url[-60:]
        short = handle[:50]
        total_waited = 0
        backoff = 10

        while True:
            ok, msg = submit_url_for_indexing(svc, url)

            if msg != "RATE_LIMITED":
                return ok, msg, short

            total_waited += backoff
            if total_waited > RATE_LIMIT_MAX_WAIT:
                with _print_lock:
                    safe_print(f"  {C.DIM}{_ts()} [{acct['name']}]{C.RESET} {short} {C.RED}429 — gave up after {total_waited}s total backoff{C.RESET}")
                return False, "RATE_LIMITED_EXHAUSTED", short

            with _print_lock:
                safe_print(f"  {C.DIM}{_ts()} [{acct['name']}]{C.RESET} {short} {C.YELLOW}429 — waiting {backoff}s (total {total_waited}s){C.RESET}")
            time.sleep(backoff)
            backoff = min(backoff * 2, 120)

    def _submit_worker(svc, acct, url_batch):
        local_results = []
        account_dead = False
        for seq, url in url_batch:
            if account_dead:
                break

            ok, msg, short = _submit_one_url(svc, acct, url, _print_lock)

            if msg == "RATE_LIMITED_EXHAUSTED":
                local_results.append((seq, url, False, "RATE_LIMITED"))
                account_dead = True
                with _print_lock:
                    safe_print(f"  {C.DIM}{_ts()} [{acct['name']}]{C.RESET} {C.RED}Submit quota exhausted — stopping worker{C.RESET}")
                continue
            elif ok:
                with _status_lock:
                    acct["index_used"] += 1
                with _print_lock:
                    safe_print(f"  {C.DIM}{_ts()} [{acct['name']}]{C.RESET} {short} {C.GREEN}SUBMITTED{C.RESET}")
                local_results.append((seq, url, True, "OK"))
            else:
                with _print_lock:
                    safe_print(f"  {C.DIM}{_ts()} [{acct['name']}]{C.RESET} {short} {C.RED}{msg[:60]}{C.RESET}")
                local_results.append((seq, url, False, msg))

            time.sleep(PARALLEL_DELAY)
        return local_results

    all_submit_results = []
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {}
        for w_idx, (svc, acct, _rem) in enumerate(active_submit):
            if submit_queues[w_idx]:
                fut = executor.submit(_submit_worker, svc, acct, submit_queues[w_idx])
                futures[fut] = w_idx

        for fut in as_completed(futures):
            try:
                results = fut.result()
                all_submit_results.extend(results)
            except Exception as e:
                cprint(C.RED, f"  Worker error: {e}")

    # Process results
    all_submit_results.sort(key=lambda r: r[0])
    for seq, url, ok, msg in all_submit_results:
        if ok:
            submitted += 1
            index_status[url]["submitted_at"] = datetime.now(PT_OFFSET).isoformat()
        else:
            errors += 1

    # Final save
    save_json(INDEX_STATUS_FILE, index_status)
    pool.save()

    cprint(C.BOLD + C.MAGENTA, "\n\n=== Submission Summary ===\n")
    cprint(C.GREEN,  f"  Submitted: {submitted}")
    cprint(C.RED,    f"  Errors:    {errors}")
    cprint(C.WHITE,  f"  Filter:    {status_filter}")


# ---------------------------------------------------------------------------
# Command: daily
# ---------------------------------------------------------------------------
def cmd_daily(args):
    """Full daily run: classify + check + submit + snapshot — fully automatic."""
    try:
        _cmd_daily_inner(args)
    except Exception as exc:
        update_pipeline_status("error", "failed",
                               error=str(exc),
                               traceback=traceback.format_exc())
        cprint(C.RED, f"\n  PIPELINE FAILED: {exc}")
        raise


def _cmd_daily_inner(args):
    cprint(C.BOLD + C.YELLOW, "\n" + "=" * 60)
    cprint(C.BOLD + C.YELLOW, f"  DAILY PIPELINE RUN (AUTOMATIC) — Started {_ts()}")
    cprint(C.BOLD + C.YELLOW, "=" * 60)
    cprint(C.WHITE, f"  Date (PT): {today_pt()}")
    cprint(C.WHITE, f"  Site:      {SITE_URL}")

    # Count accounts
    num_accounts = len(discover_credential_files())
    cprint(C.CYAN, f"  Accounts:  {num_accounts} ({num_accounts * INSPECT_DAILY_LIMIT} inspect/day, {num_accounts * INDEX_DAILY_LIMIT} submit/day)\n")

    _run_start = time.time()
    started_at = datetime.now(timezone.utc).isoformat()
    update_pipeline_status("starting", "running", started_at=started_at,
                           accounts=num_accounts, errors=[])

    # Step 0: Classify URLs
    cprint(C.BOLD, f"STEP 0/4: Smart URL Classification [{_ts()}]")
    update_pipeline_status("classify", "running", started_at=started_at, step="0/4")
    source_file = Path(args.source) if hasattr(args, "source") and args.source else DEFAULT_URL_SOURCE
    all_urls = []
    if source_file.exists():
        with open(source_file, "r", encoding="utf-8") as f:
            all_urls = []
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if line.startswith("http"):
                        all_urls.append(line.split()[0].rstrip("/"))
                    else:
                        handle = line.split()[0].strip("/")
                        all_urls.append(f"https://rudraretails.com/products/{handle}")

        index_status = load_json(INDEX_STATUS_FILE, {})
        classifications = URLClassifier.classify_all(all_urls, index_status)

        counts = {
            "total": len(all_urls),
            "skip": sum(1 for c in classifications.values() if c["skip"]),
            "inspect": sum(1 for c in classifications.values() if c["inspect"]),
            "submit": sum(1 for c in classifications.values() if c["submit"]),
            "snippet": sum(1 for c in classifications.values() if c["snippet"]),
            "search": sum(1 for c in classifications.values() if c["search"]),
        }
        type_counts: Dict[str, int] = {}
        for c in classifications.values():
            type_counts[c["type"]] = type_counts.get(c["type"], 0) + 1

        cprint(C.WHITE,   f"  Total URLs:              {counts['total']:>8}")
        cprint(C.RED,     f"  Skip (non-indexable):     {counts['skip']:>8}")
        cprint(C.CYAN,    f"  Need inspection:         {counts['inspect']:>8}")
        cprint(C.MAGENTA, f"  Eligible for submission: {counts['submit']:>8}")
        cprint(C.GREEN,   f"  Product snippet track:   {counts['snippet']:>8}")
        cprint(C.BLUE,    f"  Search analytics track:  {counts['search']:>8}")
        cprint(C.BOLD, "\n  URL Types:")
        for utype, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
            cprint(C.WHITE, f"    {utype:<20} {cnt:>8}")

        save_json(URL_CLASSIFICATIONS_FILE, {
            "counts": counts,
            "type_breakdown": type_counts,
            "classified_at": today_pt(),
        })
    else:
        cprint(C.YELLOW, f"  Source file not found: {source_file}")
        cprint(C.YELLOW, "  Skipping classification, proceeding with existing data...")

    # Step 1: Check (uses all available inspection quota)
    cprint(C.BOLD, f"\nSTEP 1/4: URL Inspection (smart filtered) [{_ts()}] +{int(time.time() - _run_start)}s")
    update_pipeline_status("inspect", "running", started_at=started_at, step="1/4")
    check_args = argparse.Namespace(
        source=args.source if hasattr(args, "source") and args.source else None,
        limit=None,
    )
    index_status = cmd_check(check_args)
    if index_status is None:
        index_status = load_json(INDEX_STATUS_FILE, {})

    # Step 2: Submit non-indexed URLs (smart filtered — only eligible ones)
    cprint(C.BOLD, f"\nSTEP 2/4: Indexing Submission (smart filtered) [{_ts()}] +{int(time.time() - _run_start)}s")
    update_pipeline_status("submit", "running", started_at=started_at, step="2/4")
    quota_data = load_account_quotas()
    total_index_limit = sum(
        max(0, a["index_limit"] - a["index_used"])
        for a in quota_data["accounts"]
    )
    submit_args = argparse.Namespace(
        limit=total_index_limit if total_index_limit > 0 else 200,
        status="all",
    )
    cmd_submit(submit_args)

    # Step 3: Re-classify after inspection (update counts with fresh data)
    cprint(C.BOLD, f"\nSTEP 3/4: Post-Inspection Classification Update [{_ts()}] +{int(time.time() - _run_start)}s")
    update_pipeline_status("reclassify", "running", started_at=started_at, step="3/4")
    index_status = load_json(INDEX_STATUS_FILE, {})
    if source_file.exists():
        classifications = URLClassifier.classify_all(all_urls, index_status)
        post_counts = {
            "total": len(all_urls),
            "indexed": sum(1 for v in index_status.values() if v.get("is_indexed")),
            "not_indexed": sum(1 for v in index_status.values() if not v.get("is_indexed")),
            "snippet_eligible": sum(1 for c in classifications.values() if c["snippet"]),
            "search_eligible": sum(1 for c in classifications.values() if c["search"]),
        }
        cprint(C.GREEN,   f"  Indexed:                 {post_counts['indexed']:>8}")
        cprint(C.RED,     f"  Not indexed:             {post_counts['not_indexed']:>8}")
        cprint(C.GREEN,   f"  Product snippet track:   {post_counts['snippet_eligible']:>8}")
        cprint(C.BLUE,    f"  Search analytics track:  {post_counts['search_eligible']:>8}")

        save_json(URL_CLASSIFICATIONS_FILE, {
            "counts": post_counts,
            "type_breakdown": type_counts,
            "classified_at": today_pt(),
            "post_inspection": True,
        })

    # Step 4: Snapshot
    cprint(C.BOLD, f"\nSTEP 4/4: Daily Snapshot [{_ts()}] +{int(time.time() - _run_start)}s")
    update_pipeline_status("snapshot", "running", started_at=started_at, step="4/4")
    take_daily_snapshot(index_status)

    # Summary of changes
    change_log = load_json(CHANGE_LOG_FILE, [])
    today_changes = [c for c in change_log if c.get("date") == today_pt()]
    if today_changes:
        cprint(C.BOLD + C.MAGENTA, f"\n  Changes detected today: {len(today_changes)}")
        newly = [c for c in today_changes if c["type"] == "newly_indexed"]
        dropped = [c for c in today_changes if c["type"] == "dropped_from_index"]
        changed = [c for c in today_changes if c["type"] == "status_change"]
        if newly:
            cprint(C.GREEN, f"    Newly indexed:      {len(newly)}")
        if dropped:
            cprint(C.RED, f"    Dropped from index: {len(dropped)}")
        if changed:
            cprint(C.YELLOW, f"    Status changes:     {len(changed)}")

    # Final status: compute summary
    index_status = load_json(INDEX_STATUS_FILE, {})
    total_tracked = len(index_status)
    total_indexed = sum(1 for v in index_status.values() if v.get("is_indexed"))
    completed_at = datetime.now(timezone.utc).isoformat()
    update_pipeline_status("done", "completed",
                           started_at=started_at, completed_at=completed_at,
                           step="4/4",
                           total_tracked=total_tracked,
                           indexed=total_indexed,
                           not_indexed=total_tracked - total_indexed,
                           changes_today=len(today_changes) if today_changes else 0)

    elapsed = int(time.time() - _run_start)
    m, s = divmod(elapsed, 60)
    cprint(C.BOLD + C.GREEN, f"\n  Daily pipeline complete! [{_ts()}] Total: {m}m {s}s\n")


def cmd_monitor(args):
    """Show monitoring status: scan progress, change history, re-check schedule."""
    cprint(C.BOLD + C.CYAN, "\n=== Monitoring Status ===\n")

    index_status = load_json(INDEX_STATUS_FILE, {})
    change_log = load_json(CHANGE_LOG_FILE, [])
    history = load_json(DAILY_HISTORY_FILE, [])

    total = len(index_status)
    indexed = sum(1 for v in index_status.values() if v.get("is_indexed"))
    not_indexed = total - indexed

    # Scan progress
    source_file = Path(args.source) if args.source else DEFAULT_URL_SOURCE
    total_urls_in_source = 0
    if source_file.exists():
        with open(source_file, "r", encoding="utf-8") as f:
            total_urls_in_source = sum(1 for l in f if l.strip() and not l.startswith("#"))

    scan_pct = (total / total_urls_in_source * 100) if total_urls_in_source else 0
    cprint(C.BOLD, "  Scan Progress:")
    cprint(C.WHITE, f"    Total URLs in sitemap:   {total_urls_in_source:>10}")
    cprint(C.WHITE, f"    Inspected so far:        {total:>10} ({scan_pct:.1f}%)")
    cprint(C.GREEN, f"    Indexed:                 {indexed:>10}")
    cprint(C.RED,   f"    Not indexed:             {not_indexed:>10}")
    safe_print(f"    {progress_bar(total, total_urls_in_source, 40)}")

    # Days to complete
    quota_data = load_account_quotas()
    daily_capacity = sum(a["inspect_limit"] for a in quota_data["accounts"])
    remaining = max(0, total_urls_in_source - total)
    days_left = (remaining / daily_capacity) if daily_capacity else float('inf')
    cprint(C.WHITE, f"\n    Daily capacity:          {daily_capacity:>10} inspections/day")
    cprint(C.WHITE, f"    Remaining to scan:       {remaining:>10}")
    cprint(C.CYAN,  f"    Est. days to complete:   {days_left:>10.1f}")

    # Staleness breakdown
    today = datetime.now(PT_OFFSET)
    stale_3d = stale_7d = stale_14d = stale_30d = fresh = 0
    for info in index_status.values():
        checked_str = info.get("checked_at", "")
        if not checked_str:
            stale_30d += 1
            continue
        try:
            checked_date = datetime.strptime(checked_str, "%Y-%m-%d").replace(tzinfo=PT_OFFSET)
            days = (today - checked_date).days
        except ValueError:
            stale_30d += 1
            continue
        if days <= 3:
            fresh += 1
        elif days <= 7:
            stale_3d += 1
        elif days <= 14:
            stale_7d += 1
        elif days <= 30:
            stale_14d += 1
        else:
            stale_30d += 1

    cprint(C.BOLD, "\n  Data Freshness:")
    cprint(C.GREEN,  f"    Fresh (≤3 days):         {fresh:>10}")
    cprint(C.YELLOW, f"    Stale 3-7 days:          {stale_3d:>10}")
    cprint(C.YELLOW, f"    Stale 7-14 days:         {stale_7d:>10}")
    cprint(C.RED,    f"    Stale 14-30 days:        {stale_14d:>10}")
    cprint(C.RED,    f"    Stale >30 days:          {stale_30d:>10}")

    # Coverage breakdown
    breakdown: Dict[str, int] = {}
    for info in index_status.values():
        cov = info.get("coverage", "Unknown")
        breakdown[cov] = breakdown.get(cov, 0) + 1

    cprint(C.BOLD, "\n  Coverage Breakdown:")
    for cov, cnt in sorted(breakdown.items(), key=lambda x: -x[1]):
        pct = cnt / total * 100 if total else 0
        color = C.GREEN if "indexed" in cov.lower() and "not" not in cov.lower() else C.YELLOW if "crawled" in cov.lower() else C.RED
        cprint(color, f"    {cov:<45} {cnt:>6} ({pct:>5.1f}%)")

    # Recent changes
    if change_log:
        recent = change_log[-20:]
        cprint(C.BOLD, f"\n  Recent Changes ({len(change_log)} total):")
        for ch in reversed(recent):
            url_short = ch["url"].split("/products/")[-1] if "/products/" in ch["url"] else ch["url"][-50:]
            ch_type = ch.get("type", "?")
            color = C.GREEN if ch_type == "newly_indexed" else C.RED if ch_type == "dropped_from_index" else C.YELLOW
            cprint(color, f"    {ch['date']} {ch_type:<22} {url_short[:50]}")
            cprint(C.DIM, f"                  {ch.get('old_coverage','')} -> {ch.get('new_coverage','')}")
    else:
        cprint(C.DIM, "\n  No changes recorded yet (run 'daily' to start monitoring)")

    # Daily history trend
    if history and len(history) > 1:
        cprint(C.BOLD, "\n  Daily Trend (last 7 days):")
        for snap in history[-7:]:
            idx = snap.get("indexed", 0)
            ni = snap.get("not_indexed", 0)
            new_idx = snap.get("newly_indexed", 0)
            dropped = snap.get("dropped", 0)
            delta = f"+{new_idx}" if new_idx else ""
            drop_str = f"-{dropped}" if dropped else ""
            cprint(C.WHITE, f"    {snap['date']}  indexed={idx:>6}  not_indexed={ni:>6}  checked={snap.get('checked',0):>5}  {C.GREEN}{delta}{C.RESET} {C.RED}{drop_str}{C.RESET}")

    print()


# ---------------------------------------------------------------------------
# Change tracking
# ---------------------------------------------------------------------------
def log_change(url: str, old_status: Dict, new_status: Dict):
    """Record a status change to change_log.json."""
    old_cov = old_status.get("coverage", "")
    new_cov = new_status.get("coverage", "")
    old_indexed = old_status.get("is_indexed", False)
    new_indexed = new_status.get("is_indexed", False)

    if old_cov == new_cov and old_indexed == new_indexed:
        return

    change = {
        "url": url,
        "date": today_pt(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "old_coverage": old_cov,
        "new_coverage": new_cov,
        "old_indexed": old_indexed,
        "new_indexed": new_indexed,
    }

    if new_indexed and not old_indexed:
        change["type"] = "newly_indexed"
    elif old_indexed and not new_indexed:
        change["type"] = "dropped_from_index"
    else:
        change["type"] = "status_change"

    log = load_json(CHANGE_LOG_FILE, [])
    log.append(change)
    if len(log) > 50000:
        log = log[-50000:]
    save_json(CHANGE_LOG_FILE, log)


def fetch_sitemap_lastmod() -> Dict[str, str]:
    """Fetch Shopify sitemap and extract lastmod dates per URL."""
    import xml.etree.ElementTree as ET
    lastmods: Dict[str, str] = {}
    sitemap_index_url = SITE_URL.rstrip("/") + "/sitemap.xml"

    try:
        import urllib.request
        req = urllib.request.Request(sitemap_index_url, headers={"User-Agent": "RudraRetailBot/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            root = ET.fromstring(resp.read())
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        sub_urls = [loc.text for loc in root.findall(".//sm:loc", ns) if loc.text and "products" in loc.text]
        if not sub_urls:
            sub_urls = [loc.text for loc in root.findall(".//sm:loc", ns) if loc.text]

        for sub_url in sub_urls[:5]:
            try:
                req2 = urllib.request.Request(sub_url, headers={"User-Agent": "RudraRetailBot/1.0"})
                with urllib.request.urlopen(req2, timeout=30) as resp2:
                    sub_root = ET.fromstring(resp2.read())
                for url_el in sub_root.findall(".//sm:url", ns):
                    loc = url_el.find("sm:loc", ns)
                    lastmod = url_el.find("sm:lastmod", ns)
                    if loc is not None and loc.text and lastmod is not None and lastmod.text:
                        lastmods[loc.text.rstrip("/")] = lastmod.text[:10]
            except Exception:
                continue
    except Exception as e:
        cprint(C.DIM, f"  Could not fetch sitemap lastmod: {e}")

    return lastmods


def prioritize_urls(all_urls: List[str], index_status: Dict, limit: int) -> List[str]:
    """Build a priority queue for monitoring.

    Priority order:
    0. Content changed on Shopify since last check (lastmod > checked_at)
    1. Recently submitted but still not indexed (track submission effectiveness)
    2. Never checked (new URLs)
    3. Not indexed + checked > 3 days ago (volatile)
    4. Not indexed + checked > 7 days ago
    5. Indexed + checked > 7 days ago (faster rotation to catch de-indexing)
    6. Indexed + checked > 14 days ago
    """
    today = datetime.now(PT_OFFSET)

    cprint(C.DIM, "  Fetching sitemap lastmod dates for change detection...")
    lastmods = fetch_sitemap_lastmod()
    if lastmods:
        cprint(C.DIM, f"  Got lastmod for {len(lastmods)} URLs")

    content_changed = []
    submitted_pending = []
    never_checked = []
    not_indexed_stale_3d = []
    not_indexed_stale_7d = []
    indexed_stale_7d = []
    indexed_stale_14d = []

    for url in all_urls:
        info = index_status.get(url)
        if info is None:
            never_checked.append(url)
            continue

        checked_str = info.get("checked_at", "")
        if not checked_str:
            never_checked.append(url)
            continue

        try:
            checked_date = datetime.strptime(checked_str, "%Y-%m-%d").replace(tzinfo=PT_OFFSET)
            days_since = (today - checked_date).days
        except ValueError:
            never_checked.append(url)
            continue

        lastmod = lastmods.get(url, "")
        if lastmod and lastmod > checked_str and days_since >= 1:
            content_changed.append(url)
            continue

        if not info.get("is_indexed") and info.get("submitted_at") and days_since >= 2:
            submitted_pending.append(url)
        elif info.get("is_indexed"):
            if days_since >= 14:
                indexed_stale_14d.append(url)
            elif days_since >= 7:
                indexed_stale_7d.append(url)
        else:
            if days_since >= 7:
                not_indexed_stale_7d.append(url)
            elif days_since >= 3:
                not_indexed_stale_3d.append(url)

    if content_changed:
        cprint(C.MAGENTA, f"  Content changed since last check: {len(content_changed)} URLs (priority re-check)")

    queue = []
    for bucket in [content_changed, submitted_pending, never_checked, not_indexed_stale_3d,
                   not_indexed_stale_7d, indexed_stale_7d, indexed_stale_14d]:
        queue.extend(bucket)
        if len(queue) >= limit:
            break

    return queue[:limit]


def take_daily_snapshot(index_status: Optional[Dict] = None):
    """Append a snapshot to daily_history.json."""
    if index_status is None:
        index_status = load_json(INDEX_STATUS_FILE, {})

    total = len(index_status)
    indexed = sum(1 for v in index_status.values() if v.get("is_indexed"))
    not_indexed = total - indexed
    submitted_today = sum(
        1 for v in index_status.values()
        if v.get("submitted_at", "").startswith(today_pt())
    )
    checked_today = sum(
        1 for v in index_status.values()
        if v.get("checked_at") == today_pt()
    )

    # Coverage breakdown
    breakdown: Dict[str, int] = {}
    for info in index_status.values():
        cov = info.get("coverage", "Unknown")
        breakdown[cov] = breakdown.get(cov, 0) + 1

    change_log = load_json(CHANGE_LOG_FILE, [])
    today_changes = [c for c in change_log if c.get("date") == today_pt()]
    newly_indexed_today = sum(1 for c in today_changes if c.get("type") == "newly_indexed")
    dropped_today = sum(1 for c in today_changes if c.get("type") == "dropped_from_index")
    status_changes_today = sum(1 for c in today_changes if c.get("type") == "status_change")

    snapshot = {
        "date": today_pt(),
        "total_urls": total,
        "indexed": indexed,
        "not_indexed": not_indexed,
        "submitted": submitted_today,
        "checked": checked_today,
        "breakdown": breakdown,
        "newly_indexed": newly_indexed_today,
        "dropped": dropped_today,
        "status_changes": status_changes_today,
    }

    history = load_json(DAILY_HISTORY_FILE, [])

    # Replace existing entry for today or append
    replaced = False
    for i, entry in enumerate(history):
        if entry.get("date") == today_pt():
            history[i] = snapshot
            replaced = True
            break
    if not replaced:
        history.append(snapshot)

    save_json(DAILY_HISTORY_FILE, history)

    cprint(C.GREEN,  f"  Snapshot saved for {today_pt()}")
    cprint(C.WHITE,  f"    Total tracked:  {total}")
    cprint(C.GREEN,  f"    Indexed:        {indexed}")
    cprint(C.RED,    f"    Not indexed:    {not_indexed}")
    cprint(C.CYAN,   f"    Checked today:  {checked_today}")
    cprint(C.MAGENTA,f"    Submitted today:{submitted_today}")


# ---------------------------------------------------------------------------
# Command: accounts
# ---------------------------------------------------------------------------
def cmd_accounts(args):
    """Show service account status and quota."""
    cprint(C.BOLD + C.BLUE, "\n=== Service Accounts ===\n")

    # Handle --add
    if args.add:
        add_file = args.add
        if not (PROJECT_ROOT / add_file).exists():
            cprint(C.RED, f"  File not found: {add_file}")
            sys.exit(1)
        quota_data = load_account_quotas()
        known = {a["credentials_file"] for a in quota_data["accounts"]}
        if add_file in known:
            cprint(C.YELLOW, f"  {add_file} already registered.")
        else:
            idx = len(quota_data["accounts"]) + 1
            quota_data["accounts"].append({
                "name": f"account-{idx}",
                "credentials_file": add_file,
                "inspect_used": 0,
                "inspect_limit": INSPECT_DAILY_LIMIT,
                "index_used": 0,
                "index_limit": INDEX_DAILY_LIMIT,
                "last_reset": today_pt(),
            })
            save_account_quotas(quota_data)
            cprint(C.GREEN, f"  Added {add_file} as account-{idx}")
        print()

    # Handle --reset
    if args.reset:
        quota_data = load_account_quotas()
        for acct in quota_data["accounts"]:
            acct["inspect_used"] = 0
            acct["index_used"] = 0
            acct["last_reset"] = today_pt()
        save_account_quotas(quota_data)
        cprint(C.GREEN, "  All quotas reset.\n")

    # Display table
    quota_data = load_account_quotas()
    accounts = quota_data.get("accounts", [])

    if not accounts:
        cprint(C.YELLOW, "  No accounts found.")
        cprint(C.DIM, "  Place credentials*.json in project root to auto-discover,")
        cprint(C.DIM, "  or run: python indexing_pipeline.py accounts --add <file>")
        return

    # Table header
    header = (
        f"  {'Name':<14} {'Credentials':<30} "
        f"{'Inspect':>12} {'Index':>12} {'Last Reset':<12}"
    )
    cprint(C.BOLD, header)
    cprint(C.DIM, "  " + "-" * 86)

    total_inspect_remaining = 0
    total_index_remaining = 0

    for acct in accounts:
        insp_used = acct["inspect_used"]
        insp_limit = acct["inspect_limit"]
        insp_rem = max(0, insp_limit - insp_used)
        idx_used = acct["index_used"]
        idx_limit = acct["index_limit"]
        idx_rem = max(0, idx_limit - idx_used)

        total_inspect_remaining += insp_rem
        total_index_remaining += idx_rem

        insp_color = C.GREEN if insp_rem > 500 else (C.YELLOW if insp_rem > 0 else C.RED)
        idx_color = C.GREEN if idx_rem > 50 else (C.YELLOW if idx_rem > 0 else C.RED)

        row = (
            f"  {acct['name']:<14} {acct['credentials_file']:<30} "
            f"{insp_color}{insp_used}/{insp_limit}{C.RESET:>12} "
            f"{idx_color}{idx_used}/{idx_limit}{C.RESET:>12} "
            f"{acct.get('last_reset', 'N/A'):<12}"
        )
        print(row)

    cprint(C.DIM, "  " + "-" * 86)
    cprint(C.BOLD,
        f"  {'TOTAL':<14} {'':<30} "
        f"{C.CYAN}{total_inspect_remaining} remain{C.RESET:>12} "
        f"{C.CYAN}{total_index_remaining} remain{C.RESET:>12}"
    )
    print()

    # Credential file validation
    cprint(C.BOLD, "  Credential files on disk:")
    for f in discover_credential_files():
        registered = any(a["credentials_file"] == f for a in accounts)
        status = f"{C.GREEN}registered{C.RESET}" if registered else f"{C.YELLOW}unregistered{C.RESET}"
        safe_print(f"    {f} — {status}")
    safe_print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        prog="indexing_pipeline",
        description="Rudra Retail — Batch URL Inspection & Indexing Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python indexing_pipeline.py check
  python indexing_pipeline.py check --source urls_all_sitemap.txt --limit 500
  python indexing_pipeline.py submit --limit 200 --status unknown
  python indexing_pipeline.py daily
  python indexing_pipeline.py accounts
  python indexing_pipeline.py accounts --add credentials2.json
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # check
    p_check = subparsers.add_parser("check", help="Inspect URLs via URL Inspection API")
    p_check.add_argument("--source", type=str, default=None,
                         help="File with URLs, one per line (default: urls_all_sitemap.txt)")
    p_check.add_argument("--limit", type=int, default=None,
                         help="Max URLs to check this run")

    # submit
    p_submit = subparsers.add_parser("submit", help="Submit non-indexed URLs for indexing")
    p_submit.add_argument("--limit", type=int, default=200,
                          help="Max URLs to submit (default: 200)")
    p_submit.add_argument("--status", type=str, default="all",
                          choices=["unknown", "crawled", "discovered", "all"],
                          help="Filter by coverage status (default: all non-indexed)")

    # daily
    p_daily = subparsers.add_parser("daily", help="Full daily run (check + submit + snapshot)")
    p_daily.add_argument("--source", type=str, default=None,
                         help="URL source file for check phase")

    # classify
    p_classify = subparsers.add_parser("classify", help="Smart URL classification — show what needs inspection/indexing/snippet tracking")
    p_classify.add_argument("--source", type=str, default=None,
                            help="URL source file")

    # monitor
    p_monitor = subparsers.add_parser("monitor", help="Show monitoring status, scan progress, change history")
    p_monitor.add_argument("--source", type=str, default=None,
                           help="URL source file (to compute scan progress)")

    # accounts
    p_accounts = subparsers.add_parser("accounts", help="Show service account status/quota")
    p_accounts.add_argument("--add", type=str, default=None,
                            help="Register a new credentials file")
    p_accounts.add_argument("--reset", action="store_true",
                            help="Force-reset all quotas")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Banner
    cprint(C.BOLD + C.CYAN, """
 ___         _            _
|_ _|_ _  __| |_____ __  | |   Rudra Retail
 | || ' \\/ _` / -_) \\ /  |_|   Indexing Pipeline
|___|_||_\\__,_\\___/_\\_\\  (_)   rudraretails.com
    """)

    # Ensure data dir
    ensure_data_dir()

    # Dispatch
    if args.command == "check":
        cmd_check(args)
    elif args.command == "submit":
        cmd_submit(args)
    elif args.command == "daily":
        cmd_daily(args)
    elif args.command == "classify":
        cmd_classify(args)
    elif args.command == "monitor":
        cmd_monitor(args)
    elif args.command == "accounts":
        cmd_accounts(args)


if __name__ == "__main__":
    main()
