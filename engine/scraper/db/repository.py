import os
from datetime import datetime
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
            {"$set": {**item, "updated_at": datetime.utcnow()}},
            upsert=True,
        )

    async def get_item(self, name: str, source: str) -> Optional[dict]:
        return await self.db.items.find_one({"name": name, "source": source})

    # ---------- prices ----------

    async def insert_price(self, price: dict) -> None:
        """Zawsze wstawia nowy rekord – budujemy historię cen."""
        await self.db.prices.insert_one(price)

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

    # ---------- cleanup ----------

    def close(self):
        self.client.close()