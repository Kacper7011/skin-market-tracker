import os
import json
import redis
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB  = os.getenv("MONGO_DB", "skin_market")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

QUEUE_SCRAPE = "queue:scrape"


def get_mongo():
    client = MongoClient(MONGO_URI)
    return client[MONGO_DB]


def get_redis():
    return redis.from_url(REDIS_URL, decode_responses=True)


# ---------- items ----------

def fetch_items(limit: int = 50) -> list:
    db = get_mongo()
    return list(db.items.find({}, {"_id": 0}).limit(limit))


def fetch_item(name: str, source: str = "steam") -> dict | None:
    db = get_mongo()
    return db.items.find_one({"name": name, "source": source}, {"_id": 0})


# ---------- prices ----------

def fetch_price_history(item_name: str, source: str = "steam", limit: int = 100) -> list:
    db = get_mongo()
    cursor = db.prices.find(
        {"item_name": item_name, "source": source},
        {"_id": 0},
        sort=[("timestamp", -1)],
    ).limit(limit)
    return list(cursor)


# ---------- listings ----------

def fetch_listings(item_name: str, source: str = "steam") -> list:
    db = get_mongo()
    cursor = db.listings.find(
        {"item_name": item_name, "source": source},
        {"_id": 0},
    )
    return list(cursor)


# ---------- scrape_logs ----------

def fetch_recent_logs(limit: int = 20) -> list:
    db = get_mongo()
    cursor = db.scrape_logs.find(
        {},
        {"_id": 0},
        sort=[("started_at", -1)],
    ).limit(limit)
    return list(cursor)


# ---------- queue ----------

def push_scrape_task(source: str, action: str, item_name: str) -> None:
    r = get_redis()
    task = {"source": source, "action": action, "item_name": item_name}
    r.rpush(QUEUE_SCRAPE, json.dumps(task))


def get_queue_length() -> int:
    r = get_redis()
    return r.llen(QUEUE_SCRAPE)


# ---------- steam_auth ----------

def save_steam_auth(username: str, sessionid: str, login_secure: str) -> None:
    from datetime import datetime, timezone
    db = get_mongo()
    db.steam_auth.delete_many({})
    db.steam_auth.insert_one({
        "username":        username,
        "sessionid":       sessionid,
        "steamLoginSecure": login_secure,
        "logged_in_at":    datetime.now(timezone.utc),
    })


def get_steam_auth_status() -> dict | None:
    db = get_mongo()
    return db.steam_auth.find_one(
        {},
        {"_id": 0, "steamLoginSecure": 0, "sessionid": 0},
        sort=[("logged_in_at", -1)],
    )