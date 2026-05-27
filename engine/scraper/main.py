import os
import asyncio
from dotenv import load_dotenv
import motor.motor_asyncio
import redis.asyncio as aioredis

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


if __name__ == "__main__":
    asyncio.run(check_connections())