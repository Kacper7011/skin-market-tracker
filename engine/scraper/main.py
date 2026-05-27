import asyncio
from scraper.worker import run_all_workers

if __name__ == "__main__":
    print("[Engine] Start")
    asyncio.run(run_all_workers())