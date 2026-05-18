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

As of May 2026, the archive contains **1,944 pages** of news articles (~15 articles per page, ~29,000 total), spanning from **1992 (ROC year 81)** to the present. Individual articles are accessible at URLs like:

```
https://www.president.gov.tw/NEWS/{id}
```

where `{id}` is an integer. The listing pages are numbered 1 (newest) through 1,944 (oldest).

---

## 2. Website Analysis

### The internal pagination API

The listing page at `/Page/35` uses client-side JavaScript for pagination. The pagination links are rendered as `<a href="javascript:;">` and trigger an AJAX call.

By analyzing the site's JavaScript (`/_content/custom/ViewComponents/News/index.js`), we discovered the internal API:

```
POST https://www.president.gov.tw/WebAPI/News/List
```

#### Request parameters

| Parameter | Value | Description |
|---|---|---|
| `lang` | `zh` | Language code |
| `country` | `TW` | Country code |
| `detailno` | `1` | Page number (1 = newest) |
| `tag` | `Page` | URL segment type |
| `no` | `35` | The page ID for "總統府新聞" |

#### Required headers

| Header | Value | Description |
|---|---|---|
| `CUSTOMER-CSRF-HEADER` | (empty string) | CSRF token; the page has no `CustomerFieldName` input, so empty works |

The API returns an HTML fragment containing the news list for that page.

#### Discovery process

The JavaScript pagination flow was traced through these files:

1. **`index.js`** — calls `PostAjaxNoShowHint()` with URL `GetApiUrl() + "/WebAPI/News/List"` and form data including `detailno` (page number)
2. **`apiurl.js`** — `GetApiUrl()` returns the current host
3. **`formUtility.js`** — `SetPostAjaxObject()` adds `tag`, `no` from `WebMenuUtility.Parse(location.pathname)`; for `/Page/35` this yields `tag=Page`, `no=35`
4. **`headerUtility.js`** — `GetDefaultHeaders()` reads a CSRF token from `input[name='CustomerFieldName']`, which doesn't exist in the page HTML, so the header is sent with an empty value

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
│   ├── 1992/
│   │   └── ...
│   ├── 2003/
│   │   └── ...
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
crawler_latest.py          Imports: init_session, fetch_listing_page,
    ↑                               fetch_article, save_article
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

The total number of listing pages is **auto-detected** from the site. The crawler paginates through all listing pages (page 1 = newest, page 1944 = oldest), discovers the article IDs on each page, and fetches each article. Articles already on disk are skipped by default.

Estimated runtime: **several hours** at default settings (0.5s delay per request, ~15 articles per page, ~1944 pages).

#### Crawl a specific page range

```bash
# Crawl only the first 10 pages (newest articles)
python3 crawler.py --start-page 1 --end-page 10

# Crawl pages 500 to 600
python3 crawler.py --start-page 500 --end-page 600
```

#### Re-fetch existing articles

```bash
python3 crawler.py --no-skip
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
| `--start-page` | `1` | First listing page to crawl (1 = newest) |
| `--end-page` | (auto-detect) | Last listing page to crawl; detected from the site if not provided |
| `--delay` | `0.5` | Seconds between requests |
| `--no-skip` | off | Re-fetch articles even if they already exist on disk |
| `--single` | (none) | Fetch and print one article by ID |

---

### Latest news (daily update)

```bash
python3 crawler_latest.py
```

Fetches the **50 most recent** articles by paginating through the first few listing pages. **Always overwrites** existing JSON files to capture any edits or corrections to recent articles.

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

#### Filter by date range

```bash
# Full date
python3 analyze.py "台灣" --from 2026-03-01 --to 2026-05-31

# Year-month (covers the entire month)
python3 analyze.py "台灣" --from 2026-03 --to 2026-05

# Year only (covers the entire year)
python3 analyze.py "川普" --from 2026 --to 2026
```

Both `--from` and `--to` are optional and can be used independently.

#### List matching article titles

```bash
$ python3 analyze.py "川普" --from 2026 --list
Found 18 articles containing '川普' (out of 293 total)

2026-01  ██████████████████████████████ 3
2026-02  ████████████████████████████████████████ 4
...

