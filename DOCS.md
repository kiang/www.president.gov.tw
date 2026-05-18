# Taiwan Presidential Office News Crawler

A complete guide to crawling, updating, and analyzing news articles from the Republic of China (Taiwan) Presidential Office website.

---

## Table of Contents

1. [Background](#1-background)
2. [Website Analysis](#2-website-analysis)
3. [Architecture](#3-architecture)
4. [Installation](#4-installation)
5. [Usage](#5-usage)
   - [Full crawl](#full-crawl-all-articles)
   - [Latest news](#latest-news-daily-update)
   - [Keyword analysis](#keyword-analysis)
   - [Automated daily updates](#automated-daily-updates-via-cron)
6. [Output Format](#6-output-format)
7. [How It Works](#7-how-it-works)
8. [Configuration](#8-configuration)
9. [Resume & Progress Tracking](#9-resume--progress-tracking)
10. [Logging](#10-logging)
11. [Troubleshooting](#11-troubleshooting)
12. [Known Limitations](#12-known-limitations)

---

## 1. Background

The Taiwan Presidential Office publishes official news at:

```
https://www.president.gov.tw/Page/35
```

As of May 2026, the archive contains **1,944 pages** of news articles, spanning from **2003 (ROC year 92)** to the present. Individual articles are accessible at URLs like:

```
https://www.president.gov.tw/NEWS/{id}
```

where `{id}` is a sequential integer. The earliest known valid ID is **1**, and the latest as of May 2026 is approximately **40055**.

---

## 2. Website Analysis

### Why not crawl the listing pages?

The listing page at `/Page/35` uses **client-side JavaScript pagination**. The pagination links are rendered as:

```html
<a href="javascript:;" title="第2頁">2</a>
```

There are no server-side query parameters (like `?page=2`), no ASP.NET ViewState fields, and no discoverable AJAX API endpoints. The pagination is entirely driven by JavaScript that cannot be replayed with simple HTTP requests.

### The alternative: direct article ID iteration

Each news article has a unique sequential integer ID. The crawler iterates through all possible IDs and fetches each article directly via its URL.

| Property | Value |
|---|---|
| Article URL pattern | `https://www.president.gov.tw/NEWS/{id}` |
| Valid ID range | 1 to ~40055 (grows over time) |
| Date range | 2003-07 (ROC 92) to present |
| Expected valid articles | ~29,000 (1,944 pages x ~15 per page) |
| Invalid IDs | Return HTTP 302 redirect to the homepage |
| Valid IDs | Return HTTP 308 (HTTPS redirect) then HTTP 200 |

### Encoding issue

The server returns `Content-Type: text/html` **without a charset declaration**. The Python `requests` library defaults to `ISO-8859-1` in this case, which double-encodes the UTF-8 Chinese characters into mojibake. The crawler explicitly sets `r.encoding = "utf-8"` after each request to fix this.

### HTML structure of an article page

```
div.pageWrap1
├── div.pageDate1          → "115年05月16日" (ROC calendar date)
├── div.pageTitle1         → Main headline
├── div.embedBox1          → (embedded media, if any)
├── div.pageTitle2         → Subtitle / event name
├── div.article1           → Article body
│   └── p                  → One paragraph per <p> tag
├── div.list8.picZoomJs    → Photo gallery
│   └── img                → Individual photos (src="/img/Image/{uuid}.jpg")
├── div.btnBar             → Links
│   └── a                  → English version link (if available)
└── div.list2.conSlick1Js  → Related news carousel
```

---

## 3. Architecture

```
Project files:
├── crawler.py             Full historical crawl (all articles)
├── crawler_latest.py      Fetch latest 50 articles (for daily updates)
├── analyze.py             Keyword search and date distribution analysis
├── cron.sh                Shell wrapper for daily cron job
├── DOCS.md                This documentation
├── .gitignore             Excludes logs, cache, progress files
│
Output files (generated):
├── news_json/
│   ├── 2003/
│   │   ├── 3.json
│   │   └── ...
│   ├── 2004/
│   ├── ...
│   └── 2026/
│       ├── 40050.json
│       └── 40055.json
├── crawl_progress.json    Resume state (crawler.py only)
├── crawler.log            Log for crawler.py
└── crawler_latest.log     Log for crawler_latest.py
```

### Module dependency

```
crawler.py                 Standalone — all core functions
    ↑
crawler_latest.py          Imports: detect_max_id, fetch_article, save_article
    ↑
cron.sh                    Calls crawler_latest.py

analyze.py                 Standalone — reads news_json/ directory
```

---

## 4. Installation

### Prerequisites

- Python 3.8+
- pip packages: `requests`, `beautifulsoup4`, `lxml`
- git (for cron.sh automated commits)

### Install dependencies

```bash
pip install requests beautifulsoup4 lxml
```

---

## 5. Usage

### Full crawl (all articles)

```bash
python3 crawler.py
```

The upper bound is **auto-detected** from the listing page at `/Page/35`. The crawler processes IDs in **descending order** (newest first) and skips articles that already exist on disk.

Estimated runtime: **several hours** at default settings (0.5s delay per request).

#### Crawl a specific range

```bash
python3 crawler.py --start 30000 --end 35000
```

#### Fetch a single article (for testing)

```bash
python3 crawler.py --single 40055
```

Prints the JSON to stdout without saving to disk.

#### Adjust politeness

```bash
python3 crawler.py --delay 1.0
```

#### CLI reference

| Argument | Default | Description |
|---|---|---|
| `--start` | `1` | First NEWS ID to crawl |
| `--end` | (auto-detect) | Last NEWS ID to crawl; scraped from the listing page if not provided |
| `--delay` | `0.5` | Seconds between requests |
| `--single` | (none) | Fetch and print one article by ID |

---

### Latest news (daily update)

```bash
python3 crawler_latest.py
```

Fetches the **50 most recent** articles by counting down from the auto-detected latest ID. **Always overwrites** existing JSON files to capture any edits or corrections to recent articles.

This script is designed to be run daily via `cron.sh`.

---

### Keyword analysis

```bash
python3 analyze.py "關鍵字"
```

Searches all downloaded articles (title, subtitle, and content) for the given keyword and displays a histogram of matches over time.

#### Group by month (default)

```bash
$ python3 analyze.py "台灣"
Found 165 articles containing '台灣' (out of 591 total)

2003  ███ 8
2025  ███████████████████████████████████ 74
2026  ████████████████████████████████████████ 83
```

#### Group by year or exact date

```bash
python3 analyze.py "健康" --by year
python3 analyze.py "健康" --by date
```

#### List matching article titles

```bash
$ python3 analyze.py "川普" --list
Found 31 articles containing '川普' (out of 601 total)

2025-10  ████████████████████████ 3
2025-11  ████████████████████████████████████████ 5
...

--- Matching articles ---
  2025-10-07  [39512] 總統接受美國廣播節目...專訪內容
  2025-10-17  [39540] 副總統接受「加拿大廣播公司」（CBC）專訪
  ...
```

#### CLI reference

| Argument | Default | Description |
|---|---|---|
| `keyword` | (required) | Keyword to search for |
| `--by` | `month` | Group results by `date`, `month`, or `year` |
| `--list` | off | Also print each matching article's date, ID, and title |

---

### Automated daily updates via cron

`cron.sh` wraps the daily update with git operations:

1. `git pull` — sync latest changes from remote
2. `python3 crawler_latest.py` — fetch the 50 most recent articles
3. `git add news_json/` — stage new/updated JSON files
4. `git commit` — commit with a dated message
5. `git push` — push to remote

#### Set up the cron job

```bash
# Edit crontab
crontab -e

# Add this line to run daily at 6:00 AM
0 6 * * * /home/kiang/public_html/president/cron.sh
```

---

## 6. Output Format

Each article is saved as a JSON file at `news_json/{year}/{id}.json`.

### Schema

```json
{
  "id": 40055,
  "url": "https://www.president.gov.tw/NEWS/40055",
  "date_roc": "115年05月16日",
  "date": "2026-05-16",
  "title": "總統盼公私協力提升心血管疾病防治與照護　落實「健康台灣」願景",
  "subtitle": "總統出席「2026年亞太心臟學會大會暨...開幕式」",
  "content": "賴清德總統今(16)日上午出席...\n\n總統以英文致詞...",
  "content_paragraphs": [
    "賴清德總統今(16)日上午出席...",
    "總統以英文致詞，內容為：",
    "..."
  ],
  "images": [
    "https://www.president.gov.tw/img/Image/712365c5-...jpg",
    "https://www.president.gov.tw/img/Image/26ccf326-...jpg"
  ],
  "english_url": "https://english.president.gov.tw/NEWS/7115"
}
```

### Field descriptions

| Field | Type | Description |
|---|---|---|
| `id` | integer | The NEWS ID on the presidential website |
| `url` | string | Full URL of the article |
| `date_roc` | string | Date in the ROC (Republic of China) calendar, e.g. "115年05月16日" |
| `date` | string | Date converted to ISO 8601 format, e.g. "2026-05-16" |
| `title` | string | Main headline of the article |
| `subtitle` | string | Secondary title, often the full event name |
| `content` | string | Full article text with paragraphs joined by double newlines |
| `content_paragraphs` | array of strings | Each paragraph as a separate string |
| `images` | array of strings | Absolute URLs to attached photos |
| `english_url` | string | URL to the English translation on english.president.gov.tw (empty if unavailable) |

### Date conversion

The ROC calendar year = Western year minus 1911. The `roc_to_iso_date` function handles this:

| ROC date | ISO date |
|---|---|
| 92年07月20日 | 2003-07-20 |
| 104年11月27日 | 2015-11-27 |
| 115年05月16日 | 2026-05-16 |

### File organization

Articles are organized into year-based subdirectories derived from the ISO date:

```
news_json/
├── 2003/          ← Earliest articles
│   ├── 3.json
│   ├── 50.json
│   └── 100.json
├── 2005/
│   └── 10000.json
├── 2015/
│   └── 20000.json
├── 2022/
│   └── 26690.json
├── 2026/          ← Latest articles
│   ├── 40050.json
│   └── 40055.json
└── unknown/       ← Articles where date parsing failed
```

---

## 7. How It Works

### crawler.py — full crawl

1. **Auto-detect max ID** — fetch `/Page/35` and find the highest `/NEWS/{id}` link.
2. **Load skip list** — combine IDs from `crawl_progress.json` and existing files in `news_json/`.
3. **Build work queue** — generate IDs from max down to 1, excluding the skip list.
4. **Process sequentially** — for each ID:
   - Wait `DELAY_BETWEEN_REQUESTS` seconds.
   - Call `fetch_article(id)`.
   - Save the result to `news_json/YYYY/ID.json`.
5. **Rate-limit detection** — if 50 consecutive IDs return "not found", the delay doubles (up to 60s max). It resets when a valid article is found.
6. **Save progress** — write `crawl_progress.json` every 100 IDs.

### crawler_latest.py — daily update

1. **Auto-detect max ID** — same as above.
2. **Count down from max ID** — fetch articles one by one.
3. **Stop after 50 found** — once 50 valid articles have been saved, exit.
4. **Always overwrite** — does not check for existing files; always writes fresh JSON.

### fetch_article — shared core

1. Send GET request to `https://www.president.gov.tw/NEWS/{id}`.
2. Force `r.encoding = "utf-8"` to avoid double-encoding.
3. Check if the final URL redirected to the homepage (means the ID doesn't exist) — return `None`.
4. Parse HTML with BeautifulSoup + lxml.
5. Extract date, title, subtitle, body paragraphs, images, and English link from the `div.pageWrap1` container.
6. Convert the ROC date to ISO format.
7. Return a dict with all extracted fields.
8. On network errors, retry up to 3 times with exponential backoff (1s, 2s, 4s).

### Detecting non-existent articles

Not all sequential IDs have articles. The website handles invalid IDs by issuing an HTTP redirect to the homepage (`https://www.president.gov.tw/`). The crawler detects this by checking if the final URL after following redirects matches the homepage.

### Rate-limit detection

The presidential website may temporarily return redirects for all requests when too many are made in a short period. Since both "article doesn't exist" and "rate limited" result in a homepage redirect, the crawler uses a heuristic: if 50 consecutive IDs all return "not found," it assumes rate limiting and exponentially increases the delay between requests (doubling each time, up to 60 seconds). The delay resets to normal as soon as a valid article is found.

---

## 8. Configuration

### Constants in `crawler.py`

| Constant | Default | Description |
|---|---|---|
| `BASE_URL` | `https://www.president.gov.tw` | Website base URL |
| `OUTPUT_DIR` | `news_json` | Directory for saved JSON files |
| `PROGRESS_FILE` | `crawl_progress.json` | Resume state file |
| `MAX_ID` | `41000` | Fallback upper bound (used only if auto-detect fails) |
| `REQUEST_TIMEOUT` | `30` | HTTP timeout in seconds |
| `RETRY_COUNT` | `3` | Max retries per request |
| `DELAY_BETWEEN_REQUESTS` | `0.5` | Base delay in seconds |

### HTTP session

The crawler uses a persistent `requests.Session` with these headers:

```
User-Agent: Mozilla/5.0 (compatible; PresidentialNewsCrawler/1.0)
Accept-Language: zh-TW,zh;q=0.9,en;q=0.8
```

The session reuses TCP connections across requests for efficiency.

---

## 9. Resume & Progress Tracking

### crawler.py

The full crawler has two layers of resume support:

1. **Progress file** (`crawl_progress.json`) — tracks all processed IDs (both found and not-found):

```json
{
  "completed_ids": [1, 2, 3, 4, 5],
  "failed_ids": [],
  "last_id": 5
}
```

2. **Disk scan** — on startup, scans `news_json/` for existing `.json` files and skips those IDs too.

Together, this means:

- You can **stop the crawler at any time** (Ctrl+C) and resume later.
- You can **re-run the same command** and it will only process remaining IDs.
- To **start fresh**, delete both `crawl_progress.json` and the `news_json/` directory.

Progress is saved every 100 articles.

### crawler_latest.py

No progress tracking. Always fetches the latest 50 articles and overwrites existing files. Designed to be idempotent for daily cron use.

---

## 10. Logging

### crawler.py

Output goes to both the console and `crawler.log` (UTF-8 encoded).

```
2026-05-18 11:03:07,582 [INFO] Crawling 40005 IDs from 40055 down to 1 (150 already done)
2026-05-18 11:03:12,648 [INFO] Progress: 100/40005 | Found: 42 | Not found: 58 | Errors: 0
```

### crawler_latest.py

Output goes to both the console and `crawler_latest.log`.

```
2026-05-18 11:10:00,123 [INFO] Detected latest NEWS ID: 40055
2026-05-18 11:10:01,456 [INFO] [1/50] ID 40055: 總統盼公私協力提升心血管疾病防治與照護...
```

### Log levels

| Level | When |
|---|---|
| `INFO` | Start, progress, completion, each found article (latest crawler) |
| `WARNING` | Failed to fetch after all retries, possible rate limiting detected |
| `ERROR` | Unexpected exception during article processing |

---

## 11. Troubleshooting

### All text appears as mojibake (garbled characters)

The server sends `Content-Type: text/html` without a charset. The crawler forces UTF-8 decoding. If you see garbled output, ensure your terminal supports UTF-8 and the `LANG` environment variable is set appropriately:

```bash
export LANG=en_US.UTF-8
```

### Many consecutive IDs return "not found"

This may indicate **rate limiting**. The crawler will automatically detect this (after 50 consecutive misses) and back off with increasing delays. If the problem persists, increase the base delay:

```bash
python3 crawler.py --delay 2.0
```

### Crawler hangs or times out

The default timeout is 30 seconds per request. Edit `REQUEST_TIMEOUT` in `crawler.py` if the server is consistently slow.

### Want to re-crawl failed IDs

Failed IDs are tracked in `crawl_progress.json` under `failed_ids`. To retry them, remove those IDs from `completed_ids` and re-run the crawler for that range.

### Disk space

Each JSON file is 1-10 KB. For ~29,000 articles, expect approximately **100-200 MB** of total disk usage.

---

## 12. Known Limitations

1. **No listing page crawl** — the crawler cannot paginate through the listing at `/Page/35` because it uses client-side JavaScript. Instead, it iterates through article IDs directly.

2. **No embedded media extraction** — the crawler extracts photo URLs from the gallery section but does not download the actual image files. Video embeds and other media in `div.embedBox1` are not extracted.

3. **Related news not captured** — the "相關新聞" (related news) carousel at the bottom of each article is not extracted. These are links to other articles that can be found by their own IDs.

4. **Rate limiting** — the presidential website may temporarily block rapid requests. The crawler includes automatic backoff detection, but very aggressive crawling may still trigger blocks. If this happens, increase the `--delay` value.

5. **Mixed categories** — the crawler targets "總統府新聞" (Presidential Office News) at `/Page/35`. Other sections of the website (presidential orders at `/Page/36`, daily schedules at `/Page/37`, etc.) use the same `/NEWS/{id}` URL space and may also be captured by the ID-based crawl.

6. **Keyword analysis is exact match** — `analyze.py` performs simple substring matching, not word boundary or fuzzy matching. Searching for "台" will also match "台灣", "台北", etc.
