import os
import asyncio
from dotenv import load_dotenv
import motor.motor_asyncio
import redis.asyncio as aioredis
from scraper.db.repository import Repository
from scraper.models.item import Item
from scraper.models.price import Price
from scraper.queue.redis_client import RedisClient
from scraper.parsers.steam import SteamParser

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB  = os.getenv("MONGO_DB", "skin_market")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

async def check_connections():
    parser = SteamParser()

    print("Szukam przedmiotów...")
    items = await parser.search_items("AK-47 Redline", count=3)
    for item in items:
        print(f"  - {item['name']} | wear: {item['wear']}")

    print("\nPobieram oferty...")
    listings = await parser.fetch_listings("AK-47 | Redline (Field-Tested)")
    for l in listings[:3]:
        print(f"  - ${l['price']} | wear: {l['wear']}")


if __name__ == "__main__":
    asyncio.run(check_connections())