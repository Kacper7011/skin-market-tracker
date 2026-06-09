import os
import json
import re
import redis
import requests as req
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB  = os.getenv("MONGO_DB", "skin_market")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

QUEUE_SCRAPE        = "queue:scrape"
STEAM_SEARCH_TTL    = 300  # 5 minutes
EXCHANGE_RATES_TTL  = 300  # 5 minutes
FLOAT_CACHE_TTL     = 86400  # 24h
BROWSE_CACHE_TTL    = 180  # 3 minutes
LISTINGS_CACHE_TTL  = 60   # 1 minute

_STEAM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://steamcommunity.com/market/",
    "X-Requested-With": "XMLHttpRequest",
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


# ---------- skin catalog ----------

def search_skin_catalog(query: str, limit: int = 30) -> list:
    """Searches local MongoDB skin_catalog collection."""
    db = get_mongo()
    filters = {}
    if query and len(query) >= 2:
        filters["name"] = {"$regex": re.escape(query), "$options": "i"}
    cursor = db.skin_catalog.find(filters, {"_id": 0}).limit(limit)
    return list(cursor)


def get_catalog_count() -> int:
    db = get_mongo()
    return db.skin_catalog.count_documents({})


def browse_skin_catalog(item_type: str = "", weapon: str = "", wear: str = "",
                         stattrak: str = "", page: int = 1, per_page: int = 48) -> dict:
    """Browse skin_catalog by category with filters."""
    db = get_mongo()
    filters: dict = {}

    if item_type:
        types = [t.strip() for t in item_type.split(",") if t.strip()]
        if len(types) == 1:
            filters["item_type"] = {"$regex": re.escape(types[0]), "$options": "i"}
        else:
            filters["item_type"] = {"$in": types}
    if weapon:
        # weapon is the base weapon name, e.g. "AK-47" — match at start of name
        filters["name"] = {"$regex": re.escape(weapon), "$options": "i"}
    if wear:
        filters["wear"] = wear
    if stattrak == "1":
        stattrak_filter = {"$regex": "StatTrak", "$options": "i"}
        if "name" in filters:
            filters["$and"] = [{"name": filters.pop("name")}, {"name": stattrak_filter}]
        else:
            filters["name"] = stattrak_filter
    elif stattrak == "0":
        # exclude StatTrak AND Souvenir
        no_st = {"$not": {"$regex": "StatTrak|Souvenir", "$options": "i"}}
        if "name" in filters:
            filters["$and"] = [{"name": filters.pop("name")}, {"name": no_st}]
        else:
            filters["name"] = no_st

    skip = (page - 1) * per_page
    items = list(
        db.skin_catalog.find(filters, {"_id": 0})
        .sort("name", 1)
        .skip(skip)
        .limit(per_page)
    )
    total = db.skin_catalog.count_documents(filters)
    return {"items": items, "total": total, "page": page, "per_page": per_page}


# ---------- steam browse (tag-based) ----------

def steam_browse_search(
    type_tags: list,
    weapon_tags: list,
    wear_tags: list,
    quality_tag: str,
    start: int = 0,
    count: int = 48,
) -> dict:
    """Browse Steam Market by category tags with Redis cache."""
    import hashlib

    params: list = [
        ("appid", 730),
        ("norender", 1),
        ("count", count),
        ("start", start),
        ("search_descriptions", 0),
    ]
    for t in type_tags:
        params.append(("category_730_Type[]", t))
    for t in weapon_tags:
        params.append(("category_730_Weapon[]", t))
    # Only send exterior tags when filtering (not all 5 = no filter needed)
    ALL_WEAR_TAGS = {
        "tag_WearCategory0", "tag_WearCategory1", "tag_WearCategory2",
        "tag_WearCategory3", "tag_WearCategory4",
    }
    if wear_tags and set(wear_tags) != ALL_WEAR_TAGS:
        for t in wear_tags:
            params.append(("category_730_Exterior[]", t))
    if quality_tag:
        params.append(("category_730_Quality[]", quality_tag))

    cache_key = "browse:" + hashlib.md5(str(sorted(params)).encode()).hexdigest()
    r = get_redis()
    cached = r.get(cache_key)
    if cached:
        return json.loads(cached)

    try:
        resp = req.get(
            "https://steamcommunity.com/market/search/render/",
            params=params,
            headers=_STEAM_HEADERS,
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"[browse] Steam returned {resp.status_code}")
            return {"items": [], "total": 0, "start": start}

        data = resp.json()
        if not data.get("success"):
            return {"items": [], "total": 0, "start": start}

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

        result = {
            "items": results,
            "total": data.get("total_count", 0),
            "start": start,
            "count": count,
        }
        r.setex(cache_key, BROWSE_CACHE_TTL, json.dumps(result))
        return result

    except Exception as e:
        print(f"[browse] Error: {e}")
        return {"items": [], "total": 0, "start": start}


