#!/usr/bin/env python3
"""
Crawler for Taiwan Presidential Office news (https://www.president.gov.tw/Page/35)
Uses the site's internal API to paginate the listing, then fetches each article.
"""

import json
import os
import re
import time
import logging
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.president.gov.tw"
API_URL = f"{BASE_URL}/WebAPI/News/List"
OUTPUT_DIR = "news_json"
PROGRESS_FILE = "crawl_progress.json"
REQUEST_TIMEOUT = 30
RETRY_COUNT = 3
DELAY_BETWEEN_REQUESTS = 0.5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("crawler.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
})


def init_session():
    """Visit the listing page once to establish cookies."""
    session.get(f"{BASE_URL}/Page/35", timeout=REQUEST_TIMEOUT)


def fetch_listing_page(page_num):
    """Fetch one page of the news listing via the internal API.
    Returns a list of news IDs found on that page, or None on failure."""
    for attempt in range(RETRY_COUNT):
        try:
            r = session.post(API_URL,
                headers={"CUSTOMER-CSRF-HEADER": ""},
                data={
                    "lang": "zh",
                    "country": "TW",
                    "detailno": str(page_num),
                    "tag": "Page",
                    "no": "35",
                },
                timeout=REQUEST_TIMEOUT,
            )
            r.encoding = "utf-8"
            if r.status_code != 200:
                if attempt < RETRY_COUNT - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None

            soup = BeautifulSoup(r.text, "lxml")
            ids = []
            for a in soup.find_all("a", href=True):
                m = re.match(r"/NEWS/(\d+)", a["href"])
                if m:
                    ids.append(int(m.group(1)))
            return sorted(set(ids), reverse=True)

        except requests.RequestException as e:
            if attempt < RETRY_COUNT - 1:
                time.sleep(2 ** attempt)
                continue
            log.warning(f"Failed to fetch listing page {page_num}: {e}")
            return None

    return None


def detect_total_pages():
    """Detect total number of listing pages from the API response."""
    ids = fetch_listing_page(1)
    if ids is None:
        return None
    r = session.post(API_URL,
        headers={"CUSTOMER-CSRF-HEADER": ""},
        data={"lang": "zh", "country": "TW", "detailno": "1", "tag": "Page", "no": "35"},
        timeout=REQUEST_TIMEOUT,
    )
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "lxml")
    max_page = 0
    for a in soup.find_all("a", attrs={"data-page": True}):
        try:
            max_page = max(max_page, int(a["data-page"]))
        except ValueError:
            pass
    return max_page if max_page > 0 else None


def roc_to_iso_date(roc_date_str):
    """Convert ROC date like '115年05月16日' to ISO format '2026-05-16'."""
    m = re.match(r"(\d+)年(\d+)月(\d+)日", roc_date_str)
    if not m:
        return roc_date_str
    year = int(m.group(1)) + 1911
    month = int(m.group(2))
    day = int(m.group(3))
    return f"{year:04d}-{month:02d}-{day:02d}"


def fetch_article(news_id):
    """Fetch and parse a single news article. Returns dict or None if not found."""
    url = f"{BASE_URL}/NEWS/{news_id}"

    for attempt in range(RETRY_COUNT):
        try:
            r = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            r.encoding = "utf-8"
            if r.url.rstrip("/") == BASE_URL or r.url.rstrip("/") == f"{BASE_URL}/":
                return None

            if r.status_code != 200:
                return None

            soup = BeautifulSoup(r.text, "lxml")
            page_wrap = soup.find("div", class_="pageWrap1")
            if not page_wrap:
                return None

            date_el = page_wrap.find("div", class_="pageDate1")
            title1_el = page_wrap.find("div", class_="pageTitle1")
            title2_el = page_wrap.find("div", class_="pageTitle2")
            article_el = page_wrap.find("div", class_="article1")

            if not title1_el and not title2_el:
                return None

            roc_date = date_el.get_text(strip=True) if date_el else ""
            iso_date = roc_to_iso_date(roc_date) if roc_date else ""
            title = title1_el.get_text(strip=True) if title1_el else ""
            subtitle = title2_el.get_text(strip=True) if title2_el else ""

            body_paragraphs = []
            if article_el:
                for p in article_el.find_all("p"):
                    text = p.get_text(strip=True)
                    if text:
                        body_paragraphs.append(text)

            images = []
            pic_section = page_wrap.find("div", class_=re.compile(r"list8"))
            if pic_section:
                for img in pic_section.find_all("img"):
                    src = img.get("src", "")
                    if src:
                        if src.startswith("/"):
                            src = BASE_URL + src
                        images.append(src)

            english_url = ""
            btn_bar = page_wrap.find("div", class_="btnBar")
            if btn_bar:
                en_link = btn_bar.find("a", href=True)
                if en_link:
                    english_url = en_link["href"]

            return {
                "id": news_id,
                "url": url,
                "date_roc": roc_date,
                "date": iso_date,
                "title": title,
                "subtitle": subtitle,
                "content": "\n\n".join(body_paragraphs),
                "content_paragraphs": body_paragraphs,
                "images": images,
                "english_url": english_url,
            }

        except requests.RequestException as e:
            if attempt < RETRY_COUNT - 1:
                time.sleep(2 ** attempt)
                continue
            log.warning(f"Failed to fetch ID {news_id} after {RETRY_COUNT} attempts: {e}")
            return None

    return None


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {"completed_pages": [], "last_page": 0}


