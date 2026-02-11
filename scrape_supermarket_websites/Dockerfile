FROM python:3.12-slim
WORKDIR /app

# Install matval_pipeline (shared dependency)
COPY scrape_supermarket_websites/matval_pipeline/ /app/matval_pipeline/
RUN pip install --no-cache-dir /app/matval_pipeline/

# Install scraper dependencies (scrapy + beautifulsoup4 for ica)
RUN pip install --no-cache-dir scrapy beautifulsoup4

# Install Playwright + Chromium for ICA's AWS WAF challenge
RUN pip install --no-cache-dir playwright \
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
