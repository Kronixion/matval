# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html
# useful for handling different item types with a single interface

from scrapy import Item, Spider


class IcaScraperPipeline:
    def process_item(self, item: Item, spider: Spider):
        return item
