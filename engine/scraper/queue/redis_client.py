import os
import json
from typing import Optional
import redis.asyncio as aioredis
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

QUEUE_SCRAPE  = "queue:scrape"   # zadania do wykonania
QUEUE_RESULTS = "queue:results"  # wyniki do zapisu


class RedisClient:
    def __init__(self):
        self.redis = aioredis.from_url(REDIS_URL, decode_responses=True)

    async def push_task(self, task: dict) -> None:
        """Dodaje zadanie na koniec kolejki."""
        await self.redis.rpush(QUEUE_SCRAPE, json.dumps(task))

    async def pop_task(self, timeout: int = 5) -> Optional[dict]:
        """Pobiera zadanie z kolejki (blokuje max timeout sekund)."""
        result = await self.redis.blpop(QUEUE_SCRAPE, timeout=timeout)
        if result:
            _, value = result
            return json.loads(value)
        return None

    async def push_result(self, result: dict) -> None:
        """Odkłada wynik scrapowania do kolejki wyników."""
        await self.redis.rpush(QUEUE_RESULTS, json.dumps(result))

    async def pop_result(self, timeout: int = 5) -> Optional[dict]:
        """Pobiera wynik z kolejki wyników."""
        result = await self.redis.blpop(QUEUE_RESULTS, timeout=timeout)
        if result:
            _, value = result
            return json.loads(value)
        return None

    async def get_queue_length(self, queue: str = QUEUE_SCRAPE) -> int:
        return await self.redis.llen(queue)

    async def clear_queue(self, queue: str = QUEUE_SCRAPE) -> None:
        await self.redis.delete(queue)

    async def close(self) -> None:
        await self.redis.aclose()