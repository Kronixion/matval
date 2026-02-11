"""Spider for collecting product listings from Hemköp."""

from __future__ import annotations

from typing import Iterator, List, Optional, Set, Tuple

import scrapy
from scrapy import Request
from scrapy.http import JsonRequest, Response

from hemkop_scraper.items import HemkopItem

# Top-level category slugs for the /c/ product listing endpoint.
# These use the *old-style* slugs that the Axfood backend recognises;
# the leftMenu category-tree API returns *new-style* slugs that 404 on /c/.
_TOP_LEVEL_CATEGORIES = [
    "kott-fagel-och-chark",
    "frukt-och-gront",
    "delikatessen",
    "vegetariskt",
    "fisk-och-skaldjur",
    "fryst",
    "mejeri-ost-och-agg",
    "skafferi",
    "brod-och-kakor",
    "godis-snacks-och-glass",
    "dryck",
    "fardigmat",
    "barn",
    "hem-och-hushall",
    "blommor-och-tillbehor",
    "halsa-och-skonhet",
    "apotek-och-lakemedel",
    "djur",
    "kiosk",
]

_PAGE_SIZE = 100


class HemkopSpider(scrapy.Spider):
    """Scraper for the Hemköp grocery catalogue.

    Strategy:
    1. Hit ``/c/<slug>?page=0&size=100&sort=topRated`` for every top-level
       category (19 known slugs).
    2. Each listing response contains a ``subCategories`` array with correct
       slugs — recursively schedule those subcategories too.
    3. Paginate through every (sub)category until all products are discovered.
    4. For each unique product code, fetch ``/axfood/rest/p/<code>`` to get
       nutrition and detailed metadata.
    """

    name = "hemkop"
    allowed_domains = ["hemkop.se"]

    # robots.txt specifies Crawl-delay: 10 and Visit-time: 0400-0845 UTC.
    # Crawl-delay is enforced below; visit-time must be enforced externally
    # (e.g. schedule the spider to run only between 04:00–08:45 UTC).
    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 10,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
        "DOWNLOAD_TIMEOUT": 30,
    }

    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:143.0) "
            "Gecko/20100101 Firefox/143.0"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.5",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.hemkop.se/",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._queued_slugs: Set[str] = set()
        self._seen_product_codes: Set[str] = set()

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def start_requests(self) -> Iterator[Request]:
        for slug in _TOP_LEVEL_CATEGORIES:
            yield from self._request_category(slug)

    # ------------------------------------------------------------------
    # Category listing
    # ------------------------------------------------------------------

    def _request_category(
        self, full_slug: str, *, page: int = 0
    ) -> Iterator[Request]:
        if page == 0:
            if full_slug in self._queued_slugs:
                return
            self._queued_slugs.add(full_slug)

        parts = full_slug.split("/")
        category_slug = parts[0]
        subcategory_slug = "/".join(parts[1:]) or None

        url = (
            f"https://www.hemkop.se/c/{full_slug}"
            f"?page={page}&size={_PAGE_SIZE}&sort=topRated"
        )
        yield JsonRequest(
            url,
            headers=self._HEADERS,
            callback=self.parse_product_listing,
            errback=self._handle_listing_error,
            cb_kwargs={
                "category_slug": category_slug,
                "full_slug": full_slug,
                "subcategory_slug": subcategory_slug,
            },
        )

    def parse_product_listing(
        self,
        response: Response,
        category_slug: str,
        full_slug: str,
        subcategory_slug: Optional[str],
    ) -> Iterator[Request]:
        try:
            data = response.json()
        except Exception:
            self.logger.error("Failed to parse JSON for %s", response.url)
            return

        # --- discover subcategories from the response -----------------
        for sub in data.get("subCategories") or []:
            sub_url = sub.get("url")
            if sub_url:
                yield from self._request_category(sub_url)

        # --- products -------------------------------------------------
        subcategory_name = data.get("categoryName")
        products = data.get("results") or []
        self.logger.info(
            "Category %s page %s: %d products",
            full_slug,
            data.get("pagination", {}).get("currentPage", "?"),
            len(products),
        )

        for product in products:
            code = product.get("code")
            if not code:
                continue
            if code in self._seen_product_codes:
                continue
            self._seen_product_codes.add(code)
            yield from self._queue_product_detail(
                category_slug, subcategory_slug, subcategory_name, product,
            )

        # --- pagination -----------------------------------------------
        pagination = data.get("pagination", {})
        current_page = pagination.get("currentPage", 0)
        num_pages = pagination.get("numberOfPages", 1)
        if current_page + 1 < num_pages:
            yield from self._request_category(full_slug, page=current_page + 1)

    def _handle_listing_error(self, failure):
        self.logger.warning("Listing request failed: %s", failure.value)

    # ------------------------------------------------------------------
    # Product detail
    # ------------------------------------------------------------------

    def _queue_product_detail(
        self,
        category_slug: str,
        subcategory_slug: Optional[str],
        subcategory_name: Optional[str],
        product: dict,
    ) -> Iterator[Request]:
        code = product["code"]
        url = f"https://www.hemkop.se/axfood/rest/p/{code}?include=BREADCRUMB,NUTRIENTS"
        yield JsonRequest(
            url,
            headers=self._HEADERS,
            callback=self.parse_product_detail,
            errback=self._handle_detail_error,
            cb_kwargs={
                "category_slug": category_slug,
                "subcategory_slug": subcategory_slug,
                "subcategory_name": subcategory_name,
                "listing_product": product,
            },
        )

    def parse_product_detail(
        self,
        response: Response,
        category_slug: str,
        subcategory_slug: Optional[str],
        subcategory_name: Optional[str],
        listing_product: dict,
    ) -> Iterator[HemkopItem]:
        try:
            detail = response.json()
        except Exception:
            self.logger.warning(
                "Failed to parse detail for %s", listing_product.get("code")
            )
            detail = None

        item = self._build_item(
            category_slug, subcategory_slug, subcategory_name,
            listing_product, detail,
        )
        if item:
            yield item

    def _handle_detail_error(self, failure):
        self.logger.warning("Detail request failed: %s", failure.value)

    # ------------------------------------------------------------------
    # Item builder
    # ------------------------------------------------------------------

    def _build_item(
        self,
        category_slug: str,
        subcategory_slug: Optional[str],
        subcategory_name: Optional[str],
        listing: Optional[dict],
        detail: Optional[dict],
    ) -> Optional[HemkopItem]:
        listing = listing or {}
        detail = detail or {}

        code = detail.get("code") or listing.get("code")
        if not code:
            return None

        name = detail.get("name") or listing.get("name")
        price = detail.get("priceValue")
        if price is None:
            price = listing.get("priceValue") or listing.get("price")

        unit_price = detail.get("comparePrice") or listing.get("comparePrice")
        unit_name = (
            detail.get("comparePriceUnit") or listing.get("comparePriceUnit")
        )

        availability = detail.get("outOfStock")
        if availability is None:
            availability = listing.get("outOfStock")

        quantity_type = (
            detail.get("productLine2")
            or listing.get("productLine2")
            or detail.get("displayVolume")
            or listing.get("displayVolume")
        )

        price_string = detail.get("price") or listing.get("price")
        currency = None
        if isinstance(price_string, str):
            parts = price_string.split()
            if parts:
                currency = parts[-1]

        return HemkopItem(
            category=category_slug,
            subcategory=subcategory_name,
            subcategory_slug=subcategory_slug,
            name=name,
            url=f"https://www.hemkop.se/produkt/{code}",
            price=price,
            unit_price=unit_price,
            unit_quantity_name=unit_name,
            unit_quantity_abbrev=unit_name,
            currency=currency,
            quantity_type=quantity_type,
            nutrition=self._build_nutrition(detail, listing),
            availability=availability,
        )

    @staticmethod
    def _build_nutrition(detail: dict, listing: dict) -> Optional[dict]:
        nutrition_description = (
            detail.get("nutritionDescription")
            or listing.get("nutritionDescription")
        )
        fact_list = (
            detail.get("nutritionsFactList")
            or listing.get("nutritionsFactList")
        )
        nutrient_headers = detail.get("nutrientHeaders") or []

        rows: List[dict] = []
        seen: Set[Tuple[Optional[str], Optional[str], Optional[str]]] = set()

        for entry in fact_list or []:
            key = (
                entry.get("typeCode"),
                entry.get("unitCode"),
                entry.get("value"),
            )
            if key in seen:
                continue
            rows.append({
                "type_code": entry.get("typeCode"),
                "unit_code": entry.get("unitCode"),
                "value": entry.get("value"),
                "precision": entry.get("measurementPrecisionCode"),
            })
            seen.add(key)

        for header in nutrient_headers:
            for nutrient in header.get("nutrientDetails", []):
                key = (
                    nutrient.get("nutrientTypeCode"),
                    nutrient.get("measurementUnitCode"),
                    nutrient.get("quantityContained"),
                )
                if key in seen:
                    continue
                rows.append({
                    "type_code": nutrient.get("nutrientTypeCode"),
                    "unit_code": nutrient.get("measurementUnitCode"),
                    "value": nutrient.get("quantityContained"),
                    "precision": nutrient.get("measurementPrecisionCode"),
                })
                seen.add(key)

        if not rows:
            return None
        return {"description": nutrition_description, "rows": rows}
