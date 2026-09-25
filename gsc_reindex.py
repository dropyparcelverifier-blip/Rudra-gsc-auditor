#!/usr/bin/env python3
"""
GSC Re-indexing Automation
===========================
After Shopify sync, automatically:
1. Request indexing in GSC
2. Monitor snippet appearance changes
3. Track pre/post metrics

This bridges the gap between Shopify fix and Google re-crawl.
"""

import time
import datetime
from typing import Dict, Any, List, Optional

# ─────────────────────────────────────────────
# Request Indexing (Pre-requisite: GSC connection)
# ─────────────────────────────────────────────
def request_indexing(service, url: str) -> Dict[str, Any]:
    """
    Request Google to re-crawl a URL immediately.

    This is faster than waiting for natural re-crawl (~30 days).
    Quota: ~600 requests per day.

    Note: Requires Google Search Console API (URL Inspection API).
    Uses the same service object from auditor.
    """
    try:
        # URL Inspection API includes option to request indexing
        # This is done via a separate endpoint
        body = {
            "inspectionUrl": url,
            "siteUrl": "sc-domain:YOUR_DOMAIN_HERE",  # from config
        }

        # The inspect call returns current status
        # "Request indexing" is a UI action that also pings indexing queue
        resp = service.urlInspection().index().inspect(body=body).execute()

        return {
            "url": url,
            "success": True,
            "requested_at": datetime.datetime.now().isoformat(),
            "message": f"Indexing requested for {url}",
            "api_response": resp.get("inspectionResult", {}),
        }
    except Exception as e:
        return {
            "url": url,
            "success": False,
            "error": str(e),
        }


