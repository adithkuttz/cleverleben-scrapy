# Cleverleben Scrapy Spider

This is a ready-to-run Scrapy project that crawls **https://www.cleverleben.at/produktauswahl**,
follows categories/subcategories, paginates listings, and extracts product detail data into CSV/JSON.

## Quickstart

```bash
# 1) Create a virtual env (optional but recommended)
python -m venv .venv && source .venv/bin/activate  # (on Windows: .venv\Scripts\activate)

# 2) Install Scrapy
pip install scrapy

# 3) Run (JSON)
scrapy crawl clever -O output.json

# 4) Also export CSV
scrapy crawl clever -O output.csv
```

> By default, the spider stops after collecting 1,000 items (configurable via `-a max_items=1000`).

## Fields
- product_url
- product_name
- price (raw, as seen on page)
- regular_price (normalized, dot decimal)
- currency
- images (list)
- product_description
- unique_id (from URL digits)
- ingredients
- details
- product_id

## Notes
- Respects robots.txt (toggle in `settings.py`).
- Adds a small delay to be polite.
- Uses robust XPath/CSS fallbacks because the site is content-managed.
