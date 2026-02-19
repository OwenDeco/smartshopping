# SmartShopping MVP

Modern one-page website to compare food product prices across:
- Colruyt
- Lidl
- Albert Heijn

## Features

- Side-by-side comparison normalized to **per kg / per l / per unit**.
- Product search filter.
- Category filter.
- Missing prices shown as **NA**.
- Best current deal highlighted.
- **Refresh scraped dataset** button with loading spinner while scraping is running.

## Connect to GitHub and clone locally

### Option A (SSH)

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
cat ~/.ssh/id_ed25519.pub
# Add this key in GitHub: Settings -> SSH and GPG keys -> New SSH key
ssh -T git@github.com

git clone git@github.com:<YOUR_USERNAME>/<YOUR_REPO>.git
cd <YOUR_REPO>
```

### Option B (HTTPS)

```bash
git clone https://github.com/<YOUR_USERNAME>/<YOUR_REPO>.git
cd <YOUR_REPO>
```

## Run locally

Run the custom local server (includes `/api/scrape` endpoint):

```bash
python server.py
```

Then open: <http://localhost:8080>

> Note: if you use `python -m http.server`, the refresh-scrape button cannot work because it needs `POST /api/scrape`.

## Price accuracy note

- The project now starts with an empty `data/prices.json` by default to avoid showing stale or guessed prices.
- Click **Refresh scraped dataset** to scrape live data.
- The scraper now reads product cards directly from HTML first (e.g. `card__text`, `rounded-number` + `decimal`, and unit like `st`) before JSON fallback.
- The scraper also keeps a JSON/script fallback when HTML structures differ between shops.
- If a website blocks scraping temporarily, the previous dataset is preserved (not overwritten with empty data).

## Alternative scraping method (recommended when blocked)

If direct HTTP requests are blocked, use Playwright browser scraping:

```bash
pip install playwright
python -m playwright install chromium
python scripts/scrape_prices_browser.py
```

`server.py` now tries the browser scraper first on refresh, and falls back to the HTTP scraper.
The API response includes an `attempts` array so you can inspect why a method failed.

## Scraping vegetables dataset

The scraper targets requested category pages:
- Albert Heijn vegetables: `https://www.ah.be/producten/23421/groenten-aardappelen`
- Colruyt vegetables: `https://www.colruyt.be/nl/producten?categories=1675&page=1`
- Lidl: no online category in this MVP, so Lidl prices are written as `null` (shown as `NA` in UI).

Run scraper manually:

```bash
python scripts/scrape_prices.py
```
