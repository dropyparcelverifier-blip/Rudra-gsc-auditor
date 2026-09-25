#!/usr/bin/env python3
"""
GSC Snippets & Rich Results Monitor
====================================
Extracts product snippet performance, review signals, and SERP appearance from Google Search Console.

Metrics extracted per product URL:
  1. Search Appearance (Product Snippet, Merchant Listings, Review Snippet, etc.)
  2. Product Snippet CTR (product-specific SERP format performance)
  3. Review/Rating signals (if Judge.me or native reviews present)
  4. Impression share by snippet type
  5. Position trends (page 1 vs 2+ performance)

Requires: Google Search Console API credentials (same as auditor)
"""

import time
import datetime
from typing import Dict, Any, List, Optional

# ─────────────────────────────────────────────
# GSC Rich Results & Snippet Data
# ─────────────────────────────────────────────
def get_snippet_appearance(service, site_url: str, url: str, days: int = 90) -> Dict[str, Any]:
    """
    Query GSC Search Analytics for SERP appearance by searchAppearance dimension.

    Returns snippet types present for this URL:
    - PRODUCT_SNIPPET: standard product structured data box
    - MERCHANT_LISTINGS: Google Shopping (if enabled)
    - REVIEW_SNIPPET: star ratings visible in SERP
    - PRODUCT_IMAGE_SNIPPET: image-focused snippet
    - FAQ_SNIPPET: FAQ schema (deprecated May 2026)

    Docs: https://developers.google.com/webmaster-tools/v1/searchanalytics/query
    """
    today = datetime.date.today()
    end = (today - datetime.timedelta(days=3)).isoformat()  # final data
    start = (today - datetime.timedelta(days=days)).isoformat()

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
        resp = service.searchanalytics().query(siteUrl=site_url, body=body).execute()

        snippets = {}
        for row in resp.get("rows", []):
            appearance = row["keys"][0]  # e.g., "PRODUCT_SNIPPET"
            impressions = int(row.get("impressions", 0))
            clicks = int(row.get("clicks", 0))
            ctr = row.get("ctr", 0)
            position = row.get("position", 0)

            snippets[appearance] = {
                "impressions": impressions,
                "clicks": clicks,
                "ctr": round(ctr * 100, 1),
                "avg_position": round(position, 1),
            }

        return snippets

    except Exception as e:
        return {"error": str(e)}


def get_snippet_comparison(service, site_url: str, url: str, days: int = 90) -> Dict[str, Any]:
    """
    Compare performance WITH snippet vs WITHOUT snippet.

    This requires two queries:
    1. All impressions with snippet type specified
    2. Estimate impressions without snippet (harder to isolate)

    For now, returns: snippet type, impr, clicks, CTR for each type present.
    """
    return get_snippet_appearance(service, site_url, url, days)


def get_review_signal_status(service, site_url: str, url: str, days: int = 90) -> Dict[str, Any]:
    """
    Fetch review/rating signal status for a product.

    Indicators:
    - If REVIEW_SNIPPET appears in searchAppearance → product has visible ratings
    - Judge.me integration → aggregateRating in schema
    - Number of reviews (from Shopify API, separate call)

    This function uses GSC data only; complement with Shopify API for review count.
    """
    snippets = get_snippet_appearance(service, site_url, url, days)

    review_data = {
        "has_review_snippet": "REVIEW_SNIPPET" in snippets,
        "review_snippet_stats": snippets.get("REVIEW_SNIPPET", {}),
        "product_snippet_with_rating": "PRODUCT_SNIPPET" in snippets and "REVIEW_SNIPPET" in snippets,
        "appeared_with_reviews_impr": snippets.get("REVIEW_SNIPPET", {}).get("impressions", 0),
        "review_ctr_boost": (
            snippets.get("REVIEW_SNIPPET", {}).get("ctr", 0) -
            snippets.get("PRODUCT_SNIPPET", {}).get("ctr", 0)
        ) if ("REVIEW_SNIPPET" in snippets and "PRODUCT_SNIPPET" in snippets) else None,
    }

    return review_data


def get_product_snippet_performance(service, site_url: str, url: str, days: int = 90) -> Dict[str, Any]:
    """
    Dedicated query for PRODUCT_SNIPPET performance only.
    Shows: how many times this product appeared in the product box on Google.
    """
    today = datetime.date.today()
    end = (today - datetime.timedelta(days=3)).isoformat()
    start = (today - datetime.timedelta(days=days)).isoformat()

    try:
        # Overall metrics with PRODUCT_SNIPPET filter
        # (Note: GSC doesn't have a direct searchAppearance=PRODUCT_SNIPPET filter,
        #  so we get all appearances and extract PRODUCT_SNIPPET separately)

        snippets = get_snippet_appearance(service, site_url, url, days)
        product_snippet = snippets.get("PRODUCT_SNIPPET", {})

        return {
            "url": url,
            "snippet_type": "PRODUCT_SNIPPET",
            "impressions": product_snippet.get("impressions", 0),
            "clicks": product_snippet.get("clicks", 0),
            "ctr": product_snippet.get("ctr", 0),
            "avg_position": product_snippet.get("avg_position", 0),
            "days_analyzed": days,
            "status": "ACTIVE" if product_snippet.get("impressions", 0) > 0 else "NOT_APPEARING",
        }

    except Exception as e:
        return {"error": str(e)}


