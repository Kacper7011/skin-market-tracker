import os
import asyncio
from dotenv import load_dotenv
import motor.motor_asyncio
import redis.asyncio as aioredis
from scraper.models.item import Item
from scraper.models.price import Price

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB  = os.getenv("MONGO_DB", "skin_market")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")


async def check_connections():
    # MongoDB
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    await client[MONGO_DB].command("ping")
    print("[OK] MongoDB połączone")
    client.close()

    # Redis
    r = await aioredis.from_url(REDIS_URL)
    await r.ping()
    print("[OK] Redis połączone")
    await r.aclose()

    item = Item(name="AK-47 | Redline", game="cs2", item_type="Rifle", wear="Field-Tested")
    price = Price(item_name="AK-47 | Redline", source="steam", price=15.49, volume=120)

    print(item.to_dict())
    print(price.to_dict())


if __name__ == "__main__":
    asyncio.run(check_connections())