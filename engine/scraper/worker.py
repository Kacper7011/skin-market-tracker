import asyncio
import os
import time
from datetime import datetime
from dotenv import load_dotenv

from scraper.queue.redis_client import RedisClient
from scraper.db.repository import Repository
from scraper.parsers.steam import SteamParser
from scraper.models.scrape_log import ScrapeLog

load_dotenv()

WORKER_COUNT = int(os.getenv("WORKER_COUNT", 4))


PARSERS = {
    "steam": SteamParser(),
}


async def process_task(task: dict, repo: Repository) -> None:
    source    = task.get("source", "steam")
    item_name = task.get("item_name")
    action    = task.get("action", "listings")  # "listings" | "search" | "history"

    if not item_name:
        print(f"[WARN] Zadanie bez item_name: {task}")
        return

    parser = PARSERS.get(source)
    if not parser:
        print(f"[WARN] Nieznane źródło: {source}")
        return

    started_at = time.time()
    items_scraped = 0
    error_message = None

    try:
        if action == "search":
            items = await parser.search_items(item_name)
            for item in items:
                await repo.upsert_item(item)
            items_scraped = len(items)

        elif action == "listings":
            listings = await parser.fetch_listings(item_name)
            await repo.replace_listings(item_name, source, listings)
            items_scraped = len(listings)

        elif action == "history":
            prices = await parser.fetch_price_history(item_name)
            for price in prices:
                await repo.insert_price(price)
            items_scraped = len(prices)

        print(f"[OK] {source} | {action} | {item_name} | {items_scraped} rekordów")

    except Exception as e:
        error_message = str(e)
        print(f"[ERROR] {source} | {action} | {item_name} | {e}")

    finally:
        log = ScrapeLog(
            source=source,
            status="success" if not error_message else "error",
            items_scraped=items_scraped,
            duration_seconds=round(time.time() - started_at, 2),
            error_message=error_message,
            worker_id=os.getpid(),
            started_at=datetime.utcnow(),
        )
        await repo.insert_log(log.to_dict())


async def run_worker(worker_id: int) -> None:
    print(f"[Worker {worker_id}] Start (PID: {os.getpid()})")
    queue = RedisClient()
    repo  = Repository()

    try:
        while True:
            task = await queue.pop_task(timeout=5)
            if task:
                print(f"[Worker {worker_id}] Zadanie: {task}")
                await process_task(task, repo)
            else:
                # brak zadań – czekamy
                await asyncio.sleep(1)
    except asyncio.CancelledError:
        print(f"[Worker {worker_id}] Zatrzymany")
    finally:
        await queue.close()
        repo.close()


async def run_all_workers() -> None:
    workers = [
        asyncio.create_task(run_worker(i))
        for i in range(WORKER_COUNT)
    ]
    await asyncio.gather(*workers)