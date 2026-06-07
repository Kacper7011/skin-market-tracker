import os
from datetime import datetime, timezone
from typing import Optional
import motor.motor_asyncio
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB  = os.getenv("MONGO_DB", "skin_market")


class Repository:
    def __init__(self):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
        self.db = self.client[MONGO_DB]

    # ---------- items ----------

    async def upsert_item(self, item: dict) -> None:
        """Wstawia lub aktualizuje przedmiot po nazwie i źródle."""
        await self.db.items.update_one(
            {"name": item["name"], "source": item["source"]},
            {"$set": {**item, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )

    async def get_item(self, name: str, source: str) -> Optional[dict]:
        return await self.db.items.find_one({"name": name, "source": source})

    # ---------- prices ----------

    async def insert_price(self, price: dict) -> None:
        await self.db.prices.insert_one(price)

    async def replace_prices(self, item_name: str, source: str, prices: list[dict]) -> None:
        """Replaces all price history for an item with fresh data."""
        await self.db.prices.delete_many({"item_name": item_name, "source": source})
        if prices:
            await self.db.prices.insert_many(prices)

    async def get_latest_price(self, item_name: str, source: str) -> Optional[dict]:
        return await self.db.prices.find_one(
            {"item_name": item_name, "source": source},
            sort=[("timestamp", -1)],
        )

    async def get_price_history(self, item_name: str, source: str, limit: int = 100) -> list:
        cursor = self.db.prices.find(
            {"item_name": item_name, "source": source},
            sort=[("timestamp", -1)],
        ).limit(limit)
        return await cursor.to_list(length=limit)

    # ---------- listings ----------

    async def replace_listings(self, item_name: str, source: str, listings: list[dict]) -> None:
        """Usuwa stare oferty i wstawia nowe – snapshot aktualnego rynku."""
        await self.db.listings.delete_many({"item_name": item_name, "source": source})
        if listings:
            await self.db.listings.insert_many(listings)

    async def get_listings(self, item_name: str, source: str) -> list:
        cursor = self.db.listings.find({"item_name": item_name, "source": source})
        return await cursor.to_list(length=100)

    # ---------- scrape_logs ----------

    async def insert_log(self, log: dict) -> None:
        await self.db.scrape_logs.insert_one(log)

    async def get_recent_logs(self, limit: int = 20) -> list:
        cursor = self.db.scrape_logs.find(
            sort=[("started_at", -1)]
        ).limit(limit)
        return await cursor.to_list(length=limit)

    # ---------- skin_catalog ----------

    async def upsert_catalog_item(self, item: dict) -> None:
        await self.db.skin_catalog.update_one(
            {"name": item["name"]},
            {"$set": {**item, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )

    async def bulk_upsert_catalog(self, items: list[dict]) -> None:
        from pymongo import UpdateOne
        if not items:
            return
        now = datetime.now(timezone.utc)
        ops = [
            UpdateOne(
                {"name": it["name"]},
                {"$set": {**it, "updated_at": now}},
                upsert=True,
            )
            for it in items
        ]
        await self.db.skin_catalog.bulk_write(ops, ordered=False)

    async def get_catalog_count(self) -> int:
        return await self.db.skin_catalog.count_documents({})

    # ---------- cleanup ----------

    def close(self):
        self.client.close()