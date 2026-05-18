#!/usr/bin/env python3
"""
Fetch the latest 50 news articles from the Taiwan Presidential Office.
Always overwrites existing JSON files to keep them up to date.
Designed to run as a daily cron job.
"""

import json
import os
import sys
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crawler import (
    detect_max_id,
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

COUNT = 50


def crawl_latest(count=COUNT):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    max_id = detect_max_id()

    found = 0
    not_found = 0
    errors = 0
    news_id = max_id

    while found < count and news_id > 0:
        time.sleep(DELAY_BETWEEN_REQUESTS)
        try:
            article = fetch_article(news_id)
            if article:
                save_article(article)
                found += 1
                log.info(f"[{found}/{count}] ID {news_id}: {article['title'][:40]}")
            else:
                not_found += 1
        except Exception as e:
            errors += 1
            log.error(f"Error fetching ID {news_id}: {e}")

        news_id -= 1

    log.info(f"Done. Found: {found}, Not found: {not_found}, Errors: {errors}")
    return found


if __name__ == "__main__":
    crawl_latest()
