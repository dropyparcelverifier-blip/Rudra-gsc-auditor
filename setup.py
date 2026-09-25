#!/usr/bin/env python3
"""
Rudra Retail GSC Auditor — Interactive Setup
=============================================
Guides you through creating .env file with all required credentials.
"""

import os
import sys
from pathlib import Path
import json

def ask(prompt: str, default: str = "", secret: bool = False) -> str:
    """Ask user for input with optional default."""
    if default:
        display = f"{prompt} [{default}]: "
    else:
        display = f"{prompt}: "

    if secret:
        import getpass
        return getpass.getpass(display) or default
    else:
        return input(display) or default


def main():
    print("\n" + "="*70)
    print("  🚀 Rudra Retail GSC Auditor — Setup Wizard")
    print("="*70 + "\n")

    env_file = Path(".env")

    if env_file.exists():
        resp = ask("⚠️  .env already exists. Overwrite?", "n")
        if resp.lower() != "y":
            print("Setup cancelled.")
            return

    config = {}

    # ─ Google Cloud Console ─
    print("\n📍 STEP 1: Google Search Console")
    print("-" * 70)
    print("""
You'll need:
  1. Google Cloud project (use existing project)
  2. OAuth 2.0 credentials (Desktop App type)

Steps:
  a) Go: https://console.cloud.google.com → Select your project
  b) APIs & Services → Library → Search "Google Search Console API" → Enable
  c) APIs & Services → Credentials → Create Credentials → OAuth client ID
  d) Application type: Desktop app → Name: "rudra-retail-gsc-local"
  e) Create → Download JSON → Save in this folder as 'credentials.json'
  f) Property format from GSC: https://search.google.com/search-console
     - If "sc-domain:yourdomain.com" → use that (Domain property)
     - If "https://yourdomain.com/" → use that (URL prefix)
    """)

    creds_file = ask("Credentials file path", "credentials.json")
    config["GOOGLE_CREDENTIALS_FILE"] = creds_file

    if Path(creds_file).exists():
        print(f"✅ Found {creds_file}")
    else:
        print(f"⚠️  {creds_file} not found (will be created on first run)")

    site_url = ask("GSC property URL", "sc-domain:YOUR_DOMAIN_HERE")
    config["GOOGLE_SITE_URL"] = site_url

    audit_days = ask("Audit lookback (days)", "90")
    config["GSC_AUDIT_DAYS"] = audit_days

    # ─ Shopify ─
    print("\n📍 STEP 2: Shopify API Access")
    print("-" * 70)
    print("""
You'll need:
  1. Shopify store (yourstore.myshopify.com)
  2. Custom app with API access

Steps:
  a) Go: https://admin.shopify.com → Settings → Apps and integrations
  b) Develop apps → Create an app → Name: "Rudra Retail GSC Auditor"
  c) Configuration → Admin API scopes → Check these:
     ✓ write_products
     ✓ read_products
     ✓ write_inventory
     ✓ read_inventory
  d) Save → Install app
  e) Reveal token → Copy Access Token (starts with "shpat_")
    """)

    store = ask("Shopify store name (without .myshopify.com)", "")
    config["SHOPIFY_STORE"] = store

    token = ask("Shopify Access Token", secret=True)
    if not token:
        print("⚠️  Shopify token empty (sync will be disabled)")
    config["SHOPIFY_ACCESS_TOKEN"] = token

    api_version = ask("Shopify API version", "2024-10")
    config["SHOPIFY_API_VERSION"] = api_version

    # ─ Flask ─
    print("\n📍 STEP 3: Flask Web App")
    print("-" * 70)

    port = ask("Flask port", "5000")
    config["FLASK_PORT"] = port
    config["FLASK_HOST"] = "0.0.0.0"
    config["FLASK_ENV"] = "production"

    # ─ Optional: Slack ─
    print("\n📍 STEP 4: Slack Notifications (Optional)")
    print("-" * 70)
    slack_enable = ask("Enable Slack notifications?", "n")
    if slack_enable.lower() == "y":
        webhook = ask("Slack webhook URL")
        config["SLACK_WEBHOOK_URL"] = webhook
        config["SLACK_CHANNEL"] = ask("Slack channel", "#seo")
        config["SLACK_NOTIFY_ON_P1"] = "True"

    # ─ Thresholds ─
    print("\n📍 STEP 5: Auditor Thresholds")
    print("-" * 70)

    config["MIN_DESCRIPTION_WORDS"] = ask("Min product description words", "100")
    config["MAX_TITLE_CHARS"] = ask("Max title characters", "60")
    config["MIN_INTERNAL_LINKS"] = ask("Min internal links", "5")
    config["MAX_PAGE_SIZE_KB"] = ask("Max page size (KB)", "800")

    # ─ Brand ─
    print("\n📍 STEP 6: Brand Information")
    print("-" * 70)

    config["BRAND_NAME"] = ask("Brand name", "Rudra Retail")
    config["BRAND_DOMAIN"] = ask("Brand domain", "YOUR_DOMAIN_HERE")
    config["COUNTRY_CODE"] = ask("Country code", "IN")
    config["CURRENCY"] = ask("Currency", "INR")

    # ─ Rate limits ─
    print("\n📍 STEP 7: Rate Limiting")
    print("-" * 70)
    print("""
Shopify: 2 req/sec burst, 4 req/sec sustained → recommend 0.5s
Google:  600 QPS burst, 2000 QPD sustained → recommend 0.3s
    """)

    config["SHOPIFY_RATE_LIMIT_DELAY"] = ask("Shopify delay (seconds)", "0.5")
    config["GOOGLE_RATE_LIMIT_DELAY"] = ask("Google delay (seconds)", "0.3")

    # ─ Write .env ─
    print("\n" + "="*70)
    print("  📝 Writing .env file...")
    print("="*70 + "\n")

    # Add defaults for optional fields
    defaults = {
        "FLASK_DEBUG": "False",
        "SHOPIFY_DRY_RUN": "False",
        "AUTO_SYNC_TO_SHOPIFY": "False",
        "VERBOSE_LOGGING": "False",
        "REPORTS_DIR": "reports",
        "LOGS_DIR": "logs",
    }
    config.update({k: v for k, v in defaults.items() if k not in config})

    env_content = """# Rudra Retail GSC Auditor — Configuration
# Generated by setup.py
# DO NOT COMMIT THIS FILE (contains secrets)

# Google Search Console
GOOGLE_CREDENTIALS_FILE={GOOGLE_CREDENTIALS_FILE}
GOOGLE_SITE_URL={GOOGLE_SITE_URL}
GSC_AUDIT_DAYS={GSC_AUDIT_DAYS}
GOOGLE_RATE_LIMIT_DELAY={GOOGLE_RATE_LIMIT_DELAY}

# Shopify
SHOPIFY_STORE={SHOPIFY_STORE}
SHOPIFY_ACCESS_TOKEN={SHOPIFY_ACCESS_TOKEN}
SHOPIFY_API_VERSION={SHOPIFY_API_VERSION}
SHOPIFY_RATE_LIMIT_DELAY={SHOPIFY_RATE_LIMIT_DELAY}
SHOPIFY_DRY_RUN={SHOPIFY_DRY_RUN}
AUTO_SYNC_TO_SHOPIFY={AUTO_SYNC_TO_SHOPIFY}

# Flask
FLASK_ENV={FLASK_ENV}
FLASK_HOST={FLASK_HOST}
FLASK_PORT={FLASK_PORT}
FLASK_DEBUG={FLASK_DEBUG}

# Auditor Thresholds
MIN_DESCRIPTION_WORDS={MIN_DESCRIPTION_WORDS}
MAX_TITLE_CHARS={MAX_TITLE_CHARS}
MIN_INTERNAL_LINKS={MIN_INTERNAL_LINKS}
MAX_PAGE_SIZE_KB={MAX_PAGE_SIZE_KB}

# Brand
BRAND_NAME={BRAND_NAME}
BRAND_DOMAIN={BRAND_DOMAIN}
COUNTRY_CODE={COUNTRY_CODE}
CURRENCY={CURRENCY}

# Paths
REPORTS_DIR={REPORTS_DIR}
LOGS_DIR={LOGS_DIR}

# Features
VERBOSE_LOGGING={VERBOSE_LOGGING}
""".format(**config)

    # Add optional Slack
    if "SLACK_WEBHOOK_URL" in config:
        env_content += f"""
# Slack
SLACK_WEBHOOK_URL={config['SLACK_WEBHOOK_URL']}
SLACK_CHANNEL={config.get('SLACK_CHANNEL', '#seo')}
SLACK_NOTIFY_ON_P1={config.get('SLACK_NOTIFY_ON_P1', 'True')}
"""

    with open(env_file, "w") as f:
        f.write(env_content)

    print(f"✅ Created {env_file}")
    print("\n⚠️  IMPORTANT:")
    print("  • Add .env to .gitignore (it contains secrets)")
    print("  • Never commit this file to git")
    print("  • If token leaked, regenerate in Shopify Admin\n")

    # ─ Validate ─
    print("="*70)
    print("  ✅ Validating configuration...")
    print("="*70 + "\n")

    from config import validate_config, get_config_summary

    ok, msg = validate_config()
    if ok:
        print(f"✅ {msg}\n")
        summary = get_config_summary()
        print("Current Configuration:")
        print(json.dumps(summary, indent=2))

        print("\n" + "="*70)
        print("  ✅ Setup complete!")
        print("="*70)
        print("\nNext steps:")
        print("  1. pip install -r requirements.txt")
        print("  2. python app.py")
        print("  3. Open http://localhost:5000")
        print("\n")
    else:
        print(f"❌ {msg}\n")
        return 1

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