--- Matching articles ---
  2026-01-14  [39764] 總統接見美國亞利桑納州鳳凰城市長...
  2026-01-21  [39777] 總統接見德國馬歇爾基金會訪團...
  ...
```

#### CLI reference

| Argument | Default | Description |
|---|---|---|
| `keyword` | (required) | Keyword to search for |
| `--by` | `month` | Group results by `date`, `month`, or `year` |
| `--from` | (none) | Start date, inclusive (e.g. `2026-01-01`, `2026-01`, or `2026`) |
| `--to` | (none) | End date, inclusive (e.g. `2026-05-31`, `2026-05`, or `2026`) |
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
| 81年01月09日 | 1992-01-09 |
| 92年07月20日 | 2003-07-20 |
| 104年11月27日 | 2015-11-27 |
| 115年05月16日 | 2026-05-16 |

### File organization

Articles are organized into year-based subdirectories derived from the ISO date:

```
news_json/
├── 1992/          ← Earliest articles (page 1944)
│   └── 22734.json
├── 2003/
│   ├── 3.json
│   └── 100.json
├── 2015/
│   └── 20000.json
├── 2026/          ← Latest articles (page 1)
│   ├── 40050.json
│   └── 40055.json
└── unknown/       ← Articles where date parsing failed
```

---

## 7. How It Works

### Two-phase crawl

The crawler uses a two-phase approach:

1. **Phase 1: Discover article IDs** — POST to the internal listing API (`/WebAPI/News/List`) with a page number. The API returns an HTML fragment containing article links (`/NEWS/{id}`). The crawler extracts all IDs from each page.

2. **Phase 2: Fetch full articles** — for each discovered ID, send a GET request to `/NEWS/{id}` and parse the full article page.

This eliminates the previous approach of guessing sequential IDs, which wasted requests on non-existent IDs and triggered rate limiting.

### crawler.py — full crawl

1. **Initialize session** — visit `/Page/35` to establish cookies.
2. **Detect total pages** — parse "共 1944 頁" from the listing page.
3. **Scan existing files** — scan `news_json/` for articles already on disk.
4. **Load progress** — read `crawl_progress.json` to skip already-completed pages.
5. **For each listing page** (1 through 1944):
   - POST to `/WebAPI/News/List` with `detailno={page}` to get article IDs.
   - For each ID not already on disk: fetch the full article and save as JSON.
   - Mark the page as completed in progress file.
6. **Log progress** — after each page, log fetched/skipped/error counts.

### crawler_latest.py — daily update

1. **Initialize session** — same as above.
2. **Paginate from page 1** — fetch listing pages starting from the newest.
3. **Fetch each article** — always overwrite, no skip check.
4. **Stop after 50** — once 50 articles have been saved, exit.

### fetch_article — shared core

1. Send GET request to `https://www.president.gov.tw/NEWS/{id}`.
2. Force `r.encoding = "utf-8"` to avoid double-encoding.
3. Check if the final URL redirected to the homepage (means the ID doesn't exist) — return `None`.
4. Parse HTML with BeautifulSoup + lxml.
5. Extract date, title, subtitle, body paragraphs, images, and English link from the `div.pageWrap1` container.
6. Convert the ROC date to ISO format.
7. Return a dict with all extracted fields.
8. On network errors, retry up to 3 times with exponential backoff (1s, 2s, 4s).

---

## 8. Configuration

### Constants in `crawler.py`

| Constant | Default | Description |
|---|---|---|
| `BASE_URL` | `https://www.president.gov.tw` | Website base URL |
| `API_URL` | `{BASE_URL}/WebAPI/News/List` | Internal listing API endpoint |
| `OUTPUT_DIR` | `news_json` | Directory for saved JSON files |
| `PROGRESS_FILE` | `crawl_progress.json` | Resume state file |
| `REQUEST_TIMEOUT` | `30` | HTTP timeout in seconds |
| `RETRY_COUNT` | `3` | Max retries per request |
| `DELAY_BETWEEN_REQUESTS` | `0.5` | Base delay in seconds |

### HTTP session

The crawler uses a persistent `requests.Session` with standard browser headers:

```
User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8
Accept-Language: zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7
```

The session reuses TCP connections and cookies across requests for efficiency.

---

## 9. Resume & Progress Tracking

### crawler.py

The full crawler tracks progress at the **page level**:

```json
{
  "completed_pages": [1, 2, 3, 4, 5],
  "last_page": 5
}
```

On startup, it also scans `news_json/` for existing article files. Together:

- **Completed pages** are skipped entirely (no API call or article fetches).
- **Articles on disk** are skipped even for pages not yet marked complete (e.g. if the crawler was interrupted mid-page).
- You can **stop the crawler at any time** (Ctrl+C) and resume later.
- To **start fresh**, delete both `crawl_progress.json` and the `news_json/` directory.

### crawler_latest.py

No progress tracking. Always fetches the latest 50 articles and overwrites existing files. Designed to be idempotent for daily cron use.

---

## 10. Logging

### crawler.py

Output goes to both the console and `crawler.log` (UTF-8 encoded).

```
2026-05-18 11:30:01,182 [INFO] Found 1091 existing articles on disk
2026-05-18 11:30:02,209 [INFO] Page 1/1944 | IDs: 15 | Fetched: 0 | Skipped: 15 | Total: 0 fetched, 15 skipped, 0 errors
2026-05-18 11:30:03,129 [INFO] Page 2/1944 | IDs: 15 | Fetched: 0 | Skipped: 15 | Total: 0 fetched, 30 skipped, 0 errors
```

### crawler_latest.py

Output goes to both the console and `crawler_latest.log`.

```
2026-05-18 11:10:01,456 [INFO] [1/50] ID 40055: 總統盼公私協力提升心血管疾病防治與照護...
2026-05-18 11:10:02,789 [INFO] [2/50] ID 40054: 總統府回應美國總統川普接受媒體訪問相關內容...
```

### Log levels

| Level | When |
|---|---|
| `INFO` | Start, page progress, completion, each found article (latest crawler) |
| `WARNING` | Failed to fetch a specific article, failed listing page |
| `ERROR` | Failed to fetch a listing page after all retries |

---

## 11. Troubleshooting

### All text appears as mojibake (garbled characters)

The server sends `Content-Type: text/html` without a charset. The crawler forces UTF-8 decoding. If you see garbled output, ensure your terminal supports UTF-8 and the `LANG` environment variable is set appropriately:

```bash
export LANG=en_US.UTF-8
```

### Listing API returns 400 or empty response

The API requires:
1. A valid session — the crawler calls `init_session()` first to visit `/Page/35` and establish cookies.
2. The `CUSTOMER-CSRF-HEADER` header (can be empty).
3. The `tag=Page` and `no=35` parameters.

If the API stops working, check whether the site's JavaScript files have changed by re-examining `/_content/custom/ViewComponents/News/index.js`.

### Crawler hangs or times out

The default timeout is 30 seconds per request. Edit `REQUEST_TIMEOUT` in `crawler.py` if the server is consistently slow. You can also increase the delay between requests:

```bash
python3 crawler.py --delay 2.0
```

### Old progress file causes errors

If you see `KeyError: 'completed_pages'`, the progress file is from the old ID-based crawler. Delete it:

```bash
rm crawl_progress.json
```

### Disk space

Each JSON file is 1-10 KB. For ~29,000 articles, expect approximately **100-200 MB** of total disk usage.

---

## 12. Known Limitations

1. **No embedded media extraction** — the crawler extracts photo URLs from the gallery section but does not download the actual image files. Video embeds and other media in `div.embedBox1` are not extracted.

2. **Related news not captured** — the "相關新聞" (related news) carousel at the bottom of each article is not extracted. These are links to other articles that can be found by their own IDs.

3. **API stability** — the internal `/WebAPI/News/List` endpoint is undocumented and could change without notice. If the site is redesigned, the API parameters or response format may break.

4. **Single category only** — the crawler targets "總統府新聞" (Presidential Office News) at `/Page/35` (`no=35`). Other sections like presidential orders (`/Page/36`) or daily schedules (`/Page/37`) would require changing the `no` parameter.

5. **Keyword analysis is exact match** — `analyze.py` performs simple substring matching, not word boundary or fuzzy matching. Searching for "台" will also match "台灣", "台北", etc.
