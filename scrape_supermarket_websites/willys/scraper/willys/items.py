# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class WillysItem(scrapy.Item):
    """Structured representation of a product scraped from Willys."""

    category = scrapy.Field()
    subcategory = scrapy.Field()
    subcategory_slug = scrapy.Field()
    name = scrapy.Field()
    url = scrapy.Field()
    price = scrapy.Field()
    unit_price = scrapy.Field()
    unit_quantity_name = scrapy.Field()
    unit_quantity_abbrev = scrapy.Field()
    currency = scrapy.Field()
    quantity_type = scrapy.Field()
    nutrition = scrapy.Field()
    availability = scrapy.Field()