# ---------- live listings ----------

def _get_steam_cookies() -> dict:
    """Returns Steam session cookies from MongoDB, or empty dict if not logged in."""
    db = get_mongo()
    auth = db.steam_auth.find_one({}, sort=[("logged_in_at", -1)])
    if auth and auth.get("sessionid") and auth.get("steamLoginSecure"):
        return {
            "sessionid":        auth["sessionid"],
            "steamLoginSecure": auth["steamLoginSecure"],
        }
    return {}


def get_steam_live_listings(item_name: str) -> dict:
    """Returns live market overview for an item using Steam priceoverview API (60s cache).

    Steam's individual listing render API (/render/) no longer returns JSON — it switched
    to SSR. priceoverview is the only publicly available endpoint that still works.
    """
    from urllib.parse import quote
    cache_key = f"listings:{item_name.lower()}"
    r = get_redis()
    cached = r.get(cache_key)
    if cached:
        return json.loads(cached)

    try:
        resp = req.get(
            "https://steamcommunity.com/market/priceoverview/",
            params={"appid": 730, "market_hash_name": item_name, "currency": 1},
            headers=_STEAM_HEADERS,
            timeout=10,
        )
        if resp.status_code != 200:
            return {"success": False}

        data = resp.json()
        if not data.get("success"):
            return {"success": False}

        def _parse_usd(price_str: str) -> float | None:
            if not price_str:
                return None
            try:
                return round(float(re.sub(r"[^\d.]", "", price_str)), 2)
            except ValueError:
                return None

        result = {
            "success":      True,
            "lowest_price": _parse_usd(data.get("lowest_price", "")),
            "median_price": _parse_usd(data.get("median_price", "")),
            "volume":       data.get("volume", "–"),
            "steam_url":    f"https://steamcommunity.com/market/listings/730/{quote(item_name)}",
        }
        r.setex(cache_key, LISTINGS_CACHE_TTL, json.dumps(result))
        return result

    except Exception as e:
        print(f"[live_listings] Error: {e}")
        return {"success": False}


# ---------- inspect float ----------

def get_inspect_float(inspect_url: str) -> dict | None:
    """Fetches float/pattern via CSFloat API with Redis cache (24h TTL)."""
    import hashlib
    cache_key = f"float:{hashlib.md5(inspect_url.encode()).hexdigest()}"
    r = get_redis()
    cached = r.get(cache_key)
    if cached:
        return json.loads(cached)
    try:
        resp = req.get(
            "https://api.csfloat.com/",
            params={"url": inspect_url},
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if resp.status_code == 200:
            info = resp.json().get("iteminfo", {})
            result = {"float_value": info.get("floatvalue"), "paint_seed": info.get("paintseed")}
            r.setex(cache_key, FLOAT_CACHE_TTL, json.dumps(result))
            return result
    except Exception as e:
        print(f"[inspect_float] Error: {e}")
    return None


# ---------- exchange rates ----------

def get_exchange_rates() -> dict:
    """Fetches live USD-based exchange rates with Redis cache (5 min TTL)."""
    cache_key = "exchange:rates"
    r = get_redis()
    cached = r.get(cache_key)
    if cached:
        return json.loads(cached)

    rates: dict = {"USD": 1.0}

    try:
        resp = req.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=5)
        if resp.status_code == 200:
            fiat = resp.json().get("rates", {})
            rates["EUR"] = fiat.get("EUR", 0.92)
            rates["PLN"] = fiat.get("PLN", 3.95)
    except Exception as e:
        print(f"[exchange_rates] fiat error: {e}")
        rates["EUR"] = 0.92
        rates["PLN"] = 3.95

    try:
        resp = req.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin", "vs_currencies": "usd"},
            timeout=5,
        )
        if resp.status_code == 200:
            btc_usd = resp.json().get("bitcoin", {}).get("usd", 1)
            rates["BTC"] = round(1 / btc_usd, 10) if btc_usd else 0
    except Exception as e:
        print(f"[exchange_rates] BTC error: {e}")
        rates["BTC"] = 0

    r.setex(cache_key, EXCHANGE_RATES_TTL, json.dumps(rates))
    return rates


# ---------- clear database ----------

def clear_all_items() -> dict:
    db = get_mongo()
    items_deleted  = db.items.delete_many({}).deleted_count
    prices_deleted = db.prices.delete_many({}).deleted_count
    return {"items": items_deleted, "prices": prices_deleted}


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
