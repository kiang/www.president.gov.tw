#!/usr/bin/env python3
"""
Analyze news articles by keyword. Shows date distribution of articles
containing the specified keyword in title, subtitle, or content.
"""

import json
import os
import sys
import argparse
from collections import Counter

NEWS_DIR = "news_json"


def load_articles():
    articles = []
    for year_dir in sorted(os.listdir(NEWS_DIR)):
        dirpath = os.path.join(NEWS_DIR, year_dir)
        if not os.path.isdir(dirpath):
            continue
        for filename in sorted(os.listdir(dirpath)):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(dirpath, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                articles.append(json.load(f))
    return articles


def search(articles, keyword):
    matches = []
    for a in articles:
        text = f"{a.get('title', '')} {a.get('subtitle', '')} {a.get('content', '')}"
        if keyword in text:
            matches.append(a)
    return matches


def main():
    parser = argparse.ArgumentParser(description="Analyze news keyword distribution")
    parser.add_argument("keyword", help="Keyword to search for")
    parser.add_argument("--by", choices=["date", "month", "year"], default="month",
                        help="Group by date, month, or year (default: month)")
    parser.add_argument("--list", action="store_true", help="List matching article titles")
    args = parser.parse_args()

    articles = load_articles()
    matches = search(articles, args.keyword)

    if not matches:
        print(f"No articles found containing '{args.keyword}'")
        return

    print(f"Found {len(matches)} articles containing '{args.keyword}' (out of {len(articles)} total)\n")

    if args.by == "date":
        key_fn = lambda a: a.get("date", "unknown")
    elif args.by == "month":
        key_fn = lambda a: a.get("date", "unknown")[:7]
    else:
        key_fn = lambda a: a.get("date", "unknown")[:4]

    dist = Counter(key_fn(a) for a in matches)

    max_count = max(dist.values())
    bar_width = 40

    for period in sorted(dist.keys()):
        count = dist[period]
        bar_len = int(count / max_count * bar_width)
        bar = "█" * bar_len
        print(f"{period}  {bar} {count}")

    if args.list:
        print(f"\n--- Matching articles ---")
        for a in sorted(matches, key=lambda x: x.get("date", "")):
            print(f"  {a.get('date', '?')}  [{a['id']}] {a.get('title', '')}")


if __name__ == "__main__":
    main()
