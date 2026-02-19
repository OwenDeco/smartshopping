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

## Run locally

Because this app loads JSON via `fetch`, run it from a local web server:

```bash
python -m http.server 8080
```

Then open: <http://localhost:8080>

## Data model

Source file: `data/prices.json`

Each product uses:

```json
{
  "name": "Semi-skimmed Milk",
  "category": "Dairy",
  "unitType": "l",
  "quantity": 1,
  "prices": {
    "Colruyt": 1.15,
    "Lidl": 1.09,
    "Albert Heijn": 1.29
  }
}
```

Use `null` to represent not available:

```json
"Albert Heijn": null
```

## Scraping bootstrap

A minimal scraper starter exists in `scripts/scrape_prices.py`.

```bash
pip install requests beautifulsoup4
python scripts/scrape_prices.py
```

Update product URLs in that script for your region and legal permissions. Some supermarket sites require consent flows or APIs and may not allow automated scraping.
