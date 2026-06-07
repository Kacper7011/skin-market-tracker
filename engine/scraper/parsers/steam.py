import asyncio
import os
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

from scraper.parsers.base import BaseParser
from scraper.models.item import Item
from scraper.models.price import Price
from scraper.models.listing import Listing
from scraper.auth.steam_session import steam_session

load_dotenv()

REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", 1.5))

SEARCH_URL  = "https://steamcommunity.com/market/search/render/"
LISTING_URL = "https://steamcommunity.com/market/listings/730/{}/render/"
HISTORY_URL = "https://steamcommunity.com/market/listings/730/{}"

HEADERS = {
    "User-Agent":        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language":   "en-US,en;q=0.9",
    "Accept":            "application/json, text/javascript, */*; q=0.01",
    "Referer":           "https://steamcommunity.com/market/",
    "X-Requested-With":  "XMLHttpRequest",
}


class SteamParser(BaseParser):
    source = "steam"

    def _get_cookies(self) -> dict:
        return steam_session.get_cookies()

    async def _get(self, session: aiohttp.ClientSession, url: str, params: dict = {}) -> Optional[dict | str]:
        await asyncio.sleep(REQUEST_DELAY)
        try:
            async with session.get(url, params=params, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 429:
                    print("[WARN] Steam rate limit – czekam 10s")
                    await asyncio.sleep(10)
                    return None
                if resp.status != 200:
                    print(f"[WARN] Status {resp.status} dla {url}")
                    return None
                content_type = resp.content_type or ""
                if "json" in content_type:
                    return await resp.json()
                return await resp.text()
        except Exception as e:
            print(f"[ERROR] {url}: {e}")
            return None

    async def search_items(self, query: str, count: int = 10) -> list[dict]:
        params = {
            "query": query,
            "count": count,
            "appid": 730,           # CS2
            "search_descriptions": 0,
            "norender": 1,
        }
        async with aiohttp.ClientSession() as session:
            data = await self._get(session, SEARCH_URL, params)

        if not data or not data.get("success"):
            return []

        results = []
        for entry in data.get("results", []):
            asset = entry.get("asset_description", {})
            item = Item(
                game="cs2",
                item_type=asset.get("type", ""),
                wear=self._parse_wear(entry.get("name", "")),
                name=entry.get("name", ""),
                icon_url=f"https://community.cloudflare.steamstatic.com/economy/image/{asset.get('icon_url', '')}",
                source=self.source,
            )
            results.append(item.to_dict())

        return results

    async def _fetch_float(self, session: aiohttp.ClientSession, inspect_link: str) -> tuple[Optional[float], Optional[int]]:
        """Fetches float_value and paint_seed from CSFloat API."""
        url = "https://api.csfloat.com/"
        try:
            async with session.get(
                url,
                params={"url": inspect_link},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status == 429:
                    print("[WARN] CSFloat rate limit (429)")
                    return None, None
                if resp.status != 200:
                    return None, None
                data = await resp.json()
                info = data.get("iteminfo", {})
                return info.get("floatvalue"), info.get("paintseed")
        except Exception as e:
            print(f"[WARN] CSFloat fetch error for {inspect_link}: {e}")
            return None, None

    async def fetch_listings(self, item_name: str) -> list[dict]:
        import re
        url = LISTING_URL.format(item_name.replace(" ", "%20"))
        params = {"count": 20, "currency": 1, "language": "english"}

        async with aiohttp.ClientSession() as session:
            data = await self._get(session, url, params)

        if not data or not isinstance(data, dict) or not data.get("success"):
            print(f"[WARN] Brak danych dla: {item_name}")
            return []

        listings = []
        listinginfo = data.get("listinginfo", {})
        assets = data.get("assets", {}).get("730", {}).get("2", {})

        for listing_id, info in listinginfo.items():
            price_raw = info.get("converted_price", 0) + info.get("converted_fee", 0)
            price = round(price_raw / 100, 2)

            asset_ref = info.get("asset", {})
            class_id = str(asset_ref.get("classid", ""))
            instance_id = str(asset_ref.get("instanceid", "0"))
            asset_id = str(asset_ref.get("id", ""))

            # inspect link
            market_actions = asset_ref.get("market_actions", [])
            inspect_link = None
            if market_actions:
                tmpl = market_actions[0].get("link", "")
                inspect_link = tmpl.replace("%listingid%", listing_id).replace("%assetid%", asset_id)

            # wear + stickers from asset descriptions
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

            listing = Listing(
                item_name=item_name,
                source=self.source,
                price=price,
                quantity=1,
                wear=wear,
                inspect_link=inspect_link,
                stickers=stickers,
                scraped_at=datetime.utcnow(),
            )
            listings.append(listing)

        # Concurrently fetch floats from CSFloat for all listings with inspect links
        async with aiohttp.ClientSession() as csfloat_session:
            tasks = []
            indices = []
            for i, listing in enumerate(listings):
                if listing.inspect_link:
                    tasks.append(self._fetch_float(csfloat_session, listing.inspect_link))
                    indices.append(i)

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for idx, result in zip(indices, results):
                    if isinstance(result, Exception):
                        print(f"[WARN] CSFloat gather exception: {result}")
                        continue
                    float_val, paint_seed = result
                    listings[idx].float_value = float_val
                    listings[idx].paint_seed = paint_seed

        return [l.to_dict() for l in listings]

    async def fetch_price_history(self, item_name: str) -> list[dict]:
        url = "https://steamcommunity.com/market/pricehistory/"

        for attempt in range(2):
            cookies = self._get_cookies()
            if not cookies:
                print("[WARN] Brak sesji Steam – historia cen niedostępna")
                return []

            params = {
                "appid":            730,
                "market_hash_name": item_name,
                "currency":         1,
                "sessionid":        cookies.get("sessionid", ""),
            }

            async with aiohttp.ClientSession(cookies=cookies) as session:
                data = await self._get(session, url, params)

            if not data or not isinstance(data, dict):
                print(f"[WARN] Brak historii cen dla: {item_name}")
                return []

            if data.get("success"):
                prices = []
                for entry in data.get("prices", []):
                    try:
                        raw_date  = entry[0][:11].strip()
                        timestamp = datetime.strptime(raw_date, "%b %d %Y")
                        price = Price(
                            item_name=item_name,
                            source=self.source,
                            price=round(float(entry[1]), 2),
                            volume=int(float(entry[2])),
                            timestamp=timestamp,
                        )
                        prices.append(price.to_dict())
                    except (ValueError, IndexError) as e:
                        print(f"[WARN] Błąd parsowania wpisu: {entry} – {e}")
                        continue
                print(f"[OK] Historia cen dla {item_name}: {len(prices)} wpisów")
                return prices

            if attempt == 0:
                print("[WARN] Sesja Steam wygasła – próba odświeżenia")
                steam_session.refresh()

        print(f"[WARN] Steam odmówił historii cen dla: {item_name}")
        return []

    async def fetch_catalog_pages(self, max_pages: int = 20) -> list[dict]:
        """Fetches up to max_pages×100 CS2 items for the local skin catalog."""
        results = []
        per_page = 100

        async with aiohttp.ClientSession() as session:
            for page in range(max_pages):
                start = page * per_page
                params = {
                    "appid": 730,
                    "count": per_page,
                    "start": start,
                    "norender": 1,
                    "search_descriptions": 0,
                }
                data = await self._get(session, SEARCH_URL, params)
                if not data or not data.get("success"):
                    break

                entries = data.get("results", [])
                if not entries:
                    break

                for entry in entries:
                    asset = entry.get("asset_description", {})
                    icon_hash = asset.get("icon_url", "")
                    name = entry.get("name", "")
                    results.append({
                        "name": name,
                        "icon_url": f"https://community.cloudflare.steamstatic.com/economy/image/{icon_hash}" if icon_hash else "",
                        "item_type": asset.get("type", ""),
                        "wear": self._parse_wear(name),
                        "source": self.source,
                    })

                total = data.get("total_count", 0)
                fetched_so_far = start + len(entries)
                print(f"[catalog] Strona {page+1}/{max_pages} – pobrano {fetched_so_far}/{total}")
                if fetched_so_far >= total:
                    break

        print(f"[catalog] Łącznie {len(results)} skinów")
        return results

    @staticmethod
    def _parse_wear(name: str) -> Optional[str]:
        wears = [
            "Factory New", "Minimal Wear", "Field-Tested",
            "Well-Worn", "Battle-Scarred"
        ]
        for w in wears:
            if w in name:
                return w
        return None