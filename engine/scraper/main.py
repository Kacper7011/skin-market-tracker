import multiprocessing
from scraper.process_manager import run_multiprocess

if __name__ == "__main__":
    multiprocessing.set_start_method("fork")
    print("[Engine] Start")
    run_multiprocess()