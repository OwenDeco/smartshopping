#!/usr/bin/env python3
"""Scrape vegetable products for SmartShopping MVP.

Targets:
- Albert Heijn vegetables: https://www.ah.be/producten/23421/groenten-aardappelen
- Colruyt vegetables: https://www.colruyt.be/nl/producten?categories=1675&page=1
- Lidl: unavailable online in this MVP (kept as NA)

Parsing strategy
- First parse concrete HTML product cards (name + price + unit) where possible.
- Then parse JSON embedded in script tags as fallback.
- Keep logic conservative to reduce wrong matches.
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
    return re.sub(r"\s+", " ", unescape(name)).strip()


def strip_tags(value: str) -> str:
    return clean_name(re.sub(r"<[^>]+>", " ", value))


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", ".")
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def normalize_unit(unit_text: str | None) -> tuple[float, str]:
    if not unit_text:
        return 1.0, "unit"

    lowered = unit_text.lower().strip()

    if lowered in {"st", "stuk", "stuks", "pc", "pcs", "unit"}:
        return 1.0, "unit"

    per_kg = re.search(r"(?:/|per\s*)kg\b", lowered)
    if per_kg:
        return 1.0, "kg"

    per_l = re.search(r"(?:/|per\s*)l\b", lowered)
    if per_l:
        return 1.0, "l"

    kg = re.search(r"(\d+(?:[\.,]\d+)?)\s?kg\b", lowered)
    if kg:
        return float(kg.group(1).replace(",", ".")), "kg"

    gram = re.search(r"(\d+)\s?g\b", lowered)
    if gram:
        return float(gram.group(1)) / 1000.0, "kg"

    liter = re.search(r"(\d+(?:[\.,]\d+)?)\s?l\b", lowered)
    if liter:
        return float(liter.group(1).replace(",", ".")), "l"

    ml = re.search(r"(\d+)\s?ml\b", lowered)
    if ml:
        return float(ml.group(1)) / 1000.0, "l"

    return 1.0, "unit"


def parse_price_parts(card_html: str) -> float | None:
    whole = re.search(r'class="rounded-number"[^>]*>(\d+)<', card_html)
    decimal = re.search(r'class="decimal"[^>]*>(\d{1,2})<', card_html)
    if whole and decimal:
        return float(f"{whole.group(1)}.{decimal.group(1).zfill(2)}")

    direct = re.search(r"(\d+[\.,]\d{1,2})", card_html)
    if direct:
        return float(direct.group(1).replace(",", "."))

    return None


def parse_html_cards(html: str) -> list[Product]:
    products: list[Product] = []

    # 1) Parse Colruyt-style cards from attributes + nested fields.
    card_blocks = re.findall(
        r'<article[^>]*class="[^"]*product-grid-item[^"]*"[^>]*>(.*?)</article>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not card_blocks:
        card_blocks = re.findall(
            r'<div[^>]*class="[^"]*product-grid-item[^"]*"[^>]*>(.*?)</div>\s*</div>',
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )

    for card in card_blocks:
        name_match = re.search(r'class="card__text"[^>]*>(.*?)<', card, flags=re.DOTALL)
        if not name_match:
            continue
        name = strip_tags(name_match.group(1))
        if not name:
            continue

        price = parse_price_parts(card)
        if price is None:
            # data attributes sometimes contain exact parsed price
            data_price = re.search(r'data-tms-product-price="([\d\.,]+)"', card)
            price = parse_float(data_price.group(1)) if data_price else None
        if price is None:
            continue

        unit = None
        unit_match = re.search(r'class="unit"[^>]*>\s*(.*?)\s*</span>', card, flags=re.DOTALL)
        if unit_match:
            unit = strip_tags(unit_match.group(1))
        if not unit:
            qty_match = re.search(r'class="card__quantity"[^>]*>(.*?)<', card, flags=re.DOTALL)
            if qty_match:
                unit = strip_tags(qty_match.group(1))

        quantity, unit_type = normalize_unit(unit)
        products.append(Product(name=name, price=price, quantity=quantity, unit_type=unit_type))

    # 2) Generic HTML fallback for cards with product name + unit price text.
    generic_cards = re.finditer(
        r'<[^>]+class="[^"]*(?:card|product)[^"]*"[^>]*>(.*?)</[^>]+>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    for m in generic_cards:
        card = m.group(1)
        name_m = re.search(r'class="[^"]*(?:card__text|product-title|title)[^"]*"[^>]*>(.*?)<', card, re.DOTALL)
        price_m = re.search(r'(\d+[\.,]\d{1,2})\s*/\s*([a-zA-Z]+)', card)
        if not name_m or not price_m:
            continue
        name = strip_tags(name_m.group(1))
        price = parse_float(price_m.group(1))
        if not name or price is None:
            continue
        quantity, unit_type = normalize_unit(price_m.group(2))
        products.append(Product(name=name, price=price, quantity=quantity, unit_type=unit_type))

    return products


def walk_json(node: Any):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk_json(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk_json(item)


def extract_product_from_node(node: dict[str, Any]) -> Product | None:
    name = node.get("name") or node.get("title")
    if not isinstance(name, str):
        return None

    price_candidates = [
        node.get("price"),
        node.get("salesPrice"),
        node.get("nowPrice"),
        node.get("currentPrice"),
    ]

    offers = node.get("offers")
    if isinstance(offers, dict):
        price_candidates.append(offers.get("price"))

    price = next((p for p in (parse_float(c) for c in price_candidates) if p is not None), None)
    if price is None:
        return None

    unit_candidates = [
        node.get("unit"),
        node.get("unitType"),
        node.get("priceUnit"),
        node.get("salesUnit"),
        node.get("displayUnit"),
        node.get("content"),
        node.get("description"),
    ]
    quantity, unit_type = 1.0, "unit"
    for unit_candidate in unit_candidates:
        if not isinstance(unit_candidate, str):
            continue
        quantity, unit_type = normalize_unit(unit_candidate)
        if quantity != 1.0 or unit_type != "unit":
            break

    return Product(name=clean_name(name), price=price, quantity=quantity, unit_type=unit_type)


def parse_products(html: str) -> list[Product]:
    products: list[Product] = []

    # Priority: concrete HTML product-card parsing
    products.extend(parse_html_cards(html))

    # Fallback: parse JSON from script tags
    scripts = re.findall(
        r'<script[^>]*>(.*?)</script>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )

    for script in scripts:
        raw = script.strip()
        if not raw:
            continue

        json_candidates = []
        if raw.startswith("{") or raw.startswith("["):
            json_candidates.append(raw)
        if "__NEXT_DATA__" in raw:
            match = re.search(r"__NEXT_DATA__\s*=\s*(\{.*\})\s*;?", raw, flags=re.DOTALL)
            if match:
                json_candidates.append(match.group(1))

        for candidate in json_candidates:
            try:
                data = json.loads(candidate)
            except json.JSONDecodeError:
                continue

            for node in walk_json(data):
                if isinstance(node, dict):
                    product = extract_product_from_node(node)
                    if product:
                        products.append(product)

    unique: dict[str, Product] = {}
    for product in products:
        key = product.name.lower()
        if key not in unique:
            unique[key] = product

    return list(unique.values())


def scrape_shop(url: str) -> list[Product]:
    html = fetch_html(url)
    return parse_products(html)


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
