#!/usr/bin/env python3
"""Very small MVP scraper for food prices.

This script attempts to extract product prices from public product pages and
writes normalized output to `data/prices.json`.

Note: supermarket websites often require cookies, JavaScript rendering, and may
block bots. For a reliable production flow, move to official partner/data APIs
or licensed feeds.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import bs4
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT_FILE = ROOT / "data" / "prices.json"


@dataclass
class ProductTarget:
    name: str
    category: str
    unit_type: str
    quantity: float
    colruyt_url: Optional[str] = None
    lidl_url: Optional[str] = None
    ah_url: Optional[str] = None


def extract_price_from_html(html: str) -> Optional[float]:
    soup = bs4.BeautifulSoup(html, "html.parser")

    json_ld_nodes = soup.select('script[type="application/ld+json"]')
    for node in json_ld_nodes:
      if not node.string:
        continue
      try:
        data = json.loads(node.string)
      except json.JSONDecodeError:
        continue

      stack = data if isinstance(data, list) else [data]
      for item in stack:
        offers = item.get("offers") if isinstance(item, dict) else None
        if isinstance(offers, dict):
          price = offers.get("price")
          if price is not None:
            try:
              return float(price)
            except (TypeError, ValueError):
              pass

    text = soup.get_text(" ", strip=True)
    match = re.search(r"(\d+[\.,]\d{2})\s?€", text)
    if match:
      return float(match.group(1).replace(",", "."))

    return None


def fetch_price(url: str) -> Optional[float]:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; SmartShoppingMVP/1.0)",
        "Accept-Language": "nl-BE,nl;q=0.9,en;q=0.8",
    }
    try:
        response = requests.get(url, timeout=12, headers=headers)
        response.raise_for_status()
    except requests.RequestException:
        return None

    return extract_price_from_html(response.text)


def build_dataset(products: list[ProductTarget]) -> list[dict]:
    dataset = []
    for product in products:
        dataset.append(
            {
                "name": product.name,
                "category": product.category,
                "unitType": product.unit_type,
                "quantity": product.quantity,
                "prices": {
                    "Colruyt": fetch_price(product.colruyt_url)
                    if product.colruyt_url
                    else None,
                    "Lidl": fetch_price(product.lidl_url) if product.lidl_url else None,
                    "Albert Heijn": fetch_price(product.ah_url)
                    if product.ah_url
                    else None,
                },
            }
        )

    return dataset


def main() -> None:
    targets = [
        ProductTarget(
            name="Semi-skimmed Milk",
            category="Dairy",
            unit_type="l",
            quantity=1,
            # Fill in product URLs that are valid in your region.
            colruyt_url=None,
            lidl_url=None,
            ah_url=None,
        )
    ]

    result = build_dataset(targets)
    OUT_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote {len(result)} products to {OUT_FILE}")


if __name__ == "__main__":
    main()
