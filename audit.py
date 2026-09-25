#!/usr/bin/env python3
"""
Rudra Retail GSC Auditor v1.0
==============================
Audits product URLs against known issues,
calls GSC URL Inspection API + Search Analytics,
outputs a prioritised HTML report.

Docs verified against:
  https://developers.google.com/webmaster-tools/v1/urlInspection.index/inspect
  https://developers.google.com/webmaster-tools/v1/searchanalytics/query
  https://developers.google.com/webmaster-tools/limits
"""

# ─────────────────────────────────────────────
# CONFIG — fill these in before first run
# ─────────────────────────────────────────────
CREDENTIALS_FILE = "credentials.json"   # OAuth Desktop App JSON from Google Cloud
SITE_URL         = "https://YOUR_DOMAIN_HERE/"  # trailing slash required (URL-prefix property)
INPUT_FILE       = "input/urls.txt"     # one product URL per line
OUTPUT_DIR       = "reports"

# Rate limiting (stay well under 600 QPM / 2000 QPD)
DELAY_BETWEEN_CALLS = 0.3  # seconds between API calls
# ─────────────────────────────────────────────

import os, re, json, time, datetime, webbrowser, html as htmllib
import urllib.request, urllib.parse
from pathlib import Path

# Google auth
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

GOOGLEBOT_UA = (
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)

# ─────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────
def get_credentials():
    creds = None
    token_path = "token.json"
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
    return creds


