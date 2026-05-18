#!/usr/bin/env python3
"""
Fetch the latest 2 pages of news from the Taiwan Presidential Office.
Always overwrites existing JSON files to keep them up to date.
Designed to run as a daily cron job.
"""

import os
import sys
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crawler import (
    init_session,
    fetch_listing_page,
    fetch_article,
    save_article,
    DELAY_BETWEEN_REQUESTS,
    OUTPUT_DIR,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "crawler_latest.log"),
            encoding="utf-8",
        ),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

PAGES = 2


def crawl_latest(pages=PAGES):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    init_session()

    found = 0
    errors = 0

    for page_num in range(1, pages + 1):
        time.sleep(DELAY_BETWEEN_REQUESTS)
        ids = fetch_listing_page(page_num)
        if ids is None:
            log.error(f"Failed to fetch listing page {page_num}")
            errors += 1
            continue

        for news_id in ids:
            time.sleep(DELAY_BETWEEN_REQUESTS)
            article = fetch_article(news_id)
            if article:
                save_article(article)
                found += 1
                log.info(f"[{found}] ID {news_id}: {article['title'][:40]}")
            else:
                errors += 1
                log.warning(f"Could not fetch article {news_id}")

    log.info(f"Done. Fetched: {found}, Errors: {errors}")
    return found


if __name__ == "__main__":
    crawl_latest()
