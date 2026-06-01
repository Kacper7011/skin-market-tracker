import asyncio
import multiprocessing
from scraper.process_manager import run_multiprocess
from scraper.scheduler import schedule_tasks


async def run_scheduler() -> None:
    await schedule_tasks()


if __name__ == "__main__":
    multiprocessing.set_start_method("fork")
    print("[Engine] Start")

    # scheduler w osobnym procesie
    scheduler_process = multiprocessing.Process(
        target=lambda: asyncio.run(run_scheduler()),
        name="scheduler",
    )
    scheduler_process.daemon = True
    scheduler_process.start()
    print("[Engine] Scheduler uruchomiony")

    # workery
    run_multiprocess()