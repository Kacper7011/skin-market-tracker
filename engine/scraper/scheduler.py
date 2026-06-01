import asyncio
import os
from dotenv import load_dotenv
from scraper.queue.redis_client import RedisClient

load_dotenv()

SCHEDULE_INTERVAL = int(os.getenv("SCHEDULE_INTERVAL", 3600))  # sekundy, domyślnie 1h

# Lista przedmiotów do automatycznego scrapowania
TRACKED_ITEMS = [
    "AK-47 | Redline (Field-Tested)",
    "AK-47 | Redline (Minimal Wear)",
    "AWP | Asiimov (Field-Tested)",
    "AWP | Dragon Lore (Field-Tested)",
    "M4A4 | Howl (Field-Tested)",
]


async def schedule_tasks() -> None:
    print(f"[Scheduler] Start – interwał: {SCHEDULE_INTERVAL}s")

    while True:
        queue = RedisClient()
        try:
            for item_name in TRACKED_ITEMS:
                await queue.push_task({
                    "source":    "steam",
                    "action":    "search",
                    "item_name": item_name,
                })
                await queue.push_task({
                    "source":    "steam",
                    "action":    "history",
                    "item_name": item_name,
                })
            print(f"[Scheduler] Dodano {len(TRACKED_ITEMS) * 2} zadań")
        except Exception as e:
            print(f"[Scheduler] Błąd: {e}")
        finally:
            await queue.close()

        await asyncio.sleep(SCHEDULE_INTERVAL)