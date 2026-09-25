#!/usr/bin/env python3
"""
Configuration loader for Rudra Retail GSC Auditor
Reads from .env file with sensible defaults
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any

# Try to load python-dotenv if available
try:
    from dotenv import load_dotenv
    dotenv_path = Path(__file__).parent / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path)
except ImportError:
    print("⚠️  python-dotenv not installed. Using environment variables only.")
    print("   pip install python-dotenv")


# ─────────────────────────────────────────────
# Google Search Console Config
# ─────────────────────────────────────────────
class GoogleConfig:
    CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    SITE_URL = os.getenv("GOOGLE_SITE_URL", "https://rudraretails.com/")
    AUDIT_DAYS = int(os.getenv("GSC_AUDIT_DAYS", "90"))
    RATE_LIMIT_DELAY = float(os.getenv("GOOGLE_RATE_LIMIT_DELAY", "0.3"))
    SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


# ─────────────────────────────────────────────
# Shopify Config
# ─────────────────────────────────────────────
class ShopifyConfig:
    STORE = os.getenv("SHOPIFY_STORE", "")
    ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN", "")
    API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2024-10")
    RATE_LIMIT_DELAY = float(os.getenv("SHOPIFY_RATE_LIMIT_DELAY", "0.5"))
    DRY_RUN = os.getenv("SHOPIFY_DRY_RUN", "False").lower() == "true"
    AUTO_SYNC = os.getenv("AUTO_SYNC_TO_SHOPIFY", "False").lower() == "true"

    @staticmethod
    def validate():
        if not ShopifyConfig.ACCESS_TOKEN:
            return False, "SHOPIFY_ACCESS_TOKEN not set in .env"
        if not ShopifyConfig.STORE:
            return False, "SHOPIFY_STORE not set in .env"
        return True, "OK"


# ─────────────────────────────────────────────
# Flask App Config
# ─────────────────────────────────────────────
class FlaskConfig:
    ENV = os.getenv("FLASK_ENV", "production")
    HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    PORT = int(os.getenv("FLASK_PORT", "5000"))
    DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"


# ─────────────────────────────────────────────
# Auditor Thresholds
# ─────────────────────────────────────────────
class AuditorThresholds:
    MIN_DESCRIPTION_WORDS = int(os.getenv("MIN_DESCRIPTION_WORDS", "100"))
    MAX_TITLE_CHARS = int(os.getenv("MAX_TITLE_CHARS", "60"))
    MIN_INTERNAL_LINKS = int(os.getenv("MIN_INTERNAL_LINKS", "5"))
    MAX_PAGE_SIZE_KB = int(os.getenv("MAX_PAGE_SIZE_KB", "800"))
    MIN_CTR_FOR_POSITION = float(os.getenv("MIN_CTR_FOR_POSITION", "2"))
    MIN_POSITION_FOR_CTR_CHECK = int(os.getenv("MIN_POSITION_FOR_CTR_CHECK", "5"))
    MAX_POSITION_FOR_CTR_CHECK = int(os.getenv("MAX_POSITION_FOR_CTR_CHECK", "15"))


# ─────────────────────────────────────────────
# Optional: Slack Integration
# ─────────────────────────────────────────────
class SlackConfig:
    WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
    CHANNEL = os.getenv("SLACK_CHANNEL", "#seo")
    NOTIFY_ON_P1 = os.getenv("SLACK_NOTIFY_ON_P1", "True").lower() == "true"

    @staticmethod
    def enabled():
        return bool(SlackConfig.WEBHOOK_URL)


# ─────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────
class Paths:
    BASE_DIR = Path(__file__).parent
    REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "reports"))
    LOGS_DIR = Path(os.getenv("LOGS_DIR", "logs"))
    INPUT_DIR = Path("input")

    @staticmethod
    def ensure_directories():
        """Create necessary directories if they don't exist."""
        for d in [Paths.REPORTS_DIR, Paths.LOGS_DIR, Paths.INPUT_DIR]:
            d.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────
# Brand Info
# ─────────────────────────────────────────────
class BrandConfig:
    NAME = os.getenv("BRAND_NAME", "Rudra Retail")
    DOMAIN = os.getenv("BRAND_DOMAIN", "rudraretails.com")
    COUNTRY_CODE = os.getenv("COUNTRY_CODE", "IN")
    CURRENCY = os.getenv("CURRENCY", "INR")


# ─────────────────────────────────────────────
# Feature Flags
# ─────────────────────────────────────────────
class Features:
    VERBOSE_LOGGING = os.getenv("VERBOSE_LOGGING", "False").lower() == "true"


# ─────────────────────────────────────────────
# Validation & Startup
# ─────────────────────────────────────────────
def validate_config() -> tuple[bool, str]:
    """
    Validate all required configuration.
    Returns: (is_valid, message)
    """
    errors = []
    warnings = []

    # Google
    if not Path(GoogleConfig.CREDENTIALS_FILE).exists():
        warnings.append(f"⚠️  {GoogleConfig.CREDENTIALS_FILE} not found (GSC features will be limited)")

    # Shopify
    shopify_ok, shopify_msg = ShopifyConfig.validate()
    if not shopify_ok:
        warnings.append(f"⚠️  {shopify_msg} (Shopify sync disabled)")

    # Paths
    try:
        Paths.ensure_directories()
    except Exception as e:
        errors.append(f"❌ Failed to create directories: {e}")

    # Slack (optional)
    if SlackConfig.enabled():
        print("✅ Slack notifications enabled")

    if errors:
        return False, "\n".join(errors)

    if warnings:
        print("\n".join(warnings))

    return True, "Config OK"


def get_config_summary() -> Dict[str, Any]:
    """Return a summary of current configuration."""
    return {
        "google": {
            "site_url": GoogleConfig.SITE_URL,
            "credentials": Path(GoogleConfig.CREDENTIALS_FILE).exists(),
            "audit_days": GoogleConfig.AUDIT_DAYS,
        },
        "shopify": {
            "store": ShopifyConfig.STORE,
            "authenticated": bool(ShopifyConfig.ACCESS_TOKEN),
            "dry_run": ShopifyConfig.DRY_RUN,
            "auto_sync": ShopifyConfig.AUTO_SYNC,
        },
        "flask": {
            "host": FlaskConfig.HOST,
            "port": FlaskConfig.PORT,
            "debug": FlaskConfig.DEBUG,
        },
        "paths": {
            "reports": str(Paths.REPORTS_DIR),
            "logs": str(Paths.LOGS_DIR),
        },
        "brand": {
            "name": BrandConfig.NAME,
            "domain": BrandConfig.DOMAIN,
            "currency": BrandConfig.CURRENCY,
        },
    }


# ─────────────────────────────────────────────
# CLI: Print current config
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import json

    ok, msg = validate_config()
    print(f"\n{'='*60}")
    print(f"Config Status: {msg}")
    print(f"{'='*60}\n")

    if ok:
        summary = get_config_summary()
        print(json.dumps(summary, indent=2))
        print(f"\n✅ All systems go! Run: python app.py")
    else:
        print(f"❌ Configuration errors:\n{msg}")
        exit(1)
