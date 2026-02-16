# Matval

Matval (_mat_ = food, _val_ = choice) scrapes product data from five Swedish supermarket websites and stores it in PostgreSQL. An MCP server called **Shelfwatch** exposes the data to AI assistants so you can ask natural-language questions like _"which yogurt has the most protein?"_, _"is sourdough bread available at ICA?"_, _"show me all plant-based milk options"_, or _"compare prices for chicken breast across stores"_.

## Motivation

I love cooking. For years my grocery routine was simple walk into the store, browse the aisles, fill the basket. Then I discovered online grocery shopping and something clicked. For the first time I could see every product a supermarket carried laid out on a screen, with prices, unit costs, and nutrition all in one place. But I also noticed a gap: every chain had its own website, its own layout, its own way of organising things. There was no single place to search across all of them, compare products side by side, or answer questions like _"which store has the highest-protein Greek yogurt?"_ or _"is that specialty ingredient actually in stock anywhere?"_

So I built **Matval** Swedish for _food choice_ to fill that gap. Five scrapers pull product data from Coop, Hemkop, ICA, Mathem, and Willys into a shared PostgreSQL database. On top of that sits **Shelfwatch**, an MCP server that lets any AI assistant query the data conversationally. I can ask it to find high-protein breakfast options, check which stores have a specific ingredient in stock, browse entire product categories I've never explored, plan meals around nutritional goals, or compare prices across stores. What used to take half an hour of tabbing between websites now takes a single question and it has genuinely changed how I shop, cook, and eat.

## Architecture

```
┌────────────┐  ┌────────────┐  ┌────────────┐
│  Coop      │  │  Hemkop    │  │  ICA       │  ...
│  Scraper   │  │  Scraper   │  │  Scraper   │
└─────┬──────┘  └─────┬──────┘  └─────┬──────┘
      │               │               │
      └───────────┬───┴───────────────┘
                  │  matval_pipeline
                  ▼
           ┌─────────────┐
           │  PostgreSQL │
           │     16      │
           └──────┬──────┘
                  │
           ┌──────┴──────┐
           │  Shelfwatch │
           │  MCP Server │
           └──────┬──────┘
                  │ Streamable HTTP
                  ▼
           ┌─────────────┐
           │  MCP Client │
           │  (Claude,   │
           │   Cursor...)│
           └─────────────┘
```

| Component | Description |
|-----------|-------------|
| **Scrapers** | Five independent Scrapy spiders — one per supermarket chain |
| **matval_pipeline** | Shared library that normalises items and upserts them into PostgreSQL |
| **PostgreSQL** | Stores products, categories, nutrition (JSONB), availability status, prices, unit pricing, and historical changes |
| **Shelfwatch** | MCP server with domain-specific tools for searching products, browsing categories, comparing nutrition and prices, checking availability |

## Quickstart

### Prerequisites

- Docker and Docker Compose
- Git

### 1. Clone and configure

```bash
git clone <repo-url> matval && cd matval
cp .env.example .env
# Edit .env — at minimum set POSTGRES_PASSWORD
```

### 2. Start the stack

```bash
docker compose up -d
```

This starts **PostgreSQL** (with automatic schema + seed migration) and **Shelfwatch**. Verify:

```bash
docker compose logs shelfwatch
# Should show: "StreamableHTTP session manager started"
#              "Uvicorn running on http://0.0.0.0:8000"
```

### 3. Run a scraper

Scrapers are behind a Docker Compose profile and only run on demand:

```bash
docker compose run --rm scraper coop
docker compose run --rm scraper ica
```

Available stores: `coop`, `hemkop`, `ica`, `mathem`, `willys`.

You can pass extra Scrapy flags after the store name:

```bash
docker compose run --rm scraper willys --loglevel=DEBUG
```

### 4. Connect an MCP client

Point your MCP client at the Shelfwatch server. Example config for Claude Desktop or similar:

