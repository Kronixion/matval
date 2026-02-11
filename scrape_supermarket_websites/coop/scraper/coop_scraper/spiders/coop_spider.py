"""Coop product spider using personalization API.

This initial implementation loads category IDs from a static JSON mapping
captured from recent HAR recordings and paginates through the
``search/entities/by-attribute`` endpoint to yield structured ``CoopItem``
records.
"""

from __future__ import annotations

import json
import math
import os
import re
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, Optional

import scrapy
from scrapy import Request
from scrapy.http import JsonRequest, Response

from coop_scraper.items import CoopItem


class CoopSpider(scrapy.Spider):
    """Initial Coop spider that enumerates known categories and scrapes products."""

    name = "coop"
    allowed_domains = ["coop.se", "external.api.coop.se"]

    personalization_endpoint = (
        "https://external.api.coop.se/personalization/search/entities/by-attribute"
    )

    device = "desktop"
    store_id = "251300"
    customer_groups = "CUSTOMER_PRIVATE"
    page_size = 48

    custom_settings = {
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1.0,
        "AUTOTHROTTLE_MAX_DELAY": 10.0,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Content-Type": "application/json",
            "Pragma": "no-cache",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) CoopScraper/0.1",
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subscription_key = kwargs.get("subscription_key")
        self.category_mapping = self._load_category_mapping()
        self.category_id_to_slug = {v: k for k, v in self.category_mapping.items()}

    @staticmethod
    def _load_category_mapping() -> Dict[str, str]:
        mapping_path = Path(__file__).resolve().parents[1] / "data" / "coop_category_ids.json"
        if not mapping_path.exists():
            raise FileNotFoundError(
                "Category mapping JSON not found: "
                f"{mapping_path}. Ensure HAR extraction ran successfully."
            )
        with mapping_path.open(encoding="utf-8") as handle:
            data = json.load(handle)
            return dict(data)

    def start_requests(self) -> Iterable[Request]:
        if not self.subscription_key:
            self.subscription_key = self._resolve_subscription_key()

        for slug, category_id in self.category_mapping.items():
            payload = self._build_payload(slug, category_id, skip=0)
            meta = {
                "slug": slug,
                "category_id": category_id,
                "skip": 0,
                "page": 0,
            }
            yield JsonRequest(
                url=self._personalization_url(),
                data=payload,
                headers=self._personalization_headers(),
                method="POST",
                meta=meta,
                callback=self.parse_listing,
                cb_kwargs={"slug": slug, "category_id": category_id},
            )

    def parse_listing(
        self,
        response: Response,
        slug: str,
        category_id: str,
    ) -> Iterable[Request]:
        data = response.json()
        results = data.get("results") or {}
        items = results.get("items") or results.get("results") or []

        for product in items:
            item = self._build_item(slug, product)
            if item:
                yield item

        count = results.get("count") or 0
        current_skip = response.meta.get("skip", 0)
        if count and current_skip + self.page_size < count:
            next_skip = current_skip + self.page_size
            payload = self._build_payload(slug, category_id, skip=next_skip)
            meta = {
                "slug": slug,
                "category_id": category_id,
                "skip": next_skip,
                "page": math.floor(next_skip / self.page_size),
            }
            yield JsonRequest(
                url=self._personalization_url(),
                data=payload,
                headers=self._personalization_headers(),
                method="POST",
                meta=meta,
                callback=self.parse_listing,
                cb_kwargs={"slug": slug, "category_id": category_id},
            )

    def _build_item(self, slug: str, product: dict) -> Optional[CoopItem]:
        if not product:
            return None

        top_category, subcategory, subcategory_slug = self._resolve_categories(product)

        promotions = product.get("onlinePromotions") or []
        comparative_unit = product.get("comparativePriceUnit") or {}

        return CoopItem(
            category=top_category,
            subcategory=subcategory,
            subcategory_slug=subcategory_slug,
            name=product.get("name"),
            url=self._build_product_url(product, slug),
            price=product.get("salesPrice"),
            unit_price=product.get("comparativePrice"),
            unit_quantity_name=comparative_unit.get("text"),
            unit_quantity_abbrev=comparative_unit.get("unit"),
            currency="SEK",
            quantity_type=product.get("packageSizeInformation"),
            nutrition=self._extract_nutrition(product),
            availability=product.get("availableOnline"),
            product_id=product.get("id"),
            ean=product.get("ean"),
            promotions=promotions,
        )

    def _build_payload(self, slug: str, category_id: str, skip: int) -> dict:
        return {
            "attribute": {"name": "categoryIds", "value": category_id},
            "requestAlias": {
                "name": "Subcategory",
                "value": slug.split("/")[-1] or slug,
                "details": slug,
            },
            "resultsOptions": {
                "skip": skip,
                "take": self.page_size,
                "sortBy": [],
                "facets": [],
            },
        }

    def _personalization_url(self) -> str:
        return (
            f"{self.personalization_endpoint}?api-version=v1"
            f"&store={self.store_id}&groups={self.customer_groups}"
            f"&device={self.device}&direct=false"
        )

    def _personalization_headers(self) -> dict:
        return {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Origin": "https://www.coop.se",
            "Referer": "https://www.coop.se/",
        }

    def _resolve_categories(self, product: dict) -> tuple[Optional[str], Optional[str], Optional[str]]:
        nav_categories = product.get("navCategories") or []
        if not nav_categories:
            return None, None, None

        primary = nav_categories[0]
        subcategory_name = primary.get("name")
        subcategory_id = primary.get("code")
        subcategory_slug = self.category_id_to_slug.get(str(subcategory_id))

        super_categories = primary.get("superCategories") or []
        top_category_name = None
        if super_categories:
            top_category_name = super_categories[0].get("name")

        return top_category_name, subcategory_name, subcategory_slug

    def _extract_nutrition(self, product: dict) -> Optional[dict]:
        nutrient_information = product.get("nutrientInformation") or []
        header_block = None
        for entry in nutrient_information:
            if isinstance(entry, dict) and entry.get("header"):
                header_block = entry["header"]
                break

        nutrient_links = product.get("nutrientLinks") or []
        values: list[dict] = []
        for link in nutrient_links:
            if not isinstance(link, dict):
                continue
            description = link.get("description")
            amounts = link.get("amount") or []
            amount_value: Optional[float | str] = None
            if amounts:
                candidate = amounts[0]
                if isinstance(candidate, str):
                    normalized = candidate.replace(",", ".").strip()
                    try:
                        amount_value = float(normalized)
                    except ValueError:
                        amount_value = candidate
                else:
                    amount_value = candidate

            values.append(
                {
                    "slug": self._slugify(description),
                    "description": description,
                    "unit": link.get("unit"),
                    "amount": amount_value,
                }
            )

        if not header_block and not values:
            return None

        return {
            "header": header_block,
            "values": values,
        }

    @staticmethod
    def _slugify(value: Optional[str]) -> Optional[str]:
        if not value:
            return None

        sanitized = value.strip().lower()
        translations = str.maketrans({"å": "a", "ä": "a", "ö": "o"})
        sanitized = sanitized.translate(translations)
        sanitized = re.sub(r"[^a-z0-9]+", "-", sanitized)
        sanitized = sanitized.strip("-")
        return sanitized or None

    def _resolve_subscription_key(self) -> str:
        crawler = getattr(self, "crawler", None)
        if crawler:
            cached = getattr(crawler.engine, "_coop_subscription_key", None)
            if cached:
                return cached

            configured = crawler.settings.get("COOP_SUBSCRIPTION_KEY")
            if configured:
                crawler.engine._coop_subscription_key = configured
                return configured

        env_key = os.environ.get("COOP_SUBSCRIPTION_KEY")
        if env_key:
            if crawler:
                crawler.engine._coop_subscription_key = env_key
            return env_key

        key = self._fetch_subscription_key()
        if crawler:
            crawler.engine._coop_subscription_key = key
        return key

    def _fetch_subscription_key(self) -> str:
        request = urllib.request.Request(
            "https://www.coop.se/handla/aktuella-erbjudanden/",
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) CoopScraper/0.1",
            },
        )

        with urllib.request.urlopen(request) as response:
            html = response.read().decode("utf-8", errors="ignore")

        match = re.search(r'\"personalizationApiSubscriptionKey\"\s*:\s*\"([0-9a-fA-F]{32})\"', html)
        if not match:
            raise ValueError(
                "Unable to automatically determine Coop subscription key. "
                "Pass it explicitly via -a subscription_key or COOP_SUBSCRIPTION_KEY."
            )

        key = match.group(1)
        return key

    def _build_product_url(self, product: dict, fallback_slug: str) -> Optional[str]:
        url = product.get("url") or product.get("productUrl")
        if url:
            return url

        product_id = product.get("id")
        name = product.get("name") or ""
        if not product_id or not name:
            return None

        slug = self.category_id_to_slug.get(str(product.get("navCategories", [{}])[0].get("code"))) or fallback_slug
        sanitized_name = "-".join(name.lower().split())
        return f"https://www.coop.se/handla/varor{slug}/{sanitized_name}-{product_id}"