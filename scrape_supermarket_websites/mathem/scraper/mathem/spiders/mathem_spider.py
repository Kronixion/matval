"""Spider for harvesting product listings and nutrition data from Mathem."""

from __future__ import annotations

import json
import re
from typing import Dict, Iterable, Iterator, List, Optional, Set, Tuple

import scrapy
from scrapy.http import JsonRequest, Response
from urllib.parse import urljoin

from mathem.items import MathemItem


class MathemSpider(scrapy.Spider):
    """Scrapes the Mathem grocery catalogue across categories and subcategories."""

    name = "mathem"
    allowed_domains = ["mathem.se"]
    start_urls = ["https://www.mathem.se/se/products/"]

    custom_settings = {
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1.0,
        "AUTOTHROTTLE_MAX_DELAY": 10.0,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5,
    }

    def __init__(self, *args, **kwargs):
        """Initialises the spider with bookkeeping for queued subcategories."""

        super().__init__(*args, **kwargs)
        self._queued_subcategories: Set[Tuple[str, str]] = set()

    def parse(self, response: Response) -> Iterator[scrapy.Request]:
        """Seed requests for every top-level category.

        Args:
            response: HTTP response for the Mathem landing page.

        Yields:
            Requests targeting each detected category JSON endpoint.
        """

        build_data = json.loads(response.css("script#__NEXT_DATA__::text").get())
        build_id = build_data["buildId"]

        categories = list(self._extract_category_slugs(response))
        if not categories:
            self.logger.warning("No categories discovered; using fallback list")
            categories = self._default_category_slugs()

        for slug in categories:
            url = f"https://www.mathem.se/_next/data/{build_id}/se/categories/{slug}.json"
            yield JsonRequest(
                url,
                callback=self.parse_category,
                cb_kwargs={"build_id": build_id, "category_slug": slug},
            )

    def parse_category(
        self,
        response: Response,
        build_id: str,
        category_slug: str,
        subcategory_slug: Optional[str] = None,
        subcategory_name: Optional[str] = None,
    ) -> Iterator[scrapy.Request]:
        """Process category JSON and schedule follow-up requests.

        Args:
            response: Response containing category or subcategory JSON payload.
            build_id: Next.js build identifier extracted from the homepage.
            category_slug: Slug of the top-level category being crawled.
            subcategory_slug: Slug of the current subcategory, if any.
            subcategory_name: Human-readable name of the subcategory, if known.

        Yields:
            Requests for subcategory discovery, pagination, or product detail pages.
        """

        payload = response.json()
        queries = payload.get("pageProps", {}).get("dehydratedState", {}).get("queries", [])
        if not queries:
            self.logger.warning("Missing queries for %s", response.url)
            return

        data = queries[0].get("state", {}).get("data", {})

        if subcategory_slug is None:
            yield from self._discover_subcategories(response.url, data, build_id, category_slug)
            return

        # Handle subcategory content
        yield from self._extract_subcategory_products(
            response,
            data,
            build_id,
            category_slug,
            subcategory_slug,
            subcategory_name,
        )

    def parse_product(self, response: Response, meta: Dict[str, dict]):
        """Combine category data with detailed nutrition information.

        Args:
            response: Response containing a product detail JSON payload.
            meta: Metadata carrying category, subcategory, and base product info.

        Yields:
            Populated :class:`MathemItem` instances.
        """

        base_product = meta["base_info"]
        detail = (
            response.json()
            .get("pageProps", {})
            .get("dehydratedState", {})
            .get("queries", [{}])[0]
            .get("state", {})
            .get("data", {})
        )

        nutrition = self._extract_nutrition(detail)
        detailed_info = detail.get("detailedInfo", {}) if isinstance(detail, dict) else {}

        yield MathemItem(
            category=meta["category"],
            subcategory=meta.get("subcategory_name"),
            subcategory_slug=meta.get("subcategory"),
            name=base_product.get("fullName"),
            url=urljoin("https://www.mathem.se", base_product.get("absoluteUrl", "")),
            price=base_product.get("grossPrice"),
            unit_price=base_product.get("grossUnitPrice"),
            unit_quantity_name=base_product.get("unitPriceQuantityName"),
            unit_quantity_abbrev=base_product.get("unitPriceQuantityAbbreviation"),
            currency=base_product.get("currency"),
            quantity_type=detailed_info.get("quantity"),
            nutrition=nutrition,
            availability=base_product.get("availability"),
        )

    def _discover_subcategories(
        self,
        request_url: str,
        data: dict,
        build_id: str,
        category_slug: str,
    ) -> Iterator[scrapy.Request]:
        """Identify and queue every subcategory belonging to a category.

        Args:
            request_url: URL of the current category JSON resource.
            data: Parsed JSON object describing the category contents.
            build_id: Next.js build identifier required for JSON endpoints.
            category_slug: Slug of the top-level category currently processed.

        Yields:
            Requests targeting each discovered subcategory JSON resource.
        """

        discovered: Dict[str, str] = {}

        for block in data.get("blocks", []):
            if block.get("component") == "page-header":
                for chip_group in block.get("chipGroups", []):
                    for chip in chip_group.get("chips", []):
                        uri = chip.get("target", {}).get("uri")
                        title = chip.get("title")
                        slug, name = self._normalize_subcategory(category_slug, uri, title)
                        if slug and uri:
                            discovered[uri] = name

        for section in data.get("sections", []):
            uri = section.get("uri")
            title = section.get("title")
            slug, name = self._normalize_subcategory(category_slug, uri, title)
            if slug and uri:
                discovered[uri] = name

        for page_entry in data.get("pages", []):
            for section in page_entry.get("sections", []):
                uri = section.get("uri")
                title = section.get("title")
                slug, name = self._normalize_subcategory(category_slug, uri, title)
                if slug and uri:
                    discovered[uri] = name

        for uri, name in discovered.items():
            queue_key = (category_slug, uri)
            if queue_key in self._queued_subcategories:
                continue
            self._queued_subcategories.add(queue_key)
            json_url = self._build_json_url(build_id, uri)
            slug, _ = self._normalize_subcategory(category_slug, uri, name)
            yield JsonRequest(
                json_url,
                callback=self.parse_category,
                cb_kwargs={
                    "build_id": build_id,
                    "category_slug": category_slug,
                    "subcategory_slug": slug,
                    "subcategory_name": name,
                },
            )

    def _extract_subcategory_products(
        self,
        response: Response,
        data: dict,
        build_id: str,
        category_slug: str,
        subcategory_slug: str,
        subcategory_name: Optional[str],
    ) -> Iterator[scrapy.Request]:
        """Yield product detail requests for a subcategory, including pagination.

        Args:
            response: Response that produced the subcategory payload.
            data: Parsed JSON block representing the subcategory contents.
            build_id: Next.js build identifier.
            category_slug: Parent category slug.
            subcategory_slug: Active subcategory slug.
            subcategory_name: Human-readable subcategory name.

        Yields:
            Requests for subsequent cursors or product detail endpoints.
        """
        pages = data.get("pages")
        if pages:
            for page_entry in pages:
                page_subcategory_name = page_entry.get("title") or subcategory_name
                for item in page_entry.get("items", []):
                    if item.get("type") == "product":
                        product = item.get("attributes", {})
                        yield from self._schedule_product(
                            build_id,
                            category_slug,
                            product,
                            subcategory_slug,
                            page_subcategory_name,
                        )

                if page_entry.get("hasMore") and page_entry.get("nextCursor"):
                    yield from self._schedule_cursor_request(
                        response.url,
                        build_id,
                        category_slug,
                        subcategory_slug,
                        page_subcategory_name,
                        page_entry["nextCursor"],
                    )
            return

        blocks = data.get("blocks")
        if blocks:
            yield from self._parse_legacy_blocks(
                blocks,
                build_id,
                category_slug,
                subcategory_slug,
                subcategory_name,
            )
            return

        # Fallback to sections if items are nested further
        for section in data.get("sections", []):
            uri = section.get("uri")
            title = section.get("title")
            slug, name = self._normalize_subcategory(category_slug, uri, title)
            if slug and uri:
                queue_key = (category_slug, uri)
                if queue_key in self._queued_subcategories:
                    continue
                self._queued_subcategories.add(queue_key)
                json_url = self._build_json_url(build_id, uri)
                yield JsonRequest(
                    json_url,
                    callback=self.parse_category,
                    cb_kwargs={
                        "build_id": build_id,
                        "category_slug": category_slug,
                        "subcategory_slug": slug,
                        "subcategory_name": name,
                    },
                )

    def _parse_legacy_blocks(
        self,
        blocks: List[dict],
        build_id: str,
        category_slug: str,
        subcategory_slug: Optional[str],
        subcategory_name: Optional[str],
    ) -> Iterator[scrapy.Request]:
        """Handle legacy page structures that expose product grids directly.

        Args:
            blocks: List of content blocks within the category JSON.
            build_id: Next.js build identifier.
            category_slug: Parent category slug.
            subcategory_slug: Current subcategory slug, if any.
            subcategory_name: Current subcategory name, if any.

        Yields:
            Requests for further pagination or products.
        """
        for block in blocks:
            component = block.get("component")

            if component == "product-grid":
                grid_title = block.get("title")
                current_subcategory = grid_title or subcategory_name
                for product in block.get("products", []):
                    yield from self._schedule_product(
                        build_id,
                        category_slug,
                        product,
                        subcategory_slug,
                        current_subcategory,
                    )

                button = block.get("button")
                next_uri = button.get("target", {}).get("uri") if button else None
                if next_uri:
                    json_url = self._build_json_url(build_id, next_uri)
                    yield JsonRequest(
                        json_url,
                        callback=self.parse_category,
                        cb_kwargs={
                            "build_id": build_id,
                            "category_slug": category_slug,
                            "subcategory_slug": subcategory_slug,
                            "subcategory_name": current_subcategory,
                        },
                    )

    def _schedule_product(
        self,
        build_id: str,
        category_slug: str,
        product: Optional[dict],
        subcategory_slug: Optional[str],
        subcategory_name: Optional[str],
    ) -> Iterator[scrapy.Request]:
        """Generate a request for a product detail page.

        Args:
            build_id: Next.js build identifier.
            category_slug: Parent category slug.
            product: Product metadata extracted from a grid or section.
            subcategory_slug: Subcategory slug associated with the product.
            subcategory_name: Human-readable subcategory name associated with the product.

        Yields:
            A single :class:`JsonRequest` targeting the product detail JSON.
        """
        if not product:
            return

        detail_slug = product.get("absoluteUrl", "").strip("/").split("/")[-1]
        if not detail_slug:
            return

        detail_url = f"https://www.mathem.se/_next/data/{build_id}/se/products/{detail_slug}.json"
        meta = {
            "category": category_slug,
            "base_info": product,
            "subcategory": subcategory_slug,
            "subcategory_name": subcategory_name,
        }
        yield JsonRequest(detail_url, callback=self.parse_product, cb_kwargs={"meta": meta})

    def _build_json_url(self, build_id: str, uri: str) -> str:
        """Convert a storefront URI into its `_next/data` JSON equivalent.

        Args:
            build_id: Next.js build identifier.
            uri: Storefront URI (e.g. ``/se/categories/...``).

        Returns:
            Fully qualified URL pointing to the JSON representation of ``uri``.
        """
        path = uri.split("?")[0]
        query = uri.partition("?")[2]
        json_url = f"https://www.mathem.se/_next/data/{build_id}{path}.json"
        if query:
            json_url = f"{json_url}?{query}"
        return json_url

    def _schedule_cursor_request(
        self,
        current_url: str,
        build_id: str,
        category_slug: str,
        subcategory_slug: Optional[str],
        subcategory_name: Optional[str],
        cursor: str,
    ) -> Iterator[scrapy.Request]:
        """Queue the next paginated request for a subcategory listing.

        Args:
            current_url: URL of the current page request.
            build_id: Next.js build identifier.
            category_slug: Parent category slug.
            subcategory_slug: Subcategory slug being paginated.
            subcategory_name: Human-readable name for the subcategory.
            cursor: Pagination cursor supplied by Mathem.

        Yields:
            A single :class:`JsonRequest` for the next cursor value.
        """
        base, sep, existing_query = current_url.partition("?")
        if existing_query:
            params = existing_query.split("&")
            params = [p for p in params if not p.startswith("cursor=")]
            params.append(f"cursor={cursor}")
            next_url = f"{base}?{'&'.join(params)}"
        else:
            next_url = f"{base}?cursor={cursor}"

        yield JsonRequest(
            next_url,
            callback=self.parse_category,
            cb_kwargs={
                "build_id": build_id,
                "category_slug": category_slug,
                "subcategory_slug": subcategory_slug,
                "subcategory_name": subcategory_name,
            },
        )

    def _normalize_subcategory(
        self,
        category_slug: str,
        uri: Optional[str],
        title: Optional[str],
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extract a usable slug and name from a subcategory URI.

        Args:
            category_slug: Parent category slug.
            uri: Subcategory URI as presented on the storefront.
            title: Display title associated with the subcategory.

        Returns:
            Tuple of ``(slug, name)`` or ``(None, None)`` if the URI should be
            ignored.
        """
        if not uri or not uri.startswith("/se/categories/"):
            return None, None

        path, _, query = uri.partition("?")
        stripped = path[len("/se/categories/") :].strip("/")
        if not stripped or stripped == category_slug:
            return None, None

        if stripped.startswith(f"{category_slug}/"):
            relative = stripped[len(category_slug) + 1 :]
        else:
            relative = stripped

        name = title or relative
        return relative, name

    def _extract_nutrition(self, detail: dict) -> Dict[str, str]:
        if not isinstance(detail, dict):
            return {}

        # Some products expose nutritionFacts directly
        nutrition = detail.get("nutritionFacts")
        if nutrition:
            return nutrition

        detailed_info = detail.get("detailedInfo", {})
        local_sections = detailed_info.get("local") if isinstance(detailed_info, dict) else None
        if isinstance(local_sections, list):
            for section in local_sections:
                table = section.get("nutritionInfoTable")
                if not table:
                    continue
                rows = table.get("rows", [])
                if rows:
                    return {row.get("key"): row.get("value") for row in rows if row.get("key")}

        return {}

    def _extract_category_slugs(self, response) -> Iterable[str]:
        """Pull category slugs from links in the products page HTML."""

        seen: set[str] = set()
        for match in re.finditer(r'/se/categories/(\d+-[a-z0-9-]+)/?(?=["\s?])', response.text):
            slug = match.group(1)
            if "/" not in slug and slug not in seen:
                seen.add(slug)
                yield slug

    @staticmethod
    def _default_category_slugs() -> List[str]:
        return [
            "1-frukt-gront",
            "78-mejeri-ost-juice",
            "155-brod-bageri",
            "199-kott-chark-fagel",
            "264-dryck",
            "329-skafferi",
            "420-fisk-skaldjur",
            "466-hem-hushall",
            "575-fardigmat-mellanmal",
            "630-glass-godis-snacks",
            "663-barn-baby",
            "693-apotek-skonhet-halsa",
            "783-kryddor-smaksattare",
            "872-djurmat-tillbehor",
            "892-kiosk-tidningar",
            "1070-enklare-smabarnsliv",
            "1109-blommor-plantering",
            "1197-lokala-favoriter",
            "1231-var-delikatessdisk",
            "1233-vardagshjaltar",
            "1259-fryst",
            "1342-traning",
        ]
