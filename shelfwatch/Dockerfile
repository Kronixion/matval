FROM python:3.12-slim
WORKDIR /app

# Install matval_pipeline first (shared dependency)
COPY scrape_supermarket_websites/matval_pipeline/ /app/matval_pipeline/
RUN pip install --no-cache-dir /app/matval_pipeline/

# Install shelfwatch
COPY shelfwatch/ /app/shelfwatch/
RUN pip install --no-cache-dir /app/shelfwatch/

CMD ["shelfwatch"]
