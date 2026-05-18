#!/bin/bash
cd "$(dirname "$0")"

git pull

/usr/bin/python3 crawler_latest.py >> crawler_latest.log 2>&1

git add news_json/
git commit -m "Daily update: fetch latest news $(date +%Y-%m-%d)"
git push
