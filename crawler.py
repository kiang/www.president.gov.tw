#!/usr/bin/env python3
"""
Crawler for Taiwan Presidential Office news (https://www.president.gov.tw/Page/35)
Iterates through NEWS IDs and extracts each article as JSON.
"""

import json
import os
import re
import sys
import time
import logging
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://www.president.gov.tw"
OUTPUT_DIR = "news_json"
PROGRESS_FILE = "crawl_progress.json"
MAX_ID = 41000
WORKERS = 5
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
    "User-Agent": "Mozilla/5.0 (compatible; PresidentialNewsCrawler/1.0)",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
})


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
    return {"completed_ids": [], "failed_ids": [], "last_id": 0}


def save_progress(progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f)


def save_article(article):
    year_dir = os.path.join(OUTPUT_DIR, article["date"][:4] if article["date"] else "unknown")
    os.makedirs(year_dir, exist_ok=True)
    filepath = os.path.join(year_dir, f"{article['id']}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(article, f, ensure_ascii=False, indent=2)


def crawl_range(start_id, end_id):
    """Crawl a range of news IDs."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    progress = load_progress()
    completed = set(progress["completed_ids"])
    failed = set(progress["failed_ids"])

    ids_to_crawl = [i for i in range(start_id, end_id + 1) if i not in completed]
    total = len(ids_to_crawl)
    log.info(f"Crawling {total} IDs from {start_id} to {end_id} ({len(completed)} already done)")

    found = 0
    not_found = 0
    errors = 0
    batch_size = 50

    for batch_start in range(0, total, batch_size):
        batch = ids_to_crawl[batch_start:batch_start + batch_size]

        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            futures = {}
            for news_id in batch:
                time.sleep(DELAY_BETWEEN_REQUESTS / WORKERS)
                futures[executor.submit(fetch_article, news_id)] = news_id

            for future in as_completed(futures):
                news_id = futures[future]
                try:
                    article = future.result()
                    if article:
                        save_article(article)
                        found += 1
                        completed.add(news_id)
                    else:
                        not_found += 1
                        completed.add(news_id)
                except Exception as e:
                    errors += 1
                    failed.add(news_id)
                    log.error(f"Error processing ID {news_id}: {e}")

        progress["completed_ids"] = sorted(completed)
        progress["failed_ids"] = sorted(failed)
        progress["last_id"] = max(batch)
        save_progress(progress)

        processed = batch_start + len(batch)
        log.info(f"Progress: {processed}/{total} | Found: {found} | Not found: {not_found} | Errors: {errors}")

    log.info(f"Done. Found: {found}, Not found: {not_found}, Errors: {errors}")
    return found


def main():
    import argparse
    global WORKERS, DELAY_BETWEEN_REQUESTS
    parser = argparse.ArgumentParser(description="Crawl Presidential Office news articles")
    parser.add_argument("--start", type=int, default=1, help="Starting NEWS ID (default: 1)")
    parser.add_argument("--end", type=int, default=MAX_ID, help=f"Ending NEWS ID (default: {MAX_ID})")
    parser.add_argument("--workers", type=int, default=WORKERS, help=f"Number of concurrent workers (default: {WORKERS})")
    parser.add_argument("--delay", type=float, default=DELAY_BETWEEN_REQUESTS, help="Delay between requests in seconds")
    parser.add_argument("--single", type=int, help="Fetch a single article by ID (for testing)")
    args = parser.parse_args()

    WORKERS = args.workers
    DELAY_BETWEEN_REQUESTS = args.delay

    if args.single:
        article = fetch_article(args.single)
        if article:
            print(json.dumps(article, ensure_ascii=False, indent=2))
        else:
            print(f"Article {args.single} not found")
        return

    crawl_range(args.start, args.end)


if __name__ == "__main__":
    main()