```json
{
  "mcpServers": {
    "shelfwatch": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

## Configuration

All configuration is via environment variables in `.env`. Docker Compose passes them to every service, with host overrides for internal networking.

### PostgreSQL

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `postgres` | Database user |
| `POSTGRES_PASSWORD` | — | Database password (required) |
| `POSTGRES_DB` | `supermarket_items` | Database name |
| `POSTGRES_HOST` | `localhost` | Host (overridden to `postgres` inside Docker) |
| `POSTGRES_PORT` | `5432` | Port (host-side mapping) |

### Shelfwatch MCP Server

| Variable | Default | Description |
|----------|---------|-------------|
| `SHELFWATCH_MCP_TRANSPORT` | `stdio` | Transport protocol (`streamable-http`, `sse`, `stdio`) |
| `SHELFWATCH_MCP_HOST` | — | Bind address (`0.0.0.0` for network access) |
| `SHELFWATCH_MCP_PORT` | — | Listen port |
| `SHELFWATCH_DB_HOST` | `localhost` | Database host (overridden to `postgres` inside Docker) |
| `SHELFWATCH_DB_PORT` | `5432` | Database port |
| `SHELFWATCH_DB_NAME` | `supermarket_items` | Database name |
| `SHELFWATCH_DB_USER` | `postgres` | Database user |
| `SHELFWATCH_DB_PASSWORD` | — | Database password |
| `SHELFWATCH_DB_AUTOCOMMIT` | `true` | Use autocommit mode |
| `SHELFWATCH_DB_OPTIONS` | — | Extra libpq connection options |
| `SHELFWATCH_LOG_LEVEL` | `INFO` | Logging level |

## MCP Tools

Shelfwatch exposes nine tools:

| Tool | Description |
|------|-------------|
| `search_products` | Keyword search across all or a specific store |
| `get_categories` | List categories with product counts |
| `get_products_in_category` | Browse products within a category |
| `get_product_details` | Full product info — nutrition, availability, price, unit pricing |
| `get_nutrition` | Nutrition data (JSONB) for a product |
| `list_stores` | All stores with product counts and data freshness |
| `compare_prices` | Side-by-side price comparison for a product across stores |
| `get_cheapest` | Find the lowest-priced items matching a keyword |
| `execute_query` | Raw SQL escape hatch for advanced queries |

## Examples

Ask Shelfwatch natural-language questions through your MCP client:

### Nutrition & Product Discovery
- _"Which brands of Greek yogurt have the most protein per 100g?"_
- _"Show me all gluten-free bread options across all stores"_
- _"Compare the fiber content of different breakfast cereals"_
- _"What plant-based protein sources are available at ICA?"_

### Availability & Stock
- _"Is Risifrutti rice pudding in stock at Coop?"_
- _"Which stores currently have sourdough bread available?"_
- _"Show me all out-of-stock items at Willys"_

### Category Browsing
- _"What categories of products does Hemkop carry?"_
- _"Show me everything in the 'Drycker' (beverages) category"_
- _"List all cheese products at Mathem"_

### Price Comparison
- _"Where is oat milk cheapest?"_
- _"Compare chicken breast prices across all five stores"_
- _"Find the best value per kg for coffee beans"_

### Meal Planning & Combined Queries
- _"Find high-protein, low-sugar breakfast options under 30 kr"_
- _"What are the cheapest sources of vitamin C?"_
- _"Plan a week of vegetarian dinners using in-stock items at ICA"_

## Database Schema

The database is initialised automatically on first `docker compose up` via init scripts in `db/`.

Core tables:

- **stores** — the five supermarket chains (seeded automatically)
- **categories** — hierarchical product categories (self-referencing `parent_category_id`)
- **products** — canonical products linked to a category
- **store_products** — per-store pricing, unit pricing, URLs, nutrition (JSONB), and availability
- **product_availability_history** — price/availability change log

Lookup tables: `units`, `quantity_types`, `availability_statuses`, `currencies`.

## Project Structure

```
matval/
├── .env.example                 # Environment template
├── docker-compose.yml           # PostgreSQL + Shelfwatch + Scraper services
├── .dockerignore
├── db/
│   ├── schema.sql               # Full database schema
│   └── 02-seed-stores.sql       # Pre-seed the 5 stores
├── shelfwatch/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── client-config.json       # Example MCP client config
│   └── src/shelfwatch/
│       └── server.py            # MCP server implementation
└── scrape_supermarket_websites/
    ├── Dockerfile
    ├── entrypoint.sh            # Store-selector entrypoint
    ├── matval_pipeline/         # Shared Scrapy pipeline library
    │   └── matval_pipeline/
    │       ├── pipeline.py      # Scrapy ItemPipeline (normalise + upsert)
    │       ├── connector.py     # PostgresConnector
    │       ├── db_ops.py        # DB operations (get-or-create, upsert)
    │       ├── normalizers.py   # Price/currency/availability normalisers
    │       └── config.py        # Store IDs and pipeline config
    ├── coop/scraper/
    ├── hemkop/scraper/
    ├── ica/scraper/
    ├── mathem/scraper/
    └── willys/scraper/
