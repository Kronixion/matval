"""ICA grocery catalogue spider leveraging public JSON APIs."""

from __future__ import annotations

import json
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import scrapy
from scrapy import Request
from scrapy.http import Response

from ica_scraper.items import ICAItem

_BATCH_SIZE = 50
_WAF_TOKEN_TTL = 240  # seconds before proactive refresh (token lasts ~5 min)
_MAX_WAF_RETRIES = 3
_BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class CategorySeed:
    """Representation of a category request seed."""

    identifier: str
    name: str
    full_path: str


class IcaSpider(scrapy.Spider):
    """Scrapes ICA's public store catalogue across categories."""

    name = "ica"
    allowed_domains = ["handlaprivatkund.ica.se"]

    store_id_default = "1003380"
    api_base = "https://handlaprivatkund.ica.se/stores/{store_id}/api/v6/products"
    put_base = "https://handlaprivatkund.ica.se/stores/{store_id}/api/webproductpagews/v6/products"

    handle_httpstatus_list = [202, 403]

    custom_settings = {
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1.0,
        "AUTOTHROTTLE_MAX_DELAY": 10.0,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5,
        "COOKIES_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
            "Origin": "https://handlaprivatkund.ica.se",
            "Ecom-Request-Source": "web",
            "Ecom-Request-Source-Version": "1",
            "User-Agent": _BROWSER_UA,
        },
    }

    root_categories: List[CategorySeed] = [
        CategorySeed("03968fc5-dadb-4e2b-8983-6abbf641df3c", "Frukt & Grönt", "Frukt-Grönt"),
        CategorySeed("4d07744d-fd8d-47ea-89e6-38c49ca44652", "Kött, Chark & Fågel", "Kött-Chark-Fågel"),
        CategorySeed("3bfbe616-f05c-4fdf-823a-f55ed6eed6c2", "Fisk & Skaldjur", "Fisk-Skaldjur"),
        CategorySeed("03d68f50-5a8c-4b9c-95a1-f0f017cacab0", "Mejeri & Ost", "Mejeri-Ost"),
        CategorySeed("c7739997-6b40-45c9-9042-a6102ae9779c", "Bröd & Kakor", "Bröd-Kakor"),
        CategorySeed("0b6beda8-526a-49c5-b533-cb3b8474f3b3", "Vegetariskt", "Vegetariskt"),
        CategorySeed("67062250-87a0-4b75-be6c-21413a477e79", "Färdigmat", "Färdigmat"),
        CategorySeed("3f7fdab0-b5c9-451b-b081-98f7b6f01d82", "Barn", "Barn"),
        CategorySeed("0053d478-6e25-4982-aa2c-ea5e5770a071", "Glass, Godis & Snacks", "Glass-Godis-Snacks"),
        CategorySeed("7a765e3c-d8a5-4f1d-afa3-93761d10f3c1", "Dryck", "Dryck"),
        CategorySeed("31c18410-0856-4908-8834-1eea8808c498", "Skafferi", "Skafferi"),
        CategorySeed("3937612b-efec-4ede-91ae-57904b8473aa", "Fryst", "Fryst"),
        CategorySeed("8a38226b-8bba-4905-8ed3-bb28e32eadf5", "Apotek, Hälsa & Skönhet", "Apotek-Hälsa-Skönhet"),
        CategorySeed("e89c368d-4d41-4086-9802-90a13490bac8", "Träning & Återhämtning", "Träning-Återhämtning"),
        CategorySeed("42388d25-26a7-40f5-ac5d-7a65c8da784f", "Djur", "Djur"),
        CategorySeed("978ea4a6-5267-4fb7-a474-67e5dceeb3c9", "Städ, Tvätt & Papper", "Städ-Tvätt-Papper"),
        CategorySeed("9d39ff06-9c72-46c5-a69e-dbaa2fab7411", "Kök", "Kök"),
        CategorySeed("2b2f384d-2caa-43f3-ad8e-403b1a7be4e5", "Hem & Inredning", "Hem-Inredning"),
        CategorySeed("665217df-7775-4b3b-980b-3e094003a5a1", "Fritid", "Fritid"),
        CategorySeed("cae1e58c-a558-4eff-a899-7ece0ce575f9", "Blommor & Trädgård", "Blommor-Trädgård"),
        CategorySeed("331db70a-9d3f-4574-96fc-3543d7149a57", "Tobak", "Tobak"),
    ]

    def __init__(self, *args, store_id: Optional[str] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.store_id = store_id or self.store_id_default
        self._visited_categories: set[str] = set()
        self._emitted_product_ids: set[str] = set()
        self._waf_token: Optional[str] = None
        self._csrf_token: Optional[str] = None
        self._session_cookies: Dict[str, str] = {}
        self._token_obtained_at: float = 0

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def start_requests(self) -> Iterable[Request]:
        self._refresh_session()

        for seed in self.root_categories:
            slug = self._slugify(seed.full_path)
            meta = {
                "category_id": seed.identifier,
                "category_chain": [
                    {
                        "id": seed.identifier,
                        "name": seed.name,
                        "slug": slug,
                    }
                ],
            }
            yield self._build_category_request(seed.identifier, slug, meta)

    # ------------------------------------------------------------------
    # Request builders
    # ------------------------------------------------------------------

    def _build_category_request(
        self, category_id: str, slug: str, meta: Dict, dont_filter: bool = False,
    ) -> Request:
        url = self.api_base.format(store_id=self.store_id)
        url = f"{url}?category={category_id}"

        self._maybe_refresh_session()
        headers = self._request_headers(slug, category_id)
        cookies = self._auth_cookies()

        return Request(
            url,
            headers=headers,
            cookies=cookies,
            meta=meta,
            callback=self.parse_category,
            dont_filter=dont_filter,
        )

    def _build_product_batch_request(
        self,
        product_ids: List[str],
        category_chain: List[Dict],
    ) -> Request:
        url = self.put_base.format(store_id=self.store_id)
        self._maybe_refresh_session()
        cookies = self._auth_cookies()
        headers = {
            "Accept": "application/json; charset=utf-8",
            "Content-Type": "application/json; charset=utf-8",
            "Origin": "https://handlaprivatkund.ica.se",
            "Referer": "https://handlaprivatkund.ica.se/",
            "Ecom-Request-Source": "web",
            "Ecom-Request-Source-Version": "1",
            "User-Agent": _BROWSER_UA,
        }
        if self._csrf_token:
            headers["x-csrf-token"] = self._csrf_token

        return Request(
            url,
            method="PUT",
            headers=headers,
            cookies=cookies,
            body=json.dumps(product_ids),
            meta={"category_chain": category_chain, "product_ids": product_ids},
            callback=self.parse_product_batch,
            dont_filter=True,
        )

    def _auth_cookies(self) -> Dict[str, str]:
        cookies = dict(self._session_cookies)
        if self._waf_token:
            cookies["aws-waf-token"] = self._waf_token
        return cookies

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    def parse_category(self, response: Response) -> Iterable[Request | ICAItem]:
        # Detect WAF block and refresh
        if response.status == 202:
            retries = response.meta.get("waf_retries", 0)
            if retries >= _MAX_WAF_RETRIES:
                self.logger.error("Max WAF retries reached for %s; skipping", response.url)
                return
            self.logger.warning("Got 202 (WAF challenge); refreshing session (retry %d)", retries + 1)
            self._refresh_session()
            meta = response.meta.copy()
            category_id = meta.get("category_id")
            chain = meta.get("category_chain", [])
            slug = chain[-1]["slug"] if chain else ""
            new_meta = {"category_id": category_id, "category_chain": chain, "waf_retries": retries + 1}
            yield self._build_category_request(category_id, slug, new_meta, dont_filter=True)
            return

        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError as exc:
            self.logger.error("Failed to decode JSON for %s: %s", response.url, exc)
            return

        result = payload.get("result") or {}
        entities = payload.get("entities") or {}
        products = entities.get("product") or {}

        category_chain = response.meta.get("category_chain", [])
        current_category_id = response.meta.get("category_id")

        # Discover subcategories
        for subcategory in result.get("categories", []):
            sub_id = subcategory.get("id")
            if not sub_id or sub_id in self._visited_categories:
                continue
            self._visited_categories.add(sub_id)

            slug = self._slugify(subcategory.get("fullURLPath") or subcategory.get("name") or sub_id)
            new_chain = category_chain + [
                {"id": sub_id, "name": subcategory.get("name"), "slug": slug}
            ]
            yield self._build_category_request(sub_id, slug, {"category_id": sub_id, "category_chain": new_chain})

        # Emit products from entities (first 50)
        entity_ids = set()
        for product in products.values():
            item = self._build_item(product, category_chain)
            if not item:
                continue
            pid = item["product_id"]
            entity_ids.add(pid)
            if pid not in self._emitted_product_ids:
                self._emitted_product_ids.add(pid)
                yield item

        # Fetch remaining products from productGroups via PUT
        if self._csrf_token:
            remaining_ids = []
            for group in result.get("productGroups", []):
                for pid in group.get("products", []):
                    if pid not in entity_ids and pid not in self._emitted_product_ids:
                        remaining_ids.append(pid)

            # Batch into chunks
            for i in range(0, len(remaining_ids), _BATCH_SIZE):
                batch = remaining_ids[i : i + _BATCH_SIZE]
                yield self._build_product_batch_request(batch, category_chain)

    def parse_product_batch(self, response: Response) -> Iterable[Request | ICAItem]:
        """Parse products returned by the PUT batch endpoint."""
        if response.status == 202:
            retries = response.meta.get("waf_retries", 0)
            if retries >= _MAX_WAF_RETRIES:
                self.logger.error("Max WAF retries for PUT batch; skipping %d products", len(response.meta.get("product_ids", [])))
                return
            self.logger.warning("PUT batch got 202 (WAF); refreshing (retry %d)", retries + 1)
            self._refresh_session()
            meta = response.meta
            yield self._build_product_batch_request(
                meta["product_ids"], meta["category_chain"],
            )
            return

        if response.status == 403:
            retries = response.meta.get("waf_retries", 0)
            if retries >= _MAX_WAF_RETRIES:
                self.logger.error("Max CSRF retries for PUT batch; skipping")
                return
            self.logger.warning("PUT batch got 403; refreshing CSRF (retry %d)", retries + 1)
            self._refresh_session()
            meta = response.meta
            yield self._build_product_batch_request(
                meta["product_ids"], meta["category_chain"],
            )
            return

        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError):
            self.logger.error("Failed to decode PUT response: %s", response.url)
            return

        category_chain = response.meta.get("category_chain", [])
        products = payload.get("products", [])

        for product in products:
            item = self._build_item(product, category_chain)
            if not item:
                continue
            pid = item["product_id"]
            if pid not in self._emitted_product_ids:
                self._emitted_product_ids.add(pid)
                yield item

    # ------------------------------------------------------------------
    # Item builder
    # ------------------------------------------------------------------

    def _build_item(self, product: dict, category_chain: List[Dict]) -> Optional[ICAItem]:
        product_id = product.get("productId")
        retailer_id = product.get("retailerProductId")
        name = product.get("name")

        if not product_id or not retailer_id or not name:
            return None

        category_path = product.get("categoryPath") or []
        top_category = category_path[0] if category_path else (category_chain[0]["name"] if category_chain else None)
        subcategory_name = category_path[1] if len(category_path) > 1 else (category_chain[-1]["name"] if category_chain else None)
        subcategory_slug = self._slugify(subcategory_name) if subcategory_name else None

        price_info = product.get("price") or {}
        price_amount = self._extract_price(price_info)
        unit_price_amount, unit_label = self._extract_unit_price(price_info, product)

        size_info = product.get("size") or {}

        return ICAItem(
            category=top_category,
            subcategory=subcategory_name,
            subcategory_slug=subcategory_slug,
            name=name,
            url=self._build_product_url(name, retailer_id),
            price=price_amount,
            unit_price=unit_price_amount,
            unit_quantity_name=unit_label,
            unit_quantity_abbrev=size_info.get("uom"),
            currency=self._extract_currency(price_info),
            quantity_type=product.get("packSizeDescription") or size_info.get("value"),
            nutrition=None,
            availability=product.get("available"),
            product_id=product_id,
            ean=product.get("ean"),
            promotions=product.get("offers") or [],
        )

    # ------------------------------------------------------------------
    # Session / WAF management
    # ------------------------------------------------------------------

    def _maybe_refresh_session(self) -> None:
        """Proactively refresh session if the WAF token is about to expire."""
        if not self._waf_token:
            self._refresh_session()
            return
        elapsed = time.monotonic() - self._token_obtained_at
        if elapsed > _WAF_TOKEN_TTL:
            self.logger.info("Proactive WAF refresh after %.0fs", elapsed)
            self._refresh_session()

    def _refresh_session(self) -> None:
        """Solve the WAF challenge and obtain CSRF token via Playwright."""
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except ImportError:
            self.logger.warning(
                "playwright not installed; cannot solve WAF challenge. "
                "Install with: pip install playwright && playwright install chromium"
            )
            return

        self.logger.info("Obtaining WAF token and CSRF token via Playwright")

        first_category = self.root_categories[0]
        category_url = (
            f"https://handlaprivatkund.ica.se/stores/{self.store_id}"
            f"/categories/{self._slugify(first_category.full_path)}/{first_category.identifier}"
        )

        def _run() -> Tuple[Optional[str], Optional[str], Dict[str, str]]:
            from playwright.sync_api import sync_playwright

            csrf = None

            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                context = browser.new_context(user_agent=_BROWSER_UA)
                page = context.new_page()

                def on_request(request):
                    nonlocal csrf
                    if "webproductpagews" in request.url and not csrf:
                        csrf = request.headers.get("x-csrf-token")

                page.on("request", on_request)

                # Navigate to a category page to trigger both WAF and product loading
                page.goto(category_url, wait_until="networkidle", timeout=30000)

                # Wait for WAF token
                waf_token = None
                for _ in range(20):
                    for cookie in context.cookies():
                        if cookie["name"] == "aws-waf-token":
                            waf_token = cookie["value"]
                            break
                    if waf_token:
                        break
                    page.wait_for_timeout(500)

                # Scroll to trigger PUT request (to capture CSRF)
                if not csrf:
                    page.wait_for_timeout(1000)
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(2000)

                session_cookies = {c["name"]: c["value"] for c in context.cookies() if c["name"] != "aws-waf-token"}
                browser.close()

            return waf_token, csrf, session_cookies

        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                waf_token, csrf, session_cookies = pool.submit(_run).result(timeout=60)

            self._waf_token = waf_token
            self._csrf_token = csrf
            self._session_cookies = session_cookies
            self._token_obtained_at = time.monotonic()

            if waf_token:
                self.logger.info("Obtained WAF token (%d chars)", len(waf_token))
            else:
                self.logger.warning("Failed to obtain WAF token")

            if csrf:
                self.logger.info("Obtained CSRF token: %s", csrf[:12] + "...")
            else:
                self.logger.warning("Failed to obtain CSRF token; PUT batching disabled")

        except Exception as exc:
            self.logger.error("Failed to refresh session: %s", exc)

    # ------------------------------------------------------------------
    # Price / field extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_price(price_info: dict) -> Optional[str]:
        if not price_info:
            return None
        # PUT endpoint: {"amount": "7.98", "currency": "SEK"}
        # GET endpoint: {"current": {"amount": "7.98", ...}}
        current = price_info.get("current")
        if isinstance(current, dict):
            return current.get("amount")
        return price_info.get("amount")

    @staticmethod
    def _extract_unit_price(price_info: dict, product: Optional[dict] = None) -> tuple[Optional[str], Optional[str]]:
        # GET endpoint: nested in price.unit.current
        unit_info = price_info.get("unit") if isinstance(price_info, dict) else None
        if isinstance(unit_info, dict):
            current = unit_info.get("current")
            amount = current.get("amount") if isinstance(current, dict) else unit_info.get("amount")
            label = unit_info.get("label")
            return amount, label
        # PUT endpoint: unitPrice is a top-level field on the product
        if product:
            up = product.get("unitPrice")
            if isinstance(up, dict):
                return up.get("amount"), up.get("label")
        return None, None

    @staticmethod
    def _extract_currency(price_info: dict) -> Optional[str]:
        if not isinstance(price_info, dict):
            return None
        current = price_info.get("current")
        if isinstance(current, dict):
            return current.get("currency")
        original = price_info.get("original")
        if isinstance(original, dict):
            return original.get("currency")
        return price_info.get("currency")

    def _build_product_url(self, name: str, retailer_id: str) -> str:
        slug = self._slugify(name)
        return (
            f"https://handlaprivatkund.ica.se/stores/{self.store_id}/products/{slug}/{retailer_id}"
        )

    def _request_headers(self, slug: str, category_id: str) -> Dict[str, str]:
        referer = (
            f"https://handlaprivatkund.ica.se/stores/{self.store_id}/categories/{slug}/{category_id}"
        )
        headers = self.custom_settings["DEFAULT_REQUEST_HEADERS"].copy()
        headers["Referer"] = referer
        return headers

    @staticmethod
    def _slugify(value: Optional[str]) -> str:
        if not value:
            return ""
        normalized = unicodedata.normalize("NFKD", value)
        ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
        sanitized = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value)
        sanitized = sanitized.strip("-")
        return sanitized.lower()
