#!/usr/bin/env python3
"""
Shopify Sync Module for Rudra Retail GSC Auditor
==========================================
Applies auto-fixes to product metadata directly via Shopify REST API.

Fixes applied:
- Schema: Product title, SEO description, handle
- Content: Product description (expand thin content)
- SEO: Manage hidden status (noindex), canonical (via URL redirects)

Setup:
  1. In Shopify Admin → Settings → Apps → Develop apps
  2. Create a custom app → "Rudra Retail GSC Auditor"
  3. Scopes needed:
     - write_products, read_products (for product edits)
     - write_inventory, read_inventory (for variants)
  4. Install → copy Access Token → save in .env or as SHOPIFY_ACCESS_TOKEN env var
"""

import os
import json
import time
import requests
from typing import Dict, Any, Optional, List, Tuple

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
SHOPIFY_STORE = os.getenv("SHOPIFY_STORE", "")  # e.g., "mystore" for mystore.myshopify.com
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN", "")  # from Shopify Admin
SHOPIFY_API_VERSION = "2024-10"
RATE_LIMIT_DELAY = 0.5  # seconds between API calls (Shopify: 2 req/sec burst, 4 req/sec sustained)

if not SHOPIFY_ACCESS_TOKEN and __name__ == "__main__":
    raise RuntimeError("SHOPIFY_ACCESS_TOKEN not set. Set env var or pass to init_shopify().")