# ─────────────────────────────────────────────
# Stage 1 — Pre-flight (no API, Googlebot UA)
# ─────────────────────────────────────────────
def preflight(url):
    result = {
        "url": url,
        "http_status": None,
        "noindex": False,
        "canonical_self": True,
        "title": None,
        "title_len": 0,
        "desc_len": 0,
        "h1_count": 0,
        "has_product_jsonld": False,
        "has_aggregate_rating": False,
        "gtin": None,
        "brand": None,
        "brand_unknown": False,
        "faq_count": 0,
        "return_days": None,
        "page_kb": 0,
        "preflight_issues": [],
        "preflight_warnings": [],
    }
    try:
        req = urllib.request.Request(url, headers={"User-Agent": GOOGLEBOT_UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            result["http_status"] = r.status
            body = r.read().decode("utf-8", errors="ignore")
        result["page_kb"] = len(body) // 1024
    except urllib.error.HTTPError as e:
        result["http_status"] = e.code
        result["preflight_issues"].append(f"HTTP {e.code}")
        return result
    except Exception as e:
        result["http_status"] = 0
        result["preflight_issues"].append(f"Fetch error: {e}")
        return result

    # noindex
    robots_meta = re.search(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']+)["\']', body, re.I)
    if robots_meta and "noindex" in robots_meta.group(1).lower():
        result["noindex"] = True
        result["preflight_issues"].append("NOINDEX tag found — blocked from Google")

    # canonical
    canon_match = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', body, re.I)
    if canon_match:
        canon_url = canon_match.group(1).rstrip("/")
        clean_url = url.rstrip("/").split("?")[0]
        if canon_url.rstrip("/") != clean_url:
            result["canonical_self"] = False
            result["preflight_warnings"].append(f"Canonical points to different URL: {canon_url}")

    # title
    title_m = re.search(r"<title>(.*?)</title>", body, re.S)
    if title_m:
        title_raw = re.sub(r"<[^>]+>", "", title_m.group(1)).strip()
        title_raw = htmllib.unescape(title_raw)
        # strip site name suffix for length check
        title_core = re.sub(r"\s*[–—|-]\s*Rudra Retail.*$", "", title_raw, flags=re.I).strip()
        result["title"] = title_core
        result["title_len"] = len(title_core)
        if len(title_core) > 60:
            result["preflight_warnings"].append(
                f"Title too long ({len(title_core)} chars, ideal ≤60): {title_core[:60]}…"
            )
    else:
        result["preflight_issues"].append("Title tag missing")

    # meta description
    desc_m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', body, re.I)
    if desc_m:
        result["desc_len"] = len(desc_m.group(1))
        if result["desc_len"] < 120:
            result["preflight_warnings"].append(f"Meta description short ({result['desc_len']} chars)")
    else:
        result["preflight_warnings"].append("Meta description missing")

    # H1
    h1s = re.findall(r"<h1[^>]*>.*?</h1>", body, re.S)
    result["h1_count"] = len(h1s)
    if len(h1s) == 0:
        result["preflight_issues"].append("No H1 tag found")
    elif len(h1s) > 1:
        result["preflight_warnings"].append(f"{len(h1s)} H1 tags found (should be 1)")

    # JSON-LD blocks
    ld_blocks = re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', body, re.S)
    faq_count = 0
    for b in ld_blocks:
        try:
            d = json.loads(b)
        except Exception:
            continue
        t = d.get("@type", "")
        if t == "FAQPage":
            faq_count += 1
        if t == "Product":
            result["has_product_jsonld"] = True
            if d.get("aggregateRating"):
                result["has_aggregate_rating"] = True
            result["gtin"] = d.get("gtin") or d.get("gtin13") or d.get("gtin12")
            brand = (d.get("brand") or {}).get("name", "")
            result["brand"] = brand
            if brand.lower() in ("unknown brand", "unknown", ""):
                result["brand_unknown"] = True
                result["preflight_warnings"].append(f"Brand is '{brand}' — set real brand name")
            # return policy
            offers = d.get("offers", {})
            ret = offers.get("hasMerchantReturnPolicy", {})
            if isinstance(ret, dict):
                days = ret.get("merchantReturnDays")
                if days is not None:
                    result["return_days"] = int(days)
                    if int(days) > 3:
                        result["preflight_issues"].append(
                            f"Return policy schema says {days} days — actual policy is 3-day damaged-only. MANUAL ACTION RISK."
                        )

    result["faq_count"] = faq_count
    if faq_count > 0:
        result["preflight_warnings"].append(
            f"{faq_count} FAQPage JSON-LD block(s) found — FAQ rich results removed by Google May 2026. Remove to reduce page bloat."
        )

    if not result["has_product_jsonld"]:
        result["preflight_issues"].append("Product JSON-LD missing")
    elif not result["has_aggregate_rating"]:
        result["preflight_warnings"].append(
            "aggregateRating missing from Product schema — no star snippets in SERP. Enable JSON-LD in Judge.me settings."
        )
    if result["has_product_jsonld"] and not result["gtin"]:
        result["preflight_warnings"].append("GTIN missing — add UPC from US product listing")

    if result["page_kb"] > 800:
        result["preflight_warnings"].append(
            f"Page size {result['page_kb']}KB (>800KB) — heavy page slows crawl budget"
        )

    return result


# ─────────────────────────────────────────────
# Stage 2 — GSC URL Inspection API
# ─────────────────────────────────────────────
def gsc_inspect(service, url):
    """
    POST https://searchconsole.googleapis.com/v1/urlInspection/index:inspect
    Returns flat dict of what we care about.
    Docs: https://developers.google.com/webmaster-tools/v1/urlInspection.index/inspect
    """
    try:
        body = {
            "inspectionUrl": url,
            "siteUrl": SITE_URL,
            "languageCode": "en-US",
        }
        resp = service.urlInspection().index().inspect(body=body).execute()
        r = resp.get("inspectionResult", {})
        idx = r.get("indexStatusResult", {})
        rr  = r.get("richResultsResult", {})

        # extract rich result issues
        rich_issues = []
        for item_group in rr.get("detectedItems", []):
            rtype = item_group.get("richResultType", "")
            for item in item_group.get("items", []):
                for iss in item.get("issues", []):
                    rich_issues.append({
                        "type": rtype,
                        "item": item.get("name", ""),
                        "message": iss.get("issueMessage", ""),
                        "severity": iss.get("severity", ""),
                    })

        return {
            "gsc_verdict":        idx.get("verdict", "UNKNOWN"),
            "coverage_state":     idx.get("coverageState", "Unknown"),
            "robots_txt_state":   idx.get("robotsTxtState", "UNKNOWN"),
            "indexing_state":     idx.get("indexingState", "UNKNOWN"),
            "page_fetch_state":   idx.get("pageFetchState", "UNKNOWN"),
            "last_crawl_time":    idx.get("lastCrawlTime", "Never crawled"),
            "google_canonical":   idx.get("googleCanonical", ""),
            "user_canonical":     idx.get("userCanonical", ""),
            "crawled_as":         idx.get("crawledAs", "UNKNOWN"),
            "in_sitemap":         bool(idx.get("sitemap")),
            "referring_urls":     idx.get("referringUrls", [])[:3],
            "rich_verdict":       rr.get("verdict", "NEUTRAL"),
            "rich_issues":        rich_issues,
            "gsc_inspect_link":   r.get("inspectionResultLink", ""),
            "gsc_error":          None,
        }
    except Exception as e:
        return {"gsc_error": str(e)}


# ─────────────────────────────────────────────
# Stage 3 — Search Analytics (per URL)
# ─────────────────────────────────────────────
def gsc_analytics(service, url):
    """
    POST https://www.googleapis.com/webmasters/v3/sites/{siteUrl}/searchAnalytics/query
    Docs: https://developers.google.com/webmaster-tools/v1/searchanalytics/query
    aggregationType: byPage required when filtering by page
    """
    today = datetime.date.today()
    end   = (today - datetime.timedelta(days=3)).isoformat()   # final data
    start = (today - datetime.timedelta(days=93)).isoformat()  # ~90 days

    try:
        # 1. Overall metrics for this URL
        body_total = {
            "startDate": start,
            "endDate":   end,
            "dimensions": [],
            "dimensionFilterGroups": [{
                "groupType": "and",
                "filters": [{"dimension": "page", "operator": "equals", "expression": url}],
            }],
            "aggregationType": "byPage",
            "type":            "web",
            "rowLimit":        1,
            "dataState":       "final",
        }
        resp_total = service.searchanalytics().query(
            siteUrl=SITE_URL, body=body_total
        ).execute()
        rows = resp_total.get("rows", [])
        total = rows[0] if rows else {}

        time.sleep(DELAY_BETWEEN_CALLS)

        # 2. Top queries for this URL
        body_queries = {
            "startDate": start,
            "endDate":   end,
            "dimensions": ["query"],
            "dimensionFilterGroups": [{
                "groupType": "and",
                "filters": [{"dimension": "page", "operator": "equals", "expression": url}],
            }],
            "aggregationType": "byPage",
            "type":            "web",
            "rowLimit":        10,
            "dataState":       "final",
        }
        resp_q = service.searchanalytics().query(
            siteUrl=SITE_URL, body=body_queries
        ).execute()
        top_queries = [
            {
                "query":       r["keys"][0],
                "clicks":      int(r.get("clicks", 0)),
                "impressions": int(r.get("impressions", 0)),
                "position":    round(r.get("position", 0), 1),
                "ctr":         round(r.get("ctr", 0) * 100, 1),
            }
            for r in resp_q.get("rows", [])
        ]

        return {
            "clicks":       int(total.get("clicks", 0)),
            "impressions":  int(total.get("impressions", 0)),
            "position":     round(total.get("position", 0), 1),
            "ctr":          round(total.get("ctr", 0) * 100, 1),
            "top_queries":  top_queries,
            "sa_error":     None,
        }
    except Exception as e:
        return {"clicks": 0, "impressions": 0, "position": 0, "ctr": 0,
                "top_queries": [], "sa_error": str(e)}


# ─────────────────────────────────────────────
# Stage 4 — Decision engine
# ─────────────────────────────────────────────
def decide(pf, gsc, sa):
    """Returns list of {priority, category, message, fix} dicts."""
    actions = []

    def add(priority, category, message, fix):
        actions.append({"priority": priority, "category": category,
                        "message": message, "fix": fix})

    # ── Indexing blockers ──────────────────────────────────────
    if pf["noindex"]:
        add(1, "BLOCKED",
            "Page has noindex tag — invisible to Google",
            "Shopify Admin → Products → find product → SEO section → uncheck 'Hide from search engines'. "
            "Or bulk: export CSV, set seo.hidden=0 for this product, re-import.")

    coverage = gsc.get("coverage_state", "")
    if "Crawled" in coverage and "not indexed" in coverage:
        add(1, "QUALITY",
            f"Google crawled but chose NOT to index: '{coverage}'",
            "Improve product description — make it unique, India-specific, add specs. "
            "Avoid copy-pasting from Amazon listing verbatim.")
    elif "Discovered" in coverage and "not indexed" in coverage:
        add(2, "CRAWL BUDGET",
            f"Google knows URL exists but hasn't crawled it yet: '{coverage}'",
            "Add internal links from collection pages and blog posts to this product. "
            "Fix crawl budget: delete off-niche products, reduce 547 nav links to 30.")
    elif "Redirect" in coverage or gsc.get("page_fetch_state") == "REDIRECT_ERROR":
        add(1, "REDIRECT",
            "Redirect error — Google can't follow the redirect",
            "Fix redirect chain in Shopify URL redirects. Ensure destination URL is live.")
    elif gsc.get("page_fetch_state") in ("NOT_FOUND", "SOFT_404"):
        add(1, "404",
            f"Page fetch: {gsc.get('page_fetch_state')} — page not found",
            "Restore product in Shopify or create a 301 redirect to the correct URL.")
    elif gsc.get("page_fetch_state") == "SERVER_ERROR":
        add(1, "SERVER",
            "Google got a 5xx error fetching this page",
            "Check Shopify status page. May be a theme or app conflict.")
    elif gsc.get("robots_txt_state") == "DISALLOWED":
        add(1, "ROBOTS",
            "Blocked by robots.txt",
            "Check robots.txt — the /products/ path should not be disallowed.")

    # ── Canonical mismatch ─────────────────────────────────────
    gc = gsc.get("google_canonical", "")
    uc = gsc.get("user_canonical", "")
    if gc and uc and gc.rstrip("/") != uc.rstrip("/"):
        add(2, "CANONICAL",
            f"Google chose different canonical: {gc}",
            "Check for duplicate product handles (product-name-4). Delete duplicates and 301 redirect.")

    # ── Return policy schema risk ──────────────────────────────
    for iss in pf["preflight_issues"]:
        if "Return policy" in iss or "MANUAL ACTION RISK" in iss:
            add(1, "SCHEMA RISK",
                "Return policy schema says 30 days free return — actual policy is 3-day damaged-only",
                "Edit theme JSON-LD: change merchantReturnDays to 3, "
                "change returnPolicyCategory to MerchantReturnNotPermitted for supplements/beauty.")
            break

    # ── Rich result errors ─────────────────────────────────────
    for ri in gsc.get("rich_issues", []):
        if ri["severity"] == "ERROR":
            add(2, "SCHEMA ERROR",
                f"Rich result ERROR in {ri['type']}: {ri['message']}",
                "Fix Product JSON-LD. Use Google Rich Results Test to validate: "
                "https://search.google.com/test/rich-results")
    if gsc.get("rich_verdict") == "FAIL":
        add(2, "SCHEMA",
            "Rich Results verdict: FAIL — product won't get enhanced SERP appearance",
            "Check Product schema with Rich Results Test. Ensure name, offers (price+currency+availability) are correct.")

    # ── Missing aggregateRating ────────────────────────────────
    if pf["has_product_jsonld"] and not pf["has_aggregate_rating"]:
        add(2, "CTR LOSS",
            "No star snippet — aggregateRating missing from Product JSON-LD",
            "Judge.me App → Settings → Rich Snippets → enable 'Product review JSON-LD'. "
            "One toggle fixes all 312,265 products.")

    # ── Missing GTIN ───────────────────────────────────────────
    if pf["has_product_jsonld"] and not pf["gtin"] and pf["brand"] and not pf["brand_unknown"]:
        add(3, "SCHEMA",
            f"GTIN missing for branded product ({pf['brand']})",
            "Find UPC barcode on US product listing (Amazon/manufacturer site). "
            "Add to Shopify product → Barcode field. Re-export sitemap.")

    # ── Title too long ─────────────────────────────────────────
    if pf["title_len"] > 60:
        add(3, "CTR",
            f"Title {pf['title_len']} chars — Google truncates at ~60 in SERPs",
            f"Shorten to: '{(pf['title'] or '')[:55]}…' | Rudra Retail")

    # ── Low CTR relative to position ──────────────────────────
    pos = sa.get("position", 0)
    ctr = sa.get("ctr", 0)
    if 5 <= pos <= 15 and ctr < 2 and sa.get("impressions", 0) > 50:
        add(3, "CTR",
            f"Ranking pos {pos} but CTR only {ctr}% (should be >2% at this position)",
            "Rewrite title to include search intent keyword first. "
            "Rewrite meta description to include a differentiator (USA import, COD, genuine). "
            "After Judge.me fix, star snippet will also boost CTR.")

    # ── FAQ cleanup ────────────────────────────────────────────
    if pf["faq_count"] > 0:
        add(4, "CLEANUP",
            f"{pf['faq_count']} FAQPage JSON-LD block(s) — FAQ rich results removed May 2026",
            "Remove all FAQPage JSON-LD from theme (sections/main-product.liquid). "
            "Keep FAQ content visible as HTML — just remove the schema markup.")

    # ── Page size ──────────────────────────────────────────────
    if pf["page_kb"] > 800:
        add(4, "PERFORMANCE",
            f"Page is {pf['page_kb']}KB — heavy pages slow crawl and hurt CWV",
            "Reduce collection navigation links from 547 to 30 (theme edit). "
            "Defer non-critical scripts. Target <500KB.")

    # Sort by priority
    actions.sort(key=lambda x: x["priority"])
    return actions


# ─────────────────────────────────────────────
# Priority score (for report sorting)
# ─────────────────────────────────────────────
def priority_score(pf, gsc, sa, actions):
    """Higher = more urgent to fix. Based on impression volume × issue severity."""
    impr = sa.get("impressions", 0)
    has_p1 = any(a["priority"] == 1 for a in actions)
    has_p2 = any(a["priority"] == 2 for a in actions)
    score = impr
    if has_p1: score += 100000
    if has_p2: score += 10000
    return score


# ─────────────────────────────────────────────
# HTML report
# ─────────────────────────────────────────────
STATUS_COLORS = {
    1: ("#ef4444", "🔴"),
    2: ("#f97316", "🟠"),
    3: ("#eab308", "🟡"),
    4: ("#22c55e", "🟢"),
}

def _esc(s):
    return htmllib.escape(str(s)) if s else ""

def build_report(results, output_path):
    now = datetime.datetime.now().strftime("%d %b %Y %H:%M")
    total = len(results)
    has_p1 = sum(1 for r in results if any(a["priority"] == 1 for a in r["actions"]))
    indexed = sum(1 for r in results if "Indexed" in r["gsc"].get("coverage_state",""))

    rows_html = ""
    for i, r in enumerate(results):
        pf      = r["pf"]
        gsc     = r["gsc"]
        sa      = r["sa"]
        actions = r["actions"]

        worst = min((a["priority"] for a in actions), default=4)
        color, icon = STATUS_COLORS.get(worst, ("#6b7280", "⚪"))

        # coverage badge
        cov = gsc.get("coverage_state", "Unknown")
        cov_color = "#22c55e" if "Indexed" in cov else "#ef4444" if "not" in cov.lower() else "#6b7280"

        # actions list
        action_items = ""
        for a in actions:
            ac, ai = STATUS_COLORS.get(a["priority"], ("#6b7280","⚪"))
            action_items += f"""
            <div class="action-item" style="border-left:3px solid {ac}">
              <div class="action-cat">{ai} {_esc(a['category'])}</div>
              <div class="action-msg">{_esc(a['message'])}</div>
              <div class="action-fix">→ {_esc(a['fix'])}</div>
            </div>"""

        # top queries
        q_rows = ""
        for q in sa.get("top_queries", []):
            q_rows += f"""<tr>
              <td>{_esc(q['query'])}</td>
              <td>{q['impressions']:,}</td>
              <td>{q['clicks']}</td>
              <td>{q['position']}</td>
              <td style="color:{'#ef4444' if q['ctr']<2 and q['position']<=15 else '#22c55e'}">{q['ctr']}%</td>
            </tr>"""

        # GSC inspect link
        gsc_link = gsc.get("gsc_inspect_link","")
        gsc_btn  = f'<a href="{_esc(gsc_link)}" target="_blank" class="btn-gsc">Open in GSC ↗</a>' if gsc_link else ""

        slug = pf["url"].split("/products/")[-1][:50] if "/products/" in pf["url"] else pf["url"][-50:]

        rows_html += f"""
    <div class="product-card" id="card-{i}">
      <div class="card-header" style="border-left:4px solid {color}">
        <div class="card-left">
          <div class="card-icon">{icon}</div>
          <div>
            <div class="card-slug">{_esc(slug)}</div>
            <div class="card-url"><a href="{_esc(pf['url'])}" target="_blank">{_esc(pf['url'])}</a></div>
          </div>
        </div>
        <div class="card-metrics">
          <div class="metric"><span class="metric-val">{sa.get('impressions',0):,}</span><span class="metric-label">impr</span></div>
          <div class="metric"><span class="metric-val">{sa.get('clicks',0)}</span><span class="metric-label">clicks</span></div>
          <div class="metric"><span class="metric-val">{sa.get('position',0)}</span><span class="metric-label">pos</span></div>
          <div class="metric"><span class="metric-val">{sa.get('ctr',0)}%</span><span class="metric-label">CTR</span></div>
        </div>
      </div>
      <div class="card-body">
        <div class="status-row">
          <span class="badge" style="background:{cov_color}20;color:{cov_color};border:1px solid {cov_color}">{_esc(cov)}</span>
          <span class="badge" style="background:#1e293b;color:#94a3b8">Fetched as: {_esc(gsc.get('crawled_as','?'))}</span>
          {'<span class="badge" style="background:#7f1d1d20;color:#ef4444;border:1px solid #ef4444">NOINDEX</span>' if pf['noindex'] else ''}
          {'<span class="badge" style="background:#14532d20;color:#22c55e;border:1px solid #22c55e">In Sitemap</span>' if gsc.get('in_sitemap') else ''}
          <span class="badge" style="background:#1e293b;color:#94a3b8">Last crawled: {_esc(gsc.get('last_crawl_time','Never')[:10] if gsc.get('last_crawl_time') else 'Never')}</span>
          <span class="badge" style="background:#1e293b;color:#94a3b8">{pf['page_kb']}KB</span>
          {gsc_btn}
        </div>

        <div class="two-col">
          <div>
            <div class="section-title">Issues & Fixes ({len(actions)})</div>
            {action_items if action_items else '<div style="color:#22c55e;font-size:12px">✅ No issues found</div>'}
          </div>
          <div>
            {'<div class="section-title">Top Queries (last 90 days)</div><table class="q-table"><thead><tr><th>Query</th><th>Impr</th><th>Clicks</th><th>Pos</th><th>CTR</th></tr></thead><tbody>' + q_rows + '</tbody></table>' if q_rows else '<div style="color:#475569;font-size:12px">No search analytics data yet</div>'}
            <div class="schema-flags">
              {'<span class="sflag ok">GTIN ✓</span>' if pf['gtin'] else '<span class="sflag warn">GTIN ✗</span>'}
              {'<span class="sflag ok">Rating ✓</span>' if pf['has_aggregate_rating'] else '<span class="sflag warn">Rating ✗</span>'}
              {'<span class="sflag ok">Product JSON-LD ✓</span>' if pf['has_product_jsonld'] else '<span class="sflag err">Product JSON-LD ✗</span>'}
              {'<span class="sflag warn">FAQPage×' + str(pf['faq_count']) + '</span>' if pf['faq_count'] > 0 else ''}
              {'<span class="sflag err">Brand=Unknown</span>' if pf['brand_unknown'] else ''}
            </div>
          </div>
        </div>
      </div>
    </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rudra Retail GSC Audit — {now}</title>
<style>
:root{{--bg:#0d1117;--surface:#161b22;--surface2:#21262d;--border:#30363d;
  --text:#e6edf3;--muted:#7d8590;--orange:#fb923c;}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,sans-serif;font-size:13px;line-height:1.5}}
a{{color:var(--orange);text-decoration:none}} a:hover{{text-decoration:underline}}
.header{{background:var(--surface);border-bottom:1px solid var(--border);padding:20px 24px;position:sticky;top:0;z-index:100}}
.header h1{{font-size:18px;font-weight:700}} .header .sub{{color:var(--muted);font-size:12px;margin-top:2px}}
.summary{{display:flex;gap:16px;flex-wrap:wrap;padding:20px 24px}}
.sum-card{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:14px 18px;min-width:130px}}
.sum-val{{font-size:28px;font-weight:800;color:var(--orange);font-family:monospace}}
.sum-label{{font-size:11px;color:var(--muted);margin-top:2px}}
.cards{{padding:0 24px 40px;display:flex;flex-direction:column;gap:12px}}
.product-card{{background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden}}
.card-header{{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;background:var(--surface2);flex-wrap:wrap;gap:8px}}
.card-left{{display:flex;align-items:center;gap:10px}}
.card-icon{{font-size:20px;flex-shrink:0}}
.card-slug{{font-weight:700;font-size:13px}}
.card-url{{font-size:11px;color:var(--muted)}}
.card-metrics{{display:flex;gap:16px}}
.metric{{text-align:center}} .metric-val{{display:block;font-size:16px;font-weight:700;font-family:monospace}}
.metric-label{{font-size:10px;color:var(--muted)}}
.card-body{{padding:14px 16px}}
.status-row{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px;align-items:center}}
.badge{{font-size:10px;font-weight:600;padding:2px 8px;border-radius:4px}}
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
@media(max-width:700px){{.two-col{{grid-template-columns:1fr}}}}
.section-title{{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px}}
.action-item{{background:var(--surface2);border-radius:6px;padding:10px 12px;margin-bottom:6px}}
.action-cat{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#94a3b8;margin-bottom:3px}}
.action-msg{{font-size:12px;font-weight:600;color:var(--text);margin-bottom:4px}}
.action-fix{{font-size:11px;color:#64748b;line-height:1.5}}
.q-table{{width:100%;border-collapse:collapse;margin-top:2px}}
.q-table th,.q-table td{{padding:5px 8px;text-align:left;border-bottom:1px solid var(--border);font-size:11px}}
.q-table th{{color:var(--muted);font-weight:600}}
.schema-flags{{display:flex;gap:4px;flex-wrap:wrap;margin-top:10px}}
.sflag{{font-size:10px;font-weight:600;padding:2px 7px;border-radius:4px}}
.sflag.ok{{background:#14532d40;color:#4ade80}}
.sflag.warn{{background:#78350f40;color:#fb923c}}
.sflag.err{{background:#7f1d1d40;color:#f87171}}
.btn-gsc{{font-size:10px;font-weight:700;background:#1e3a5f;color:#60a5fa;border:1px solid #1d4ed8;
  padding:3px 10px;border-radius:4px;cursor:pointer}}
</style>
</head>
<body>
<div class="header">
  <h1>🔍 Rudra Retail GSC Audit — {_esc(SITE_URL)}</h1>
  <div class="sub">Generated {now} · {total} URLs audited</div>
</div>
<div class="summary">
  <div class="sum-card"><div class="sum-val">{total}</div><div class="sum-label">URLs audited</div></div>
  <div class="sum-card"><div class="sum-val" style="color:#ef4444">{has_p1}</div><div class="sum-label">🔴 P1 blockers</div></div>
  <div class="sum-card"><div class="sum-val" style="color:#22c55e">{indexed}</div><div class="sum-label">Indexed</div></div>
  <div class="sum-card"><div class="sum-val">{sum(r['sa'].get('impressions',0) for r in results):,}</div><div class="sum-label">Total impressions</div></div>
  <div class="sum-card"><div class="sum-val">{sum(r['sa'].get('clicks',0) for r in results)}</div><div class="sum-label">Total clicks (90d)</div></div>
</div>
<div class="cards">
{rows_html}
</div>
</body>
</html>"""

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    # Load URLs
    url_file = Path(INPUT_FILE)
    if not url_file.exists():
        url_file.parent.mkdir(parents=True, exist_ok=True)
        url_file.write_text(
            "https://YOUR_DOMAIN_HERE/products/sample-product-1\n"
            "https://YOUR_DOMAIN_HERE/products/sample-product-2\n"
            "https://YOUR_DOMAIN_HERE/products/sample-product-3\n"
        )
        print(f"Created sample {INPUT_FILE} — edit it with your product URLs then re-run.")
        return

    urls = [u.strip() for u in url_file.read_text().splitlines() if u.strip() and not u.startswith("#")]
    if not urls:
        print(f"No URLs found in {INPUT_FILE}")
        return

    print(f"\n{'='*60}")
    print(f"  Rudra Retail GSC Auditor — {len(urls)} URLs")
    print(f"{'='*60}\n")

    # Auth
    print("Authenticating with Google...")
    creds   = get_credentials()
    # URL Inspection uses searchconsole v1
    sc_v1   = build("searchconsole", "v1", credentials=creds)
    # Search Analytics uses webmasters v3
    wmt_v3  = build("webmasters", "v3", credentials=creds)
    print("Auth OK ✅\n")

    results = []
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url.split('/products/')[-1][:60]}")

        # Stage 1
        print("  Stage 1: Pre-flight...", end=" ", flush=True)
        pf = preflight(url)
        p1 = len([x for x in pf["preflight_issues"] if x])
        pw = len([x for x in pf["preflight_warnings"] if x])
        print(f"HTTP {pf['http_status']} | {pf['page_kb']}KB | {p1} issues, {pw} warnings")

        # Stage 2
        print("  Stage 2: GSC URL Inspection...", end=" ", flush=True)
        gsc = gsc_inspect(sc_v1, url)
        if gsc.get("gsc_error"):
            print(f"ERROR: {gsc['gsc_error']}")
        else:
            print(f"{gsc['gsc_verdict']} | {gsc['coverage_state']}")
        time.sleep(DELAY_BETWEEN_CALLS)

        # Stage 3
        print("  Stage 3: Search Analytics...", end=" ", flush=True)
        sa = gsc_analytics(wmt_v3, url)
        if sa.get("sa_error"):
            print(f"ERROR: {sa['sa_error']}")
        else:
            print(f"{sa['impressions']:,} impr | pos {sa['position']} | CTR {sa['ctr']}%")
        time.sleep(DELAY_BETWEEN_CALLS)

        # Stage 4
        actions = decide(pf, gsc, sa)
        score   = priority_score(pf, gsc, sa, actions)

        results.append({"pf": pf, "gsc": gsc, "sa": sa, "actions": actions, "score": score})
        print(f"  → {len(actions)} actions | Priority score: {score:,}\n")

    # Sort by score descending (highest urgency first)
    results.sort(key=lambda x: -x["score"])

    # Output report
    date_str    = datetime.date.today().isoformat()
    report_path = Path(OUTPUT_DIR) / date_str / "report.html"
    build_report(results, report_path)
    print(f"\n{'='*60}")
    print(f"  Report saved: {report_path}")
    print(f"  Opening in browser...")
    print(f"{'='*60}\n")
    webbrowser.open(report_path.resolve().as_uri())


if __name__ == "__main__":
    main()
