"""Inspect a batch of unchecked skincare URLs. Run repeatedly until done."""
import json, time, os, re, sys, traceback

def inspect_url(svc, url, site_url, max_retries=3):
    """Inspect a URL with retries on 500 errors."""
    for attempt in range(max_retries):
        try:
            result = svc.urlInspection().index().inspect(
                body={'inspectionUrl': url, 'siteUrl': site_url}).execute()
            return result, None
        except Exception as e:
            err = str(e)
            if '429' in err or 'quota' in err.lower():
                return None, 'RATE_LIMITED'
            if '500' in err or '503' in err:
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
                    continue
            return None, err
    return None, 'MAX_RETRIES'

def main():
    from dotenv import load_dotenv
    load_dotenv()
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')
    SITE_URL = os.getenv('GOOGLE_SITE_URL', 'https://rudraretails.com/')
    BATCH = int(sys.argv[1]) if len(sys.argv) > 1 else 200

    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE, scopes=['https://www.googleapis.com/auth/webmasters.readonly'])
    svc = build('searchconsole', 'v1', credentials=creds)

    progress_file = 'pipeline_data/product_status_progress.json'
    progress = json.load(open(progress_file, encoding='utf-8'))

    urls = []
    with open('Skincare.txt', 'r', encoding='utf-8') as f:
        for line in f:
            found = re.findall(r'https?://[^\s,\"<>]+', line.strip())
            urls.extend(found)
    seen = set()
    handles = []
    for u in urls:
        u = u.rstrip('/')
        h = u.split('/products/')[-1] if '/products/' in u else None
        if h and h not in seen:
            seen.add(h)
            handles.append(h)

    unchecked = [h for h in handles if h not in progress]
    batch = unchecked[:BATCH]
    print(f'Skincare: {len(handles)-len(unchecked)}/{len(handles)} checked | Batch: {len(batch)}', flush=True)

    if not batch:
        print('Nothing to inspect - all done!', flush=True)
        return

    inspected = 0
    errors = 0
    consecutive_errors = 0
    print(f'Starting inspection loop...', flush=True)

    for i, handle in enumerate(batch, 1):
        url = f'https://rudraretails.com/products/{handle}'
        try:
            result, err = inspect_url(svc, url, SITE_URL)

            if err == 'RATE_LIMITED':
                print(f'  RATE LIMITED at {i} - saving and stopping', flush=True)
                break

            if err:
                errors += 1
                consecutive_errors += 1
                print(f'  [{i}] ERROR: {err[:100]}', flush=True)
                progress[handle] = {'coverage': 'ERROR: ' + str(err)[:80], 'last_crawl': '', 'rich_results': [], 'is_indexed': False, 'source': 'skincare'}
                if consecutive_errors >= 10:
                    print(f'  10 consecutive errors - stopping', flush=True)
                    break
                time.sleep(2)
                continue

            consecutive_errors = 0
            idx = result.get('inspectionResult', {}).get('indexStatusResult', {})
            coverage = idx.get('coverageState', 'unknown')
            last_crawl = idx.get('lastCrawlTime', '')
            rich = result.get('inspectionResult', {}).get('richResultsResult', {})
            rich_items = [item.get('richResultType', '') for item in rich.get('detectedItems', [])]
            progress[handle] = {
                'coverage': coverage,
                'last_crawl': last_crawl[:10] if last_crawl else '',
                'rich_results': rich_items,
                'is_indexed': 'indexed' in coverage.lower() and 'not' not in coverage.lower(),
                'source': 'skincare'
            }
            inspected += 1
            if i % 25 == 0:
                json.dump(progress, open(progress_file, 'w', encoding='utf-8'), indent=1)
                print(f'  [{i}/{len(batch)}] +{inspected} ({errors} err)', flush=True)
            time.sleep(0.3)

        except KeyboardInterrupt:
            print(f'\n  Interrupted at {i} - saving progress', flush=True)
            break

    json.dump(progress, open(progress_file, 'w', encoding='utf-8'), indent=1)
    checked_now = sum(1 for h in handles if h in progress)
    print(f'\nDone: +{inspected} inspected, {errors} errors | Total: {checked_now}/{len(handles)}', flush=True)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)
