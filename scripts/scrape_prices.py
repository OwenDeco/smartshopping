#!/usr/bin/env python3
"""Scrape vegetable products for SmartShopping MVP.

Sources requested by user:
- Albert Heijn vegetables: https://www.ah.be/producten/23421/groenten-aardappelen
- Colruyt vegetables: https://www.colruyt.be/nl/producten?categories=1675&page=1
- Lidl: no online catalogue available for this MVP -> always NA.

The script writes output to data/prices.json in the format expected by app.js.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT_FILE = ROOT / "data" / "prices.json"

AH_URL = "https://www.ah.be/producten/23421/groenten-aardappelen"
COLRUYT_URL = "https://www.colruyt.be/nl/producten?categories=1675&page=1"


@dataclass
class Product:
    name: str
    price: float
    quantity: float = 1.0
    unit_type: str = "unit"


def fetch_html(url: str) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; SmartShoppingScraper/1.0)",
            "Accept-Language": "nl-BE,nl;q=0.9,en;q=0.8",
        },
    )
    with urlopen(req, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def clean_name(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", unescape(name)).strip()
    return cleaned


def parse_size_from_name(name: str) -> tuple[float, str]:
    lowered = name.lower()
    kg = re.search(r"(\d+[\.,]?\d*)\s?kg", lowered)
    if kg:
        return float(kg.group(1).replace(",", ".")), "kg"

    gram = re.search(r"(\d+)\s?g\b", lowered)
    if gram:
        return float(gram.group(1)) / 1000.0, "kg"

    liter = re.search(r"(\d+[\.,]?\d*)\s?l\b", lowered)
    if liter:
        return float(liter.group(1).replace(",", ".")), "l"

    ml = re.search(r"(\d+)\s?ml\b", lowered)
    if ml:
        return float(ml.group(1)) / 1000.0, "l"

    return 1.0, "unit"


def walk_json(node: Any):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk_json(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk_json(item)


def parse_json_ld_products(html: str) -> list[Product]:
    products: list[Product] = []
    scripts = re.findall(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    for script in scripts:
        raw = script.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue

        for node in walk_json(data):
            if not isinstance(node, dict):
                continue
            name = node.get("name")
            offers = node.get("offers")
            price = None
            if isinstance(offers, dict):
                price = offers.get("price")
            if name and price is not None:
                try:
                    amount = float(str(price).replace(",", "."))
                except ValueError:
                    continue
                quantity, unit_type = parse_size_from_name(str(name))
                products.append(
                    Product(name=clean_name(str(name)), price=amount, quantity=quantity, unit_type=unit_type)
                )

    return products


def parse_regex_fallback(html: str) -> list[Product]:
    products: list[Product] = []
    # generic product snippets; catches common e-commerce JSON fragments
    patterns = [
        r'"name"\s*:\s*"([^"]{3,120})"[^\{\}]{0,600}?"price"\s*:\s*"?(\d+[\.,]\d{2})"?',
        r'"title"\s*:\s*"([^"]{3,120})"[^\{\}]{0,600}?"price"\s*:\s*"?(\d+[\.,]\d{2})"?',
    ]

    seen = set()
    for pattern in patterns:
        for match in re.finditer(pattern, html, flags=re.IGNORECASE | re.DOTALL):
            name = clean_name(match.group(1))
            if len(name) < 3 or name.lower() in seen:
                continue
            try:
                amount = float(match.group(2).replace(",", "."))
            except ValueError:
                continue
            quantity, unit_type = parse_size_from_name(name)
            products.append(Product(name=name, price=amount, quantity=quantity, unit_type=unit_type))
            seen.add(name.lower())

    return products


def scrape_shop(url: str) -> list[Product]:
    html = fetch_html(url)
    products = parse_json_ld_products(html)
    if not products:
        products = parse_regex_fallback(html)

    unique: dict[str, Product] = {}
    for product in products:
        key = product.name.lower()
        if key not in unique:
            unique[key] = product

    return list(unique.values())


def to_dataset(colruyt_products: list[Product], ah_products: list[Product]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    def ensure(product: Product):
        key = product.name.lower()
        if key not in merged:
            merged[key] = {
                "name": product.name,
                "category": "Vegetables",
                "unitType": product.unit_type,
                "quantity": product.quantity,
                "prices": {"Colruyt": None, "Lidl": None, "Albert Heijn": None},
            }
        return merged[key]

    for product in colruyt_products:
        row = ensure(product)
        row["prices"]["Colruyt"] = product.price

    for product in ah_products:
        row = ensure(product)
        row["prices"]["Albert Heijn"] = product.price

    return sorted(merged.values(), key=lambda item: item["name"].lower())


def main() -> None:
    try:
        colruyt_products = scrape_shop(COLRUYT_URL)
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"Warning: failed Colruyt scrape: {exc}")
        colruyt_products = []

    try:
        ah_products = scrape_shop(AH_URL)
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"Warning: failed Albert Heijn scrape: {exc}")
        ah_products = []

    dataset = to_dataset(colruyt_products, ah_products)
    if not dataset and OUT_FILE.exists():
        print("Warning: scraper produced 0 products, keeping existing dataset")
        return

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(dataset, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(dataset)} products to {OUT_FILE}")


if __name__ == "__main__":
    main()
