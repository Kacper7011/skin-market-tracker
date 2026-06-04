import os
import json
import re
import redis
import requests as req
import urllib.parse
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB  = os.getenv("MONGO_DB", "skin_market")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

QUEUE_SCRAPE       = "queue:scrape"
LIVE_LISTINGS_TTL  = 45   # seconds
STEAM_SEARCH_TTL   = 300  # 5 minutes

_STEAM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
}


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
        sort=[("timestamp", 1)],
    ).limit(limit)
    return list(cursor)


# ---------- listings (MongoDB snapshot) ----------

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


# ---------- steam market search proxy ----------

def steam_search_proxy(query: str, count: int = 20) -> list:
    """Fetches CS2 skins from Steam Market search with Redis cache."""
    if not query or len(query) < 2:
        return []

    cache_key = f"search:{query.lower().strip()}"
    r = get_redis()
    cached = r.get(cache_key)
    if cached:
        return json.loads(cached)

    try:
        resp = req.get(
            "https://steamcommunity.com/market/search/render/",
            params={"query": query, "appid": 730, "count": count,
                    "search_descriptions": 0, "norender": 1},
            headers=_STEAM_HEADERS,
            timeout=10,
        )
        if resp.status_code != 200:
            return []

        data = resp.json()
        if not data.get("success"):
            return []

        results = []
        for entry in data.get("results", []):
            asset = entry.get("asset_description", {})
            icon_hash = asset.get("icon_url", "")
            name = entry.get("name", "")
            results.append({
                "name": name,
                "icon_url": f"https://community.cloudflare.steamstatic.com/economy/image/{icon_hash}" if icon_hash else "",
                "item_type": asset.get("type", ""),
                "wear": _parse_wear(name),
                "stattrak": "StatTrak" in name,
            })

        if results:
            r.setex(cache_key, STEAM_SEARCH_TTL, json.dumps(results))
        return results

    except Exception as e:
        print(f"[steam_search] Error: {e}")
        return []


def _parse_wear(name: str) -> str | None:
    for w in ["Factory New", "Minimal Wear", "Field-Tested", "Well-Worn", "Battle-Scarred"]:
        if w in name:
            return w
    return None


# ---------- live listings (Redis cache + Steam fetch) ----------

def get_live_listings(item_name: str) -> tuple[list, bool]:
    """Returns (listings, from_cache). Fetches from Steam if cache miss."""
    r = get_redis()
    cache_key = f"live:{item_name}"
    cached = r.get(cache_key)
    if cached:
        return json.loads(cached), True

    listings = _fetch_live_from_steam(item_name)
    if listings is not None:
        r.setex(cache_key, LIVE_LISTINGS_TTL, json.dumps(listings))
        return listings, False
    return [], False


def get_live_listings_ttl(item_name: str) -> int:
    """Returns remaining TTL in seconds for cached live listings (-1 if not cached)."""
    r = get_redis()
    return r.ttl(f"live:{item_name}")


def _fetch_live_from_steam(item_name: str, count: int = 20) -> list | None:
    """Directly fetches live listings from Steam Market API."""
    encoded = urllib.parse.quote(item_name)
    url = f"https://steamcommunity.com/market/listings/730/{encoded}/render/"
    params = {"count": count, "currency": 1, "language": "english", "start": 0}

    try:
        resp = req.get(url, params=params, headers=_STEAM_HEADERS, timeout=15)
        if resp.status_code != 200:
            return None

        data = resp.json()
        if not data.get("success"):
            return None

        assets = data.get("assets", {}).get("730", {}).get("2", {})
        listinginfo = data.get("listinginfo", {})
        results = []

        for listing_id, info in listinginfo.items():
            price_raw = info.get("converted_price", 0) + info.get("converted_fee", 0)
            price = round(price_raw / 100, 2)

            asset_ref = info.get("asset", {})
            class_id = str(asset_ref.get("classid", ""))
            instance_id = str(asset_ref.get("instanceid", "0"))
            asset_id = str(asset_ref.get("id", ""))

            market_actions = asset_ref.get("market_actions", [])
            inspect_link = None
            if market_actions:
                tmpl = market_actions[0].get("link", "")
                inspect_link = (
                    tmpl.replace("%listingid%", listing_id)
                        .replace("%assetid%", asset_id)
                )

            asset_data = assets.get(class_id, {}).get(instance_id, {})
            descriptions = asset_data.get("descriptions", [])
            wear = None
            stickers = []

            for d in descriptions:
                val = d.get("value", "")
                if "Exterior:" in val:
                    m = re.search(r"Exterior:\s*([^<\n]+)", val)
                    if m:
                        wear = m.group(1).strip()
                if "Sticker:" in val:
                    found = re.findall(r"Sticker:\s*([^<\n,]+)", val)
                    stickers.extend(s.strip() for s in found if s.strip())

            results.append({
                "listing_id": listing_id,
                "price": price,
                "wear": wear,
                "inspect_link": inspect_link,
                "stickers": stickers,
            })

        return results

    except Exception as e:
        print(f"[live_listings] Fetch error: {e}")
        return None


# ---------- steam_auth ----------

def save_steam_auth(username: str, sessionid: str, login_secure: str) -> None:
    from datetime import datetime, timezone
    db = get_mongo()
    db.steam_auth.delete_many({})
    db.steam_auth.insert_one({
        "username":         username,
        "sessionid":        sessionid,
        "steamLoginSecure": login_secure,
        "logged_in_at":     datetime.now(timezone.utc),
    })


def get_steam_auth_status() -> dict | None:
    db = get_mongo()
    return db.steam_auth.find_one(
        {},
        {"_id": 0, "steamLoginSecure": 0, "sessionid": 0},
        sort=[("logged_in_at", -1)],
    )
