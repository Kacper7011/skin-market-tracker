import os
import asyncio
from dotenv import load_dotenv
import motor.motor_asyncio
import redis.asyncio as aioredis
from scraper.db.repository import Repository
from scraper.models.item import Item
from scraper.models.price import Price

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB  = os.getenv("MONGO_DB", "skin_market")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

async def check_connections():
    repo = Repository()

    # zapis
    item = Item(name="AK-47 | Redline", game="cs2", item_type="Rifle", wear="Field-Tested", source="steam")
    await repo.upsert_item(item.to_dict())
    print("[OK] Item zapisany")

    # odczyt
    result = await repo.get_item("AK-47 | Redline", "steam")
    print(f"[OK] Item odczytany: {result['name']}")

    # cena
    price = Price(item_name="AK-47 | Redline", source="steam", price=15.49, volume=120)
    await repo.insert_price(price.to_dict())
    latest = await repo.get_latest_price("AK-47 | Redline", "steam")
    print(f"[OK] Cena odczytana: {latest['price']} {latest['currency']}")

    repo.close()


if __name__ == "__main__":
    asyncio.run(check_connections())