```

## robots.txt Compliance

All five scrapers respect the `robots.txt` rules published by each supermarket.

| Store | Disallow rules | Crawl-delay | Visit-time | Notes |
|-------|---------------|-------------|------------|-------|
| **Coop** | `/mitt-coop`, `/handla/sok/*`, `/handla/search*`, etc. | — | — | API lives on `external.api.coop.se`; no restricted paths are hit |
| **Hemkop** | `/kassa/`, `/*?sort=`, `/*?q=`, etc. | 10 s | 04:00–08:45 UTC | Listing URLs put `sort` after other params (`&sort=`) so the `/*?sort=` rule does not match |
| **ICA** | `/templates/ajaxresponse.aspx` | — | — | Spider targets `handlaprivatkund.ica.se`, a separate host from `www.ica.se` |
| **Mathem** | `/*/?*filter_*`, cart/login paths | — | — | No restricted paths are hit |
| **Willys** | `/sok`, `/kassa/`, etc. | 10 s | 04:00–08:45 UTC | No restricted paths are hit |

**Crawl-delay** — Hemkop and Willys specify a 10-second crawl delay. Both spiders enforce this via `CONCURRENT_REQUESTS = 1` and `DOWNLOAD_DELAY = 10`.

**Visit-time** — Hemkop and Willys restrict crawling to 04:00–08:45 UTC. Scrapy has no built-in support for this, so you must schedule runs externally (e.g. cron):

```cron
# Run Hemkop and Willys scrapers at 04:00 UTC daily
0 4 * * * docker compose run --rm scraper hemkop
0 4 * * * docker compose run --rm scraper willys
```

## Local Development (without Docker)

If you prefer running outside Docker (e.g. for spider development):

```bash
# Start only postgres
docker compose up -d postgres

# Install the shared pipeline in a scraper's venv
cd scrape_supermarket_websites/mathem
python -m venv venv && source venv/bin/activate
pip install -e ../matval_pipeline
pip install scrapy

# Run the spider
cd scraper
scrapy crawl mathem
```

The scrapers read `POSTGRES_HOST=localhost` from `.env` by default, which works when postgres is exposed on the host.

## Maintenance

The scrapers depend on each supermarket's internal APIs and frontend structure, both of which can change without notice. I aim to review and update the spiders **every three months** to keep them working. Typical breakage includes renamed API endpoints, changed JSON response shapes, rotated category slugs, and new anti-bot measures.

## Store-Agnostic Design

While currently implemented for 5 Swedish supermarkets, **Matval is designed to be store-agnostic**. The shared `matval_pipeline` library provides a normalized data model that can accommodate stores from any country.

To add a new store:
1. Create a new Scrapy spider in `scrape_supermarket_websites/<store_name>/scraper/`
2. Configure it to use `matval_pipeline.pipeline.PostgresPipeline`
3. Set `STORE_NAME` in the spider's settings
4. Run the scraper - the shared pipeline handles normalization and database operations

No changes needed to the database schema or MCP server.

## Planned Improvements

### Optimize Product Retrieval
**Problem:** Current tool design requires multiple MCP calls for complex queries, consuming tokens and adding latency.

**Solution:** Add batch retrieval tools:
- `batch_get_product_details(product_ids: list[int])` - Get multiple products in one call
- `search_products_with_details(keyword, include_nutrition=True)` - Include full details in search results

**Benefits:** Fewer API round-trips, lower token consumption, faster responses.

### GUI for Non-Technical Users
**Goal:** Make Matval accessible to anyone who wants to compare groceries, without requiring Docker/CLI knowledge.

**Approach:** Web-based interface with chat UI, handles MCP server connection internally. Could be hosted or distributed as a simple installer.

### Historical Price Tracking
**Current state:** The database already tracks price/availability changes in `product_availability_history`.

**Feature:** Expose this via:
- MCP tool: `get_price_history(product_name, store_name, days=30)`
- Visualizations showing price trends over time
- Price drop alerts

### Recipe Suggestions
Given cuisine or meal type, suggest recipes using currently cheap/available ingredients. Requires integration with recipe APIs (Edamam, Spoonacular).

### Allergen Filtering
Normalize allergen data across stores and add filtering:
- `search_products(exclude_allergens=["gluten", "dairy"])`
- `find_allergen_free_alternatives(product_name, allergens=["nuts"])`

### Automatic Ingredient Shopping
**Challenge:** Swedish supermarkets don't provide public ordering APIs. Would require browser automation (Playwright/Selenium), which has legal/ToS concerns and detection risks.

**Near-term:** Export shopping lists with product URLs. Users manually add to cart.

**Long-term:** Explore automation if feasible, or seek partnerships for API access.
