# Taiwan Presidential Office News Crawler

A complete guide to crawling and extracting news articles from the Republic of China (Taiwan) Presidential Office website.

---

## Table of Contents

1. [Background](#1-background)
2. [Website Analysis](#2-website-analysis)
3. [Architecture](#3-architecture)
4. [Installation](#4-installation)
5. [Usage](#5-usage)
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
crawler.py
│
├── fetch_article(news_id)     Fetch one article, parse HTML, return dict
├── roc_to_iso_date(str)       Convert "115年05月16日" → "2026-05-16"
├── save_article(article)      Write JSON to news_json/YYYY/ID.json
├── crawl_range(start, end)    Orchestrate batch crawl with thread pool
├── load_progress()            Read crawl_progress.json
├── save_progress(progress)    Write crawl_progress.json
└── main()                     CLI argument parsing and entry point

Output files:
├── news_json/
│   ├── 2003/
│   │   ├── 1.json
│   │   ├── 2.json
│   │   └── ...
│   ├── 2004/
│   ├── ...
│   └── 2026/
│       ├── 40050.json
│       └── 40055.json
├── crawl_progress.json        Resume state
└── crawler.log                Execution log
```

---

## 4. Installation

### Prerequisites

- Python 3.8+
- pip packages: `requests`, `beautifulsoup4`, `lxml`

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

This scans IDs 1 through 41,000. Estimated runtime: **several hours** at default settings (5 workers, 0.5s delay).

### Crawl a specific range

```bash
python3 crawler.py --start 30000 --end 35000
```

### Fetch a single article (for testing)

```bash
python3 crawler.py --single 40055
```

Prints the JSON to stdout without saving to disk.

### Adjust concurrency and politeness

```bash
# Slower, gentler (2 workers, 1 second delay)
python3 crawler.py --workers 2 --delay 1.0

# Faster (10 workers, 0.2 second delay)
python3 crawler.py --workers 10 --delay 0.2
```

### CLI reference

| Argument | Default | Description |
|---|---|---|
| `--start` | `1` | First NEWS ID to crawl |
| `--end` | `41000` | Last NEWS ID to crawl |
| `--workers` | `5` | Number of concurrent threads |
| `--delay` | `0.5` | Seconds between requests (divided across workers) |
| `--single` | (none) | Fetch and print one article by ID |

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
  "subtitle": "總統出席「2026年亞太心臟學會大會暨中華民國心臟學會2026年第56屆年會暨學術演講會開幕式」",
  "content": "賴清德總統今(16)日上午出席...\n\n總統以英文致詞...",
  "content_paragraphs": [
    "賴清德總統今(16)日上午出席...",
    "總統以英文致詞，內容為：",
    "..."
  ],
  "images": [
    "https://www.president.gov.tw/img/Image/712365c5-e65b-4cc2-947b-bf027048724a.jpg",
    "https://www.president.gov.tw/img/Image/26ccf326-e075-426c-97b6-bec6f2da8774.jpg"
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
│   ├── 10.json
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

### Step-by-step flow

1. **Parse CLI arguments** — determine ID range, worker count, and delay.
2. **Load progress** — read `crawl_progress.json` to skip already-completed IDs.
3. **Build work queue** — generate the list of IDs to crawl (range minus completed).
4. **Process in batches of 50** — for each batch:
   - Submit all IDs to a `ThreadPoolExecutor` with the configured worker count.
   - A small delay (`DELAY / WORKERS`) is inserted between each submission.
   - Each worker calls `fetch_article(id)`.
5. **`fetch_article` for each ID:**
   - Send GET request to `https://www.president.gov.tw/NEWS/{id}`.
   - Force `r.encoding = "utf-8"` to avoid double-encoding.
   - Check if the final URL redirected to the homepage (means the ID doesn't exist) — return `None`.
   - Parse HTML with BeautifulSoup + lxml.
   - Extract date, title, subtitle, body paragraphs, images, and English link.
   - Convert the ROC date to ISO format.
   - Return a dict with all extracted fields.
6. **Save results** — valid articles are written to `news_json/YYYY/ID.json`.
7. **Update progress** — after each batch, write `crawl_progress.json`.
8. **Log progress** — print found/not-found/error counts after each batch.

### Detecting non-existent articles

Not all sequential IDs have articles. The website handles invalid IDs by issuing an HTTP 302 redirect to the homepage (`https://www.president.gov.tw/`). The crawler detects this by checking if the final URL after following redirects matches the homepage.

Valid articles may first return HTTP 308 (permanent redirect from HTTP to HTTPS) before returning 200 with content. The crawler follows all redirects automatically via `requests`.

### Concurrency model

The crawler uses Python's `ThreadPoolExecutor` for concurrent HTTP requests. The `DELAY_BETWEEN_REQUESTS` value is divided by the number of workers to approximate a target rate. For example, with 5 workers and a 0.5s delay, each request submission is staggered by 0.1s.

### Retry logic

Each request is retried up to 3 times on network errors (`requests.RequestException`). The delay between retries uses exponential backoff: 1s, 2s, 4s.

---

## 8. Configuration

### Constants in `crawler.py`

| Constant | Default | Description |
|---|---|---|
| `BASE_URL` | `https://www.president.gov.tw` | Website base URL |
| `OUTPUT_DIR` | `news_json` | Directory for saved JSON files |
| `PROGRESS_FILE` | `crawl_progress.json` | Resume state file |
| `MAX_ID` | `41000` | Upper bound for article IDs |
| `WORKERS` | `5` | Default thread count |
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

The crawler saves its progress to `crawl_progress.json` after every batch of 50 IDs:

```json
{
  "completed_ids": [1, 2, 3, 4, 5],
  "failed_ids": [],
  "last_id": 5
}
```

| Field | Description |
|---|---|
| `completed_ids` | All IDs that have been processed (both found and not-found) |
| `failed_ids` | IDs that encountered unrecoverable errors |
| `last_id` | Highest ID in the most recent batch |

On restart, the crawler reads this file and skips all `completed_ids`. This means:

- You can **stop the crawler at any time** (Ctrl+C) and resume later.
- You can **re-run the same command** and it will only process remaining IDs.
- To **start fresh**, delete `crawl_progress.json`.

---

## 10. Logging

All output goes to both the console and `crawler.log` (UTF-8 encoded).

### Log format

```
2026-05-18 10:56:27,692 [INFO] Crawling 6 IDs from 40050 to 40055 (0 already done)
2026-05-18 10:56:28,762 [INFO] Progress: 6/6 | Found: 5 | Not found: 1 | Errors: 0
2026-05-18 10:56:28,762 [INFO] Done. Found: 5, Not found: 1, Errors: 0
```

### Log levels

| Level | When |
|---|---|
| `INFO` | Start, batch progress, completion |
| `WARNING` | Failed to fetch an article after all retries |
| `ERROR` | Unexpected exception during article processing |

---

## 11. Troubleshooting

### All text appears as mojibake (garbled characters)

The server sends `Content-Type: text/html` without a charset. The crawler forces UTF-8 decoding. If you see garbled output, ensure your terminal supports UTF-8 and the `LANG` environment variable is set appropriately:

```bash
export LANG=en_US.UTF-8
```

### Many IDs return "not found"

This is expected. Not every sequential ID corresponds to an article. The ID space is shared across the entire website, so gaps are normal. Out of ~41,000 IDs, approximately 29,000 are valid news articles.

### Crawler hangs or times out

The default timeout is 30 seconds per request. If the server is slow:

```bash
# The timeout is hardcoded — edit REQUEST_TIMEOUT in crawler.py
# Or reduce workers to be gentler on the server
python3 crawler.py --workers 2 --delay 2.0
```

### Want to re-crawl failed IDs

Failed IDs are tracked in `crawl_progress.json` under `failed_ids`. To retry them, remove those IDs from `completed_ids` and re-run the crawler for that range.

### Disk space

Each JSON file is 1-10 KB. For ~29,000 articles, expect approximately **100-200 MB** of total disk usage.

---

## 12. Known Limitations

1. **No listing page crawl** — the crawler cannot paginate through the listing at `/Page/35` because it uses client-side JavaScript. Instead, it iterates through article IDs directly.

2. **ID upper bound is hardcoded** — `MAX_ID` is set to 41,000. As new articles are published, this value must be increased. Check the latest article ID on the website and adjust accordingly.

3. **No embedded media extraction** — the crawler extracts photo URLs from the gallery section but does not download the actual image files. Video embeds and other media in `div.embedBox1` are not extracted.

4. **Related news not captured** — the "相關新聞" (related news) carousel at the bottom of each article is not extracted. These are links to other articles that can be found by their own IDs.

5. **Rate limiting** — the presidential website does not appear to enforce aggressive rate limiting, but the crawler includes configurable delays as a courtesy. If you experience blocks, increase the `--delay` value.

6. **Single category only** — the crawler targets "總統府新聞" (Presidential Office News) at `/Page/35`. Other sections of the website (presidential orders at `/Page/36`, daily schedules at `/Page/37`, etc.) use the same `/NEWS/{id}` URL space and may also be captured by the ID-based crawl.
