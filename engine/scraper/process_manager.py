import asyncio
import multiprocessing
import os
import signal
from dotenv import load_dotenv

from scraper.worker import run_all_workers

load_dotenv()

WORKER_COUNT  = int(os.getenv("WORKER_COUNT", 2))   # wątki asyncio na proces
CPU_COUNT     = int(os.getenv("CPU_COUNT", multiprocessing.cpu_count()))


def start_process(process_id: int) -> None:
    """Punkt wejścia każdego procesu – uruchamia pulę workerów asyncio."""
    # ignoruj SIGINT w procesach potomnych – obsługuje go proces główny
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    print(f"[Process {process_id}] Start (PID: {os.getpid()}, workers: {WORKER_COUNT})")
    asyncio.run(run_all_workers())


def run_multiprocess() -> None:
    """Uruchamia CPU_COUNT procesów, każdy z WORKER_COUNT workerów asyncio."""
    print(f"[Manager] Uruchamiam {CPU_COUNT} procesów x {WORKER_COUNT} workerów")
    print(f"[Manager] Łącznie: {CPU_COUNT * WORKER_COUNT} równoległych workerów")

    processes = []
    for i in range(CPU_COUNT):
        p = multiprocessing.Process(target=start_process, args=(i,))
        p.start()
        processes.append(p)

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\n[Manager] Zatrzymuję procesy...")
        for p in processes:
            p.terminate()
        for p in processes:
            p.join()
        print("[Manager] Wszystkie procesy zatrzymane")