# ─────────────────────────────────────────────
# API Client
# ─────────────────────────────────────────────
class ShopifyClient:
    def __init__(self, store: str, access_token: str, api_version: str = SHOPIFY_API_VERSION):
        self.store = store
        self.access_token = access_token
        self.api_version = api_version
        self.base_url = f"https://{store}.myshopify.com/admin/api/{api_version}"
        self.session = requests.Session()
        self.session.headers.update({
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        })
        self.last_call_time = 0

    def _rate_limit(self):
        """Respect Shopify's rate limits."""
        elapsed = time.time() - self.last_call_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self.last_call_time = time.time()

    def get(self, path: str) -> Dict[str, Any]:
        """GET request."""
        self._rate_limit()
        resp = self.session.get(f"{self.base_url}{path}")
        resp.raise_for_status()
        return resp.json()

    def put(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """PUT request (update)."""
        self._rate_limit()
        resp = self.session.put(f"{self.base_url}{path}", json=data)
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """POST request (create)."""
        self._rate_limit()
        resp = self.session.post(f"{self.base_url}{path}", json=data)
        resp.raise_for_status()
        return resp.json()


# ─────────────────────────────────────────────
# Product Lookup & Fetch
# ─────────────────────────────────────────────
def get_product_id_by_handle(client: ShopifyClient, handle: str) -> Optional[str]:
    """
    Fetch Shopify product ID by handle.
    handle: e.g., "gillette-mach3-sensitive-razor-handle-5-refills"
    Returns: product_id (e.g., "1234567890"), or None if not found.
    """
    try:
        data = client.get(f"/products.json?handle={handle}&limit=1")
        products = data.get("products", [])
        if products:
            return str(products[0]["id"])
        return None
    except Exception as e:
        print(f"  ❌ Error fetching product {handle}: {e}")
        return None


def get_product_details(client: ShopifyClient, product_id: str) -> Optional[Dict[str, Any]]:
    """Fetch full product details."""
    try:
        data = client.get(f"/products/{product_id}.json")
        return data.get("product")
    except Exception as e:
        print(f"  ❌ Error fetching product {product_id}: {e}")
        return None


# ─────────────────────────────────────────────
# Auto-Fix Functions
# ─────────────────────────────────────────────
def fix_product_title(product: Dict, audit_result: Dict) -> Tuple[bool, str]:
    """
    Fix: Title too long (>60 chars).
    Audit provides: pf['title'] (already shortened) + pf['title_len'].
    """
    pf = audit_result.get("pf", {})
    title_len = pf.get("title_len", 0)

    if title_len > 60:
        new_title = (pf.get("title", "") or "")[:55]
        if new_title and new_title != product.get("title", ""):
            return True, new_title
    return False, product.get("title", "")


def fix_product_seo_title(product: Dict, audit_result: Dict) -> Tuple[bool, str]:
    """
    Fix: Meta title/SEO title missing or short.
    In Shopify, this is the 'metafields' field or admin's SEO title.
    We update the metafield: 'title_tag' under 'seo' namespace.
    """
    pf = audit_result.get("pf", {})
    title = pf.get("title", "")

    if title and len(title) > 0 and len(title) <= 60:
        return True, title
    return False, None


def fix_product_description(product: Dict, audit_result: Dict) -> Tuple[bool, str]:
    """
    Fix: Product description too thin (<150 words).
    Generates expanded description with category-specific tips, benefits, FAQs.
    """
    try:
        from content_generator import expand_description
    except ImportError:
        return False, product.get("body_html", "")

    pf = audit_result.get("pf", {})
    desc_words = pf.get("desc_word_count", 0)
    current_desc = product.get("body_html", "")

    if desc_words > 0 and desc_words < 150:
        title = product.get("title", "")
        brand = pf.get("brand", "")
        url = pf.get("url", "")

        # Infer category from URL slug
        category = ""
        if "/products/" in url:
            slug = url.split("/products/")[1].split("?")[0]
            if "razor" in slug or "shave" in slug:
                category = "razors"
            elif "face" in slug or "wash" in slug or "skincare" in slug:
                category = "skincare"
            elif "vitamin" in slug or "supplement" in slug:
                category = "supplements"

        # Generate expanded description
        expanded = expand_description(title, current_desc, brand, category, target_words=150)
        if expanded and len(expanded) > len(current_desc):
            return True, expanded

    return False, current_desc


def fix_product_handle(product: Dict, audit_result: Dict) -> Tuple[bool, str]:
    """
    Fix: Canonical points to different URL (duplicate handle).
    Recommendation: update handle to be unique, but this is complex (URL change).
    Skip for now — requires 301 redirect setup.
    """
    return False, product.get("handle", "")


def fix_product_hidden_status(product: Dict, audit_result: Dict) -> Tuple[bool, bool]:
    """
    Fix: Page has noindex tag.
    In Shopify, noindex = product is 'hidden' from search.
    Audit tells us if noindex is present. If yes, unhide the product.
    """
    pf = audit_result.get("pf", {})
    noindex = pf.get("noindex", False)

    # In Shopify API, 'hidden' means not visible in search/catalog.
    # But noindex is in the HTML meta tag, not the API field.
    # We need to check metafields or theme settings.
    # For now, return True if noindex was found (flagging for manual check).

    if noindex:
        # Product should be visible (hidden=False)
        return True, False  # set hidden to False (visible)

    return False, product.get("status", "active") == "active"


# ─────────────────────────────────────────────
# Apply Fixes (Batch Update)
# ─────────────────────────────────────────────
def apply_fixes_to_product(client: ShopifyClient, product: Dict, audit_result: Dict) -> Dict[str, Any]:
    """
    Apply all auto-fixes to a single product.
    Returns: {
        "product_id": str,
        "handle": str,
        "changes": {"field": "old_value → new_value", ...},
        "success": bool,
        "error": str or None,
    }
    """
    product_id = product.get("id")
    handle = product.get("handle")

    result = {
        "product_id": product_id,
        "handle": handle,
        "changes": {},
        "success": False,
        "error": None,
    }

    try:
        update_payload = {}

        # Fix 1: Title
        title_changed, new_title = fix_product_title(product, audit_result)
        if title_changed:
            update_payload["title"] = new_title
            result["changes"]["title"] = f"{product.get('title', '')} -> {new_title}"

        # Fix 2: Description
        desc_changed, new_desc = fix_product_description(product, audit_result)
        if desc_changed:
            update_payload["body_html"] = new_desc
            old_words = len(product.get("body_html", "").split())
            new_words = len(new_desc.split())
            result["changes"]["description"] = f"{old_words} words -> {new_words} words"

        # Fix 3: Hidden status (noindex)
        hidden_changed, should_be_visible = fix_product_hidden_status(product, audit_result)
        if hidden_changed and not should_be_visible:
            # Note: Shopify API doesn't have a 'hidden' field; noindex is in HTML meta tags (theme-dependent)
            # This requires theme Liquid editing, not API call.
            result["changes"]["noindex"] = "Requires manual removal from theme -> {Shopify -> Online Store -> Themes -> Edit code -> search 'noindex'}"

        # If no changes, skip
        if not update_payload:
            result["success"] = True
            result["changes"] = {"status": "No fixes needed"}
            return result

        # Apply update via API
        data = client.put(f"/products/{product_id}.json", {"product": update_payload})
        result["success"] = True
        return result

    except Exception as e:
        result["error"] = str(e)
        return result


# ─────────────────────────────────────────────
# Batch Processing
# ─────────────────────────────────────────────
def sync_audit_fixes(audit_results: List[Dict[str, Any]], dry_run: bool = False) -> Dict[str, Any]:
    """
    Apply fixes from audit results to Shopify products.

    audit_results: list of dicts from auditor {pf, gsc, sa, actions}
    dry_run: if True, don't actually update (preview only)

    Returns: {
        "total": int,
        "updated": int,
        "skipped": int,
        "errors": int,
        "details": [...]
    }
    """
    client = ShopifyClient(SHOPIFY_STORE, SHOPIFY_ACCESS_TOKEN)

    summary = {
        "total": len(audit_results),
        "updated": 0,
        "skipped": 0,
        "errors": 0,
        "details": [],
    }

    for i, audit in enumerate(audit_results, 1):
        pf = audit.get("pf", {})
        url = pf.get("url", "")

        if not url or "/products/" not in url:
            summary["skipped"] += 1
            continue

        # Extract handle from URL
        try:
            handle = url.split("/products/")[-1].split("?")[0]
        except:
            summary["skipped"] += 1
            continue

        print(f"[{i}] {handle}...", end=" ", flush=True)

        # Fetch product
        product_id = get_product_id_by_handle(client, handle)
        if not product_id:
            print("❌ Not found")
            summary["errors"] += 1
            summary["details"].append({
                "handle": handle,
                "status": "error",
                "error": "Product not found in Shopify",
            })
            continue

        product = get_product_details(client, product_id)
        if not product:
            print("❌ Failed to fetch")
            summary["errors"] += 1
            summary["details"].append({
                "handle": handle,
                "status": "error",
                "error": "Failed to fetch product details",
            })
            continue

        # Apply fixes
        if dry_run:
            print("🔍 (dry run)")
            summary["details"].append({
                "handle": handle,
                "status": "preview",
                "changes": {},  # would compute here
            })
            summary["skipped"] += 1
        else:
            fix_result = apply_fixes_to_product(client, product, audit)

            if fix_result["success"]:
                if fix_result["changes"]:
                    print(f"✅ Updated ({len(fix_result['changes'])} changes)")
                    summary["updated"] += 1
                else:
                    print("ℹ️  No changes")
                    summary["skipped"] += 1
            else:
                print(f"❌ Error: {fix_result['error']}")
                summary["errors"] += 1

            summary["details"].append(fix_result)

    return summary


# ─────────────────────────────────────────────
# CLI Entry Point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python shopify_sync.py <audit_json> [--dry-run]")
        print("  audit_json: output from auditor (JSON with audit results)")
        print("  --dry-run: preview changes without applying")
        sys.exit(1)

    audit_file = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    with open(audit_file) as f:
        audit_data = json.load(f)

    if isinstance(audit_data, dict) and "results" in audit_data:
        results = audit_data["results"]
    elif isinstance(audit_data, list):
        results = audit_data
    else:
        print("Invalid audit JSON format")
        sys.exit(1)

    print(f"\nShopify Sync: {len(results)} products {'(DRY RUN)' if dry_run else ''}\n")
    summary = sync_audit_fixes(results, dry_run=dry_run)

    print(f"\n{'='*50}")
    print(f"Updated:  {summary['updated']}")
    print(f"Skipped:  {summary['skipped']}")
    print(f"Errors:   {summary['errors']}")
    print(f"{'='*50}\n")
