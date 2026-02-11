#!/bin/bash
set -e

STORE="$1"
shift

if [ -z "$STORE" ]; then
    echo "Usage: docker compose run scraper <store> [scrapy args...]"
    echo "Stores: coop, hemkop, ica, mathem, willys"
    exit 1
fi

if [ ! -d "/app/scrapers/$STORE" ]; then
    echo "Error: Unknown store '$STORE'"
    exit 1
fi

cd "/app/scrapers/$STORE"
exec scrapy crawl "$STORE" "$@"
