FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app

# Install matval_core (shared dependency)
COPY matval_core/ /app/matval_core/
RUN uv pip install --system --no-cache /app/matval_core/

# Install matval_pipeline (shared dependency)
COPY scrape_supermarket_websites/matval_pipeline/ /app/matval_pipeline/
ENV UV_NO_SOURCES=1
RUN uv pip install --system --no-cache /app/matval_pipeline/

# Install scraper dependencies (scrapy + beautifulsoup4 for ica)
RUN uv pip install --system --no-cache scrapy beautifulsoup4

# Install Playwright + Chromium for ICA's AWS WAF challenge
RUN uv pip install --system --no-cache playwright \
    && playwright install --with-deps chromium

# Copy all scraper projects
COPY scrape_supermarket_websites/coop/scraper/ /app/scrapers/coop/
COPY scrape_supermarket_websites/hemkop/scraper/ /app/scrapers/hemkop/
COPY scrape_supermarket_websites/ica/scraper/ /app/scrapers/ica/
COPY scrape_supermarket_websites/mathem/scraper/ /app/scrapers/mathem/
COPY scrape_supermarket_websites/willys/scraper/ /app/scrapers/willys/

# Entrypoint script that cd's into the right scraper dir and runs scrapy
COPY scrape_supermarket_websites/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
