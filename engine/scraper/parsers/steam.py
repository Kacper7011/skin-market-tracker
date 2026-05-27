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

load_dotenv()

REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", 1.5))

SEARCH_URL  = "https://steamcommunity.com/market/search/render/"
LISTING_URL = "https://steamcommunity.com/market/listings/730/{}/render/"
HISTORY_URL = "https://steamcommunity.com/market/listings/730/{}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


class SteamParser(BaseParser):
    source = "steam"

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

    async def fetch_listings(self, item_name: str) -> list[dict]:
        url = LISTING_URL.format(item_name.replace(" ", "%20"))
        params = {"count": 10, "currency": 1, "language": "english"}

        async with aiohttp.ClientSession() as session:
            data = await self._get(session, url, params)

        if not data or not isinstance(data, dict) or not data.get("success"):
            print(f"[WARN] Brak danych dla: {item_name}")
            return []

        listings = []
        listinginfo = data.get("listinginfo", {})
        assets = data.get("assets", {}).get("730", {})

        for listing_id, info in listinginfo.items():
            price_raw = info.get("converted_price", 0) + info.get("converted_fee", 0)
            price = round(price_raw / 100, 2)

            # pobierz wear z opisu HTML
            wear = None
            description_html = ""
            asset_ref = info.get("asset", {})
            class_id = str(asset_ref.get("classid", ""))
            instance_id = str(asset_ref.get("instanceid", "0"))
            asset_data = assets.get(class_id, {}).get(instance_id, {})
            descriptions = asset_data.get("descriptions", [])
            for d in descriptions:
                val = d.get("value", "")
                if "Exterior:" in val:
                    soup = BeautifulSoup(val, "html.parser")
                    wear = soup.get_text().replace("Exterior:", "").strip()

            listing = Listing(
                item_name=item_name,
                source=self.source,
                price=price,
                quantity=1,
                wear=wear,
                scraped_at=datetime.utcnow(),
            )
            listings.append(listing.to_dict())

        return listings

    async def fetch_price_history(self, item_name: str) -> list[dict]:
        url = HISTORY_URL.format(item_name.replace(" ", "%20"))

        async with aiohttp.ClientSession() as session:
            html = await self._get(session, url)

        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        prices = []

        # historia cen jest osadzona w tagu <script> jako zmienna JS
        for script in soup.find_all("script"):
            text = script.string or ""
            if "var line1=" in text:
                start = text.find("var line1=") + len("var line1=")
                end = text.find(";", start)
                import json
                raw = json.loads(text[start:end])
                for entry in raw:
                    price = Price(
                        item_name=item_name,
                        source=self.source,
                        price=float(entry[1]),
                        volume=int(entry[2]) if len(entry) > 2 else 0,
                        timestamp=datetime.strptime(entry[0][:11].strip(), "%b %d %Y"),
                    )
                    prices.append(price.to_dict())
                break

        return prices

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