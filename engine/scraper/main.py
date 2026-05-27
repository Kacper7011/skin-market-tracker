import os
import asyncio
from dotenv import load_dotenv
import motor.motor_asyncio
import redis.asyncio as aioredis
from scraper.db.repository import Repository
from scraper.models.item import Item
from scraper.models.price import Price
from scraper.queue.redis_client import RedisClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB  = os.getenv("MONGO_DB", "skin_market")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

async def check_connections():
    q = RedisClient()

    for i in range(3):
        await q.push_task({"source": "steam", "item": f"AK-47 | Redline #{i}"})
    
    length = await q.get_queue_length()
    print(f"[OK] Kolejka ma {length} zadania")

    # pobierz jedno
    task = await q.pop_task()
    print(f"[OK] Pobrano zadanie: {task}")

    length = await q.get_queue_length()
    print(f"[OK] Kolejka ma teraz {length} zadania")

    await q.clear_queue()
    print("[OK] Kolejka wyczyszczona")

    await q.close()


if __name__ == "__main__":
    asyncio.run(check_connections())