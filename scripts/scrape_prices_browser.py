#!/usr/bin/env python3
"""Browser-based scraper fallback using Playwright.

Use this when direct HTTP scraping is blocked by anti-bot protections.
Requires:
  pip install playwright
  python -m playwright install chromium
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_FILE = ROOT / "data" / "prices.json"

AH_URL = "https://www.ah.be/producten/23421/groenten-aardappelen"
COLRUYT_URL = "https://www.colruyt.be/nl/producten?categories=1675&page=1"


def normalize_unit(text: str) -> tuple[float, str]:
    lowered = (text or "").lower().strip()
    if lowered in {"st", "stuk", "stuks", "pc", "pcs", "unit"}:
        return 1.0, "unit"
    if "kg" in lowered:
        return 1.0, "kg"
    if re.search(r"(?:^|/)l\b", lowered):
        return 1.0, "l"
    return 1.0, "unit"


def parse_price(text: str) -> float | None:
    match = re.search(r"(\d+[\.,]\d{1,2})", text or "")
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def scrape_colruyt(page) -> list[dict]:
    page.goto(COLRUYT_URL, wait_until="networkidle", timeout=60000)
    cards = page.locator(".product-grid-item")
    items = []
    for i in range(cards.count()):
        card = cards.nth(i)
        name = card.locator(".card__text").first.inner_text().strip() if card.locator(".card__text").count() else ""
        if not name:
            continue

        whole = card.locator(".rounded-number").first.inner_text().strip() if card.locator(".rounded-number").count() else ""
        decimal = card.locator(".decimal").first.inner_text().strip() if card.locator(".decimal").count() else ""
        unit_text = card.locator(".unit").first.inner_text().strip() if card.locator(".unit").count() else "st"

        price = None
        if whole and decimal and whole.isdigit():
            price = float(f"{whole}.{re.sub(r'[^0-9]', '', decimal)[:2].ljust(2,'0')}")
        if price is None:
            price = parse_price(card.inner_text())
        if price is None:
            continue

        quantity, unit_type = normalize_unit(unit_text)
        items.append({
            "name": name,
            "category": "Vegetables",
            "unitType": unit_type,
            "quantity": quantity,
            "prices": {"Colruyt": price, "Lidl": None, "Albert Heijn": None},
        })
    return items


def scrape_ah(page) -> list[dict]:
    page.goto(AH_URL, wait_until="networkidle", timeout=60000)
    cards = page.locator("article, [data-testhook*='product-card'], [class*='product-card']")
    items = []
    for i in range(min(cards.count(), 300)):
        card = cards.nth(i)
        text = card.inner_text().strip()
        if not text:
            continue

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        name = lines[0]
        price = parse_price(text)
        if price is None:
            continue

        unit_text = ""
        for token in ["/st", "/kg", "/l", "st", "kg", "l"]:
            if token in text.lower():
                unit_text = token
                break
        quantity, unit_type = normalize_unit(unit_text)
        items.append({
            "name": name,
            "category": "Vegetables",
            "unitType": unit_type,
            "quantity": quantity,
            "prices": {"Colruyt": None, "Lidl": None, "Albert Heijn": price},
        })
    return items


def merge(colruyt_items: list[dict], ah_items: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for item in colruyt_items + ah_items:
        key = item["name"].lower()
        if key not in merged:
            merged[key] = item
        else:
            for shop, price in item["prices"].items():
                if price is not None:
                    merged[key]["prices"][shop] = price
    return sorted(merged.values(), key=lambda x: x["name"].lower())


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        print(
            "Playwright is not installed. Run: pip install playwright && python -m playwright install chromium",
            file=sys.stderr,
        )
        raise SystemExit(2)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        colruyt_items = scrape_colruyt(page)
        ah_items = scrape_ah(page)
        browser.close()

    dataset = merge(colruyt_items, ah_items)
    if not dataset and OUT_FILE.exists():
        print("Warning: browser scraper produced 0 products, keeping existing dataset")
        return

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(dataset, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(dataset)} products to {OUT_FILE}")


if __name__ == "__main__":
    main()
