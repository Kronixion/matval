# Matval

## Description

I've built this project to order myself food. The process of thinking what recipes to eat and finding all the necessary ingredients for those recipes is an exhausting one (for me). As I do have a passion for cooking and since I've been doing automations for a long time I thought that I could make it more efficient and reduce this process from several hours (~4) each week to roughly 30 minutes. I like to spend time cooking or building some other fun stuff rather than looking up recipes and ingredients.

If someone is reading this and you think that this can help you, then this project is for you.

## Supported Supermarkets

As I am living in Sweden currently, I've targeted the five main supermarkets:
- Ica
- Coop
- Willys
- Hemkop
- Mathem

Additional supermarkets might be added.

## Project Functionalities

- Generate a weekly meal plan based on nutritional requirements and personal preferences
- Compare prices for the same product across supermarkets to find the best deal
- Track historical prices to spot trends and time purchases
- Look up nutritional values for products
- Search the full product catalogue across all supported supermarkets
- Find the cheapest available option for any ingredient
- Browse products by category
- Automatically scrape and refresh product data on a weekly schedule (This is an additional setup, but feasible)

## Project Limitations

- Adding items to a supermarket cart is not supported. The robots.txt of the supported supermarkets disallows automating the cart, and this boundary is respected. This is unless we can do it through a browser extension which will act as a human (to be fair I don't know if their infrastructure will hold to a huge magnitude of requests if multiple people were to do this)
- No user interface yet. The project currently operates through Claude/GPT/etc. via the MCP server, which requires API access. A standalone UI is planned for the future.
- Supermarket websites update periodically, which can change API endpoints, page structure, or URL formats. This may require scraper maintenance after such changes.
- The scrapers have no automated tests against live endpoints, so a breaking change in a website may go unnoticed until the next scheduled scrape run produces no data.
- Product deduplication is based on name and category, which means products with identical names but different variants (e.g. different sizes) may interfere with each other's price data until a scraper provides a unique external product ID.
- Data freshness depends on the scrape schedule. Prices are only as current as the last successful run.

## Quick start

This is how you can try out the project (please do) and I would recommend running the mathem scraper, it's one of my favorite supermarkets.

### Bash (Linux / macOS)

```bash
cp .env.example .env
# Edit .env with your database credentials
# Provide a password to POSTGRES_PASSWORD

# Start PostgreSQL and the shelfwatch MCP server
docker compose up postgres shelfwatch

# Run a scraper (replace <store> with coop, hemkop, ica, mathem, or willys)
docker compose --profile scrape run --rm scraper <store>
```

### Windows (PowerShell)

```powershell
Copy-Item .env.example .env
# Edit .env with your database credentials
# Provide a password to POSTGRES_PASSWORD

# Start PostgreSQL and the shelfwatch MCP server
docker compose up postgres shelfwatch

# Run a scraper (replace <store> with coop, hemkop, ica, mathem, or willys)
docker compose --profile scrape run --rm scraper <store>
```

### Scheduling with cron (Linux / macOS)

The recommended setup runs each scraper once a week, staggered by one hour:

```cron
0 1 * * 1 cd /path/to/matval && docker compose --profile scrape run --rm scraper mathem >> /var/log/matval/mathem.log 2>&1
0 2 * * 1 cd /path/to/matval && docker compose --profile scrape run --rm scraper coop    >> /var/log/matval/coop.log    2>&1
0 3 * * 1 cd /path/to/matval && docker compose --profile scrape run --rm scraper ica     >> /var/log/matval/ica.log     2>&1
0 4 * * 1 cd /path/to/matval && docker compose --profile scrape run --rm scraper willys  >> /var/log/matval/willys.log  2>&1
0 4 * * 1 cd /path/to/matval && docker compose --profile scrape run --rm scraper hemkop  >> /var/log/matval/hemkop.log  2>&1
```

**robots.txt compliance:** Willys and Hemkop both specify `Crawl-delay: 10` and `Visit-time: 0400-0845 UTC` in their robots.txt. Their scrapers enforce the crawl delay via `DOWNLOAD_DELAY = 10` and `CONCURRENT_REQUESTS = 1`. The cron entries above schedule both scrapers to start within the allowed visit window (04:00-08:45 UTC).

### Scheduling with Task Scheduler (Windows - planned in the future)

---

## What data is collected

Every scraper collects the following for each product:

- **Name** - the product name as shown on the supermarket website
- **Category and subcategory** - where the product sits in the store's catalogue
- **Price** - current selling price
- **Unit price** - price per kg, litre, or other comparable unit (e.g. 12.50 kr/kg)
- **Currency** - always SEK for the supported supermarkets
- **Quantity / package size** - e.g. "500 g", "1 L", "6-pack"
- **Availability** - whether the product is currently in stock
- **Product URL** - direct link to the product page
- **Product ID** - the supermarket's internal SKU, used to track variants and avoid duplicates
- **Nutrition** - per-100g breakdown including energy, fat, carbohydrates, protein, salt, and fibre where available

Coop additionally provides:

- **EAN barcode** - useful for cross-referencing products between stores
- **Promotions** - active discounts or member offers

Price and availability changes are recorded automatically in a history table every time the scraper runs, so you can track how prices move over time without any extra configuration.

---

## Development

### Install dependencies

```bash
uv sync
```

### Run tests

```bash
pytest tests/
```

Tests use [testcontainers](https://testcontainers.com/) to spin up a real PostgreSQL instance, so Docker must be running.

### Code quality

```bash
uv run ruff check .
uv run ruff format .
uv run mypy .
```

Pre-commit hooks enforce these checks automatically. Install them with:

```bash
uv run pre-commit install
```
