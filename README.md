# GSC Auditor & Auto-Indexing Pipeline

Automated SEO pipeline for Shopify stores: check URLs, validate structured data, auto-fix SEO issues, submit to Google for indexing, and monitor daily.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure credentials
copy .env.example .env          # Windows
# cp .env.example .env          # Mac/Linux
# Edit .env with your credentials (see Setup below)

# 3. Validate your setup
python auto_pipeline.py setup

# 4. Get your product URLs (choose one)
python auto_pipeline.py scrape              # auto-fetch from sitemap
python auto_pipeline.py add urls.txt        # from a file you already have
python auto_pipeline.py add https://yoursite.com/products/my-product  # single URL

# 5. Run the full pipeline
python auto_pipeline.py run urls.txt

# 6. Monitor daily
python auto_pipeline.py monitor
```

## What It Does

| Step | Command | Description |
|------|---------|-------------|
| Setup | `setup` | Validates config, shows what's missing |
| Input | `scrape` | Auto-fetches all product URLs from your sitemap |
| Input | `add <file_or_url>` | Adds URLs to urls.txt (deduplicates) |
| 1 | `check urls.txt` | Checks URL liveness + JSON-LD + meta tags |
| 2 | `fix` | Auto-fixes titles, descriptions via Shopify API |
| 3 | `index` | Submits non-indexed URLs to Google Indexing API |
| 4 | `status` | Checks current indexing status of all URLs |
| 5 | `snippets` | Checks rich result appearance (product/review snippets) |
| All | `run urls.txt` | Runs steps 1-3 in sequence |
| Daily | `monitor` | Runs steps 4-5 + detects rejected URLs |
| View | `report` | Shows summary of last pipeline run |

## Setup (One Time)

### 1. Google Search Console API

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create or select a project
3. Enable **Search Console API** and **Indexing API**
4. Create a **Service Account** -> download JSON key -> save as `credentials.json`
5. In [Google Search Console](https://search.google.com/search-console), add the service account email as **Owner** of your property

### 2. Shopify (for auto-fix)

1. Shopify Admin -> Settings -> Apps -> Develop apps
2. Create app "GSC Auditor"
3. Configure scopes: `write_products`, `read_products`
4. Install the app -> copy the **Admin API Access Token**

### 3. Configure .env

```
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_SITE_URL=https://yoursite.com/
SHOPIFY_STORE=your-store-handle
SHOPIFY_ACCESS_TOKEN=shpat_xxxxx
BRAND_NAME=Your Brand
BRAND_DOMAIN=yoursite.com
```

Then run `python auto_pipeline.py setup` to verify everything works.

## Web UI

```bash
python app.py
# Open http://localhost:5000
# Interactive audit with 33 SEO checks
```

## File Structure

```
gsc-auditor/
├── auto_pipeline.py     <- main automation script (start here)
├── app.py               <- web UI (Flask)
├── audit.py             <- core audit engine
├── config.py            <- configuration loader
├── .env.example         <- template for credentials
├── .env                 <- your credentials (DO NOT COMMIT)
├── credentials.json     <- Google service account key (DO NOT COMMIT)
├── urls.txt             <- your product URLs
├── requirements.txt
├── pipeline_data/       <- auto-created: pipeline state (JSON)
└── logs/                <- auto-created: log files
```

## Daily Workflow

1. Add new products: `python auto_pipeline.py scrape` or `add`
2. Run pipeline: `python auto_pipeline.py run urls.txt`
3. Check daily: `python auto_pipeline.py monitor`
4. View results: `python auto_pipeline.py report`

## API Quotas

- URL Inspection: 2,000/day per property
- Indexing API: 200/day per property
- Shopify: 2 req/sec burst, 40 req/min sustained