def save_progress(progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f)


def save_article(article):
    year_dir = os.path.join(OUTPUT_DIR, article["date"][:4] if article["date"] else "unknown")
    os.makedirs(year_dir, exist_ok=True)
    filepath = os.path.join(year_dir, f"{article['id']}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(article, f, ensure_ascii=False, indent=2)


def scan_existing_ids():
    """Scan output directory for already-downloaded article IDs."""
    existing = set()
    if not os.path.exists(OUTPUT_DIR):
        return existing
    for year_dir in os.listdir(OUTPUT_DIR):
        dirpath = os.path.join(OUTPUT_DIR, year_dir)
        if not os.path.isdir(dirpath):
            continue
        for filename in os.listdir(dirpath):
            if filename.endswith(".json"):
                try:
                    existing.add(int(filename[:-5]))
                except ValueError:
                    pass
    return existing


def crawl_all(start_page, end_page, skip_existing=True):
    """Crawl news by paginating the listing API, then fetching each article."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    existing_ids = scan_existing_ids() if skip_existing else set()
    if existing_ids:
        log.info(f"Found {len(existing_ids)} existing articles on disk")

    progress = load_progress()
    completed_pages = set(progress["completed_pages"])

    total_found = 0
    total_skipped = 0
    total_errors = 0

    for page_num in range(start_page, end_page + 1):
        if page_num in completed_pages:
            continue

        time.sleep(DELAY_BETWEEN_REQUESTS)
        ids = fetch_listing_page(page_num)
        if ids is None:
            log.error(f"Failed to fetch listing page {page_num}, skipping")
            total_errors += 1
            continue

        page_found = 0
        page_skipped = 0
        for news_id in ids:
            if skip_existing and news_id in existing_ids:
                page_skipped += 1
                continue

            time.sleep(DELAY_BETWEEN_REQUESTS)
            article = fetch_article(news_id)
            if article:
                save_article(article)
                existing_ids.add(news_id)
                page_found += 1
            else:
                total_errors += 1
                log.warning(f"Could not fetch article {news_id} from page {page_num}")

        total_found += page_found
        total_skipped += page_skipped

        completed_pages.add(page_num)
        progress["completed_pages"] = sorted(completed_pages)
        progress["last_page"] = page_num
        save_progress(progress)

        log.info(
            f"Page {page_num}/{end_page} | "
            f"IDs: {len(ids)} | Fetched: {page_found} | Skipped: {page_skipped} | "
            f"Total: {total_found} fetched, {total_skipped} skipped, {total_errors} errors"
        )

    log.info(f"Done. Fetched: {total_found}, Skipped: {total_skipped}, Errors: {total_errors}")
    return total_found


def main():
    import argparse
    global DELAY_BETWEEN_REQUESTS
    parser = argparse.ArgumentParser(description="Crawl Presidential Office news articles")
    parser.add_argument("--start-page", type=int, default=1, help="Starting listing page (default: 1, newest)")
    parser.add_argument("--end-page", type=int, default=None, help="Ending listing page (default: auto-detect last page)")
    parser.add_argument("--delay", type=float, default=DELAY_BETWEEN_REQUESTS, help="Delay between requests in seconds")
    parser.add_argument("--no-skip", action="store_true", help="Re-fetch articles even if already on disk")
    parser.add_argument("--single", type=int, help="Fetch a single article by ID (for testing)")
    args = parser.parse_args()

    DELAY_BETWEEN_REQUESTS = args.delay

    if args.single:
        init_session()
        article = fetch_article(args.single)
        if article:
            print(json.dumps(article, ensure_ascii=False, indent=2))
        else:
            print(f"Article {args.single} not found")
        return

    init_session()

    end_page = args.end_page
    if end_page is None:
        end_page = detect_total_pages()
        if end_page:
            log.info(f"Detected {end_page} total listing pages")
        else:
            log.error("Could not detect total pages")
            return

    crawl_all(args.start_page, end_page, skip_existing=not args.no_skip)


if __name__ == "__main__":
    main()