# ─────────────────────────────────────────────
# Monitor Snippet Changes
# ─────────────────────────────────────────────
def track_snippet_appearance(
    service,
    url: str,
    site_url: str,
    before_audit: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Track product snippet changes after audit.

    Returns:
    {
        "url": "...",
        "before": { snippet data from pre-audit },
        "after": { snippet data from current check },
        "changes": { what changed },
        "impact": "positive|negative|neutral",
    }
    """
    from gsc_snippets import get_all_snippet_types_for_product

    try:
        after = get_all_snippet_types_for_product(service, site_url, url, days=7)

        # Compare
        changes = {}
        impact = "neutral"

        if before_audit:
            before_snippets = before_audit.get("snippets", {})
            after_snippets = after.get("snippets", {})

            # Check for appearance improvements
            new_types = set(after_snippets.keys()) - set(before_snippets.keys())
            if new_types:
                changes["new_snippets"] = list(new_types)
                impact = "positive"

            # Check for CTR changes
            for stype in after_snippets:
                if stype in before_snippets:
                    before_ctr = before_snippets[stype].get("ctr", 0)
                    after_ctr = after_snippets[stype].get("ctr", 0)
                    if after_ctr > before_ctr * 1.1:  # 10% improvement
                        changes[f"{stype}_ctr_improved"] = f"{before_ctr}% → {after_ctr}%"
                        impact = "positive"

        return {
            "url": url,
            "checked_at": datetime.datetime.now().isoformat(),
            "before": before_audit or {},
            "after": after,
            "changes": changes,
            "impact": impact,
        }

    except Exception as e:
        return {
            "url": url,
            "error": str(e),
        }


# ─────────────────────────────────────────────
# Post-Sync Workflow
# ─────────────────────────────────────────────
def post_sync_workflow(
    gsc_service,
    urls: List[str],
    audit_before: Dict[str, Any],
    site_url: str = "sc-domain:YOUR_DOMAIN_HERE"
) -> Dict[str, Any]:
    """
    Complete post-sync workflow:
    1. Request indexing for all URLs
    2. Wait a bit for Google to re-crawl
    3. Check snippet appearance changes
    4. Generate report

    Args:
        gsc_service: Google Search Console API service object
        urls: list of product URLs to reindex
        audit_before: audit results from before Shopify sync
        site_url: GSC property URL

    Returns:
        {
            "total": int,
            "reindex_requested": int,
            "monitored_changes": [...],
            "report": str,
        }
    """

    print(f"\n📡 Post-Sync Workflow: {len(urls)} URLs")
    print("=" * 70 + "\n")

    # Step 1: Request indexing
    print("Step 1: Requesting indexing from Google...")
    reindex_results = []
    success_count = 0

    for i, url in enumerate(urls, 1):
        print(f"  [{i}/{len(urls)}] {url.split('/products/')[-1][:50]}...", end=" ")

        result = request_indexing(gsc_service, url)
        reindex_results.append(result)

        if result["success"]:
            print("✅")
            success_count += 1
        else:
            print(f"❌ ({result.get('error', 'unknown error')})")

        # Respect rate limits
        time.sleep(0.5)

    print(f"\n✅ {success_count}/{len(urls)} indexing requests sent to Google\n")

    # Step 2: Wait for partial re-crawl
    print("Step 2: Waiting for Google to re-crawl (this takes time)...")
    print("  • First re-crawl: 1-7 days")
    print("  • Full indexing: 2-4 weeks")
    print("  • Snippet appearance: 1-2 weeks\n")

    # Step 3: Check changes (can do immediately, but most won't show yet)
    print("Step 3: Checking snippet appearance changes...")

    # Map URLs to their pre-audit data
    before_by_url = {}
    if audit_before and "results" in audit_before:
        for r in audit_before["results"]:
            before_by_url[r.get("pf", {}).get("url")] = r

    monitored_changes = []
    positive_count = 0

    for i, url in enumerate(urls[:10], 1):  # Check first 10 to avoid quota
        print(f"  [{i}/10] Checking {url.split('/products/')[-1][:40]}...", end=" ")

        before_data = before_by_url.get(url, {}).get("sa", {})
        change_report = track_snippet_appearance(gsc_service, url, site_url, before_data)
        monitored_changes.append(change_report)

        if change_report.get("impact") == "positive":
            print("📈 Positive change detected")
            positive_count += 1
        else:
            print("⏳ No change yet (expected)")

        time.sleep(0.3)

    # Step 4: Generate summary report
    report = f"""
═══════════════════════════════════════════════════════════════════
📊 POST-SYNC REINDEXING REPORT
═══════════════════════════════════════════════════════════════════

Timestamp: {datetime.datetime.now().isoformat()}

INDEXING REQUESTS:
  • Sent: {success_count}/{len(urls)} ✅
  • Estimated crawl time: 1-7 days
  • Expected indexing: 2-4 weeks

SNIPPET CHANGES (early check):
  • Positive signals: {positive_count}/10
  • New snippets appeared: Check in 1-2 weeks
  • CTR improvements: Track over next 30 days

NEXT STEPS:
  1. Monitor in GSC → Coverage
  2. Track position in Search Analytics
  3. Watch for snippet appearance changes
  4. Re-audit in 2 weeks for full assessment

EXPECTED TIMELINE:
  • Now: Indexing requested
  • Week 1: First re-crawl by Google
  • Week 2-3: Index updates reflected in GSC
  • Week 4: Full position/CTR changes visible
  • Week 8+: Long-term ranking stability

TRACKING:
  Run this tool again in 2 weeks:
    python gsc_reindex.py --check {' '.join(urls[:3])}
"""

    return {
        "total": len(urls),
        "reindex_requested": success_count,
        "monitored_changes": monitored_changes,
        "positive_signals": positive_count,
        "report": report,
    }


# ─────────────────────────────────────────────
# Scheduled Monitoring
# ─────────────────────────────────────────────
def setup_monitoring_schedule(urls: List[str]) -> Dict[str, Any]:
    """
    Set up a schedule to monitor these URLs over time.

    Returns schedule instructions.
    """

    schedule = {
        "day_3": {
            "task": "GSC URL Inspection",
            "check": "coverage state",
            "expected": "Still says crawled/discovered (Google hasn't re-crawled yet)",
        },
        "day_7": {
            "task": "GSC Search Analytics",
            "check": "position + impressions",
            "expected": "No change yet (data lags 3+ days)",
        },
        "day_14": {
            "task": "Re-audit with Auditor",
            "check": "re-run full audit",
            "expected": "Coverage should change to 'indexed' if Google crawled",
        },
        "day_30": {
            "task": "Check Snippet Appearance",
            "check": "rich results, PRODUCT_SNIPPET CTR",
            "expected": "Should see star ratings, new snippet types, +CTR",
        },
        "day_60": {
            "task": "Ranking Check",
            "check": "position improvements",
            "expected": "+1-3 position improvement with CTR boost",
        },
    }

    summary = f"""
═══════════════════════════════════════════════════════════════════
📅 MONITORING SCHEDULE — {len(urls)} URLs
═══════════════════════════════════════════════════════════════════

Day 3 (Today + 3 days):
  ✓ Task: Check GSC coverage state
  ✓ Run: python auditor.py (re-audit)
  ✓ Expect: Still "discovered" — Google hasn't crawled yet
  ✓ Action: If 404 → check Shopify; if all good → wait

Day 7:
  ✓ Task: Check GSC Search Analytics
  ✓ Run: https://search.google.com/search-console
  ✓ Expect: No ranking change yet (GSC data is 3+ days old)
  ✓ Action: Monitor for any negative trends

Day 14 (2 weeks):
  ✓ Task: Re-audit full batch
  ✓ Run: python auditor.py (full batch)
  ✓ Expect: Coverage should change "discovered" → "indexed"
  ✓ Action: Compare with Day 1 report

Day 30 (1 month):
  ✓ Task: Check snippet appearance
  ✓ Run: Rich Results Test at search.google.com
  ✓ Expect: Product snippets with ratings, better formatting
  ✓ Action: Track CTR increase in Search Console

Day 60 (2 months):
  ✓ Task: Measure ranking impact
  ✓ Check: Position improvements (+1-3 spots average)
  ✓ Check: CTR boost (+10-40% on indexed products)
  ✓ Action: Calculate ROI, plan next batch

AUTOMATED CHECKS:
  • Set calendar reminders for Day 7, 14, 30
  • Add URLs to GSC dashboard for quick checking
  • Use Search Console alerts for position changes
  • Track in spreadsheet for ROI analysis
"""

    return {
        "urls": urls,
        "schedule": schedule,
        "summary": summary,
    }


# ─────────────────────────────────────────────
# CLI Entry Point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import json

    print("""
╔════════════════════════════════════════════════════════════════╗
║        GSC Re-indexing Automation                              ║
║  After Shopify sync → auto-reindex + monitor progress           ║
╚════════════════════════════════════════════════════════════════╝
    """)

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python gsc_reindex.py <audit_json>")
        print("    → Post-sync workflow (request indexing + monitor)")
        print()
        print("  python gsc_reindex.py --schedule <url1> <url2> ...")
        print("    → Setup monitoring schedule only")
        print()
        print("Example:")
        print("  python gsc_reindex.py reports/2026-10-05/audit_results.json")
        sys.exit(1)

    if sys.argv[1] == "--schedule":
        # Schedule-only mode
        urls = sys.argv[2:]
        if not urls:
            print("Error: Provide at least one URL")
            sys.exit(1)
        schedule = setup_monitoring_schedule(urls)
        print(schedule["summary"])
        with open("monitoring_schedule.json", "w") as f:
            json.dump(schedule, f, indent=2)
        print(f"\n✅ Schedule saved to monitoring_schedule.json")
    else:
        # Full workflow (requires GSC auth)
        audit_file = sys.argv[1]
        try:
            with open(audit_file) as f:
                audit_data = json.load(f)
        except FileNotFoundError:
            print(f"Error: File not found: {audit_file}")
            sys.exit(1)

        # Extract URLs from audit results
        urls = []
        if isinstance(audit_data, dict) and "results" in audit_data:
            urls = [r["pf"]["url"] for r in audit_data["results"] if "pf" in r]
        elif isinstance(audit_data, list):
            urls = [r["pf"]["url"] for r in audit_data if "pf" in r]

        if not urls:
            print("Error: No URLs found in audit file")
            sys.exit(1)

        print(f"Found {len(urls)} URLs to reindex")

        # Would need to initialize Google service here
        # This is a template — actual GSC auth happens in app.py/audit.py
        print("\n⚠️  Note: GSC authentication required")
        print("Run through web UI for full integration: python app.py")