def get_all_snippet_types_for_product(service, site_url: str, url: str, days: int = 90) -> Dict[str, Any]:
    """
    Master query: get ALL snippet types appearing for this product + their individual performance.
    """
    snippets = get_snippet_appearance(service, site_url, url, days)

    return {
        "url": url,
        "days_analyzed": days,
        "total_snippet_types": len(snippets),
        "snippets": snippets,
        "primary_snippet": max(snippets.items(), key=lambda x: x[1]["impressions"])[0] if snippets else None,
    }


# ─────────────────────────────────────────────
# Merchant & Store Performance
# ─────────────────────────────────────────────
def get_merchant_listings_data(service, site_url: str, url: str, days: int = 90) -> Dict[str, Any]:
    """
    Get MERCHANT_LISTINGS appearance + performance.
    (Requires Google Merchant Center + Shopping feed integration.)
    """
    snippets = get_snippet_appearance(service, site_url, url, days)
    merchant = snippets.get("MERCHANT_LISTINGS", {})

    return {
        "url": url,
        "has_merchant_listings": "MERCHANT_LISTINGS" in snippets,
        "merchant_impressions": merchant.get("impressions", 0),
        "merchant_clicks": merchant.get("clicks", 0),
        "merchant_ctr": merchant.get("ctr", 0),
        "merchant_position": merchant.get("avg_position", 0),
        "recommendation": "Enable Google Shopping feed" if not merchant else "Google Shopping active",
    }


def get_store_wide_snippet_stats(service, site_url: str, days: int = 90) -> Dict[str, Any]:
    """
    Aggregate snippet stats across entire site (not per URL).
    Shows: what snippet types appear most, CTR by type, etc.
    """
    today = datetime.date.today()
    end = (today - datetime.timedelta(days=3)).isoformat()
    start = (today - datetime.timedelta(days=days)).isoformat()

    try:
        body = {
            "startDate": start,
            "endDate": end,
            "dimensions": ["searchAppearance"],
            "aggregationType": "auto",
            "type": "web",
            "rowLimit": 20,
            "dataState": "final",
        }
        resp = service.searchanalytics().query(siteUrl=site_url, body=body).execute()

        stats = {}
        total_impr = 0
        for row in resp.get("rows", []):
            appearance = row["keys"][0]
            impressions = int(row.get("impressions", 0))
            clicks = int(row.get("clicks", 0))
            ctr = row.get("ctr", 0)

            stats[appearance] = {
                "impressions": impressions,
                "clicks": clicks,
                "ctr": round(ctr * 100, 1),
                "impr_share": 0,  # computed below
            }
            total_impr += impressions

        # Compute impression share
        for s in stats.values():
            s["impr_share"] = round(s["impressions"] / total_impr * 100, 1) if total_impr > 0 else 0

        return {
            "site": site_url,
            "days": days,
            "total_impressions": total_impr,
            "snippet_types": stats,
            "top_snippet": max(stats.items(), key=lambda x: x[1]["impressions"])[0] if stats else None,
        }

    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────
# Export & Reporting
# ─────────────────────────────────────────────
def build_snippet_report(results: List[Dict[str, Any]]) -> str:
    """
    Generate text report of snippet performance across audited products.
    """
    report = "SNIPPET & RICH RESULTS PERFORMANCE\n" + "="*60 + "\n\n"

    snippet_counts = {}
    total_products = len(results)
    products_with_snippets = 0

    for r in results:
        url = r.get("url", "")
        snippets = r.get("snippets", {})

        if snippets and not snippets.get("error"):
            products_with_snippets += 1
            for stype, stats in snippets.items():
                snippet_counts[stype] = snippet_counts.get(stype, 0) + 1

    report += f"Products with active snippets: {products_with_snippets}/{total_products} "
    report += f"({round(products_with_snippets/total_products*100, 1)}%)\n\n"

    report += "Snippet Type Breakdown:\n"
    for stype, count in sorted(snippet_counts.items(), key=lambda x: -x[1]):
        report += f"  • {stype}: {count} products\n"

    report += "\n" + "="*60 + "\n"

    return report


if __name__ == "__main__":
    # Example usage (requires GSC API auth)
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    import os

    CREDENTIALS_FILE = "credentials.json"
    SITE_URL = "sc-domain:YOUR_DOMAIN_HERE"
    SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

    # Auth
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=8090)
        with open("token.json", "w") as f:
            f.write(creds.to_json())

    service = build("webmasters", "v3", credentials=creds)

    # Test: fetch snippet data for a product
    test_url = "https://YOUR_DOMAIN_HERE/products/example-product"

    print("Fetching snippet performance...")
    snippets = get_all_snippet_types_for_product(service, SITE_URL, test_url)
    print(f"\n{test_url}")
    print(f"Snippet types: {snippets.get('snippets', {})}")

    print("\n\nStore-wide snippet stats...")
    store_stats = get_store_wide_snippet_stats(service, SITE_URL)
    print(f"Top snippet: {store_stats.get('top_snippet')}")
    print(f"Impression share by type:")
    for stype, stats in store_stats.get("snippet_types", {}).items():
        print(f"  {stype}: {stats['impr_share']}%")
