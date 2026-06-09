import asyncio
import base64
import json
import os
from datetime import datetime, timezone

import aiohttp
import redis.asyncio as aioredis
from bs4 import BeautifulSoup

from scraper.models.item import Item
from scraper.models.price import Price
from scraper.parsers.base import BaseParser

REQUEST_DELAY = float(os.getenv("SKINPORT_REQUEST_DELAY", "3.0"))
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
ITEMS_CACHE_KEY = "skinport:items_cache"
ITEMS_CACHE_TTL = 300  # 5 minut

MARKET_URL   = "https://skinport.com/market"
API_URL      = "https://api.skinport.com/v1/items"
HISTORY_URL  = "https://api.skinport.com/v1/sales/history"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://skinport.com/",
}

_API_HEADERS = {
    **_HEADERS,
    "Accept": "application/json",
}


class SkinportParser(BaseParser):
    source = "skinport"

    async def _get_html(self, session: aiohttp.ClientSession, url: str, params: dict) -> str | None:
        await asyncio.sleep(REQUEST_DELAY)
        try:
            async with session.get(
                url, params=params, headers=_HEADERS,
                timeout=aiohttp.ClientTimeout(total=25),
            ) as resp:
                if resp.status == 429:
                    print("[SkinportParser] Rate limit – czekam 30s")
                    await asyncio.sleep(30)
                    return None
                if resp.status != 200:
                    print(f"[SkinportParser] HTML status {resp.status}")
                    return None
                return await resp.text()
        except Exception as e:
            print(f"[SkinportParser] Błąd HTML: {e}")
            return None

    async def search_items(self, query: str, count: int = 10) -> list[dict]:
        """Parses Skinport market search HTML with BeautifulSoup."""
        async with aiohttp.ClientSession() as session:
            html = await self._get_html(
                session, MARKET_URL, {"search": query, "currency": "USD"}
            )
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        results = []

        # Skinport uses Next.js SSR – class names contain "CatalogItem" prefix
        cards = soup.find_all("div", class_=lambda c: c and "CatalogItem_item" in " ".join(c) if isinstance(c, list) else c and "CatalogItem_item" in c)
        if not cards:
            # Fallback: broader search for any card-like container with item data
            cards = soup.select("[class*='CatalogItem']")

        for card in cards[:count]:
            name_el = card.find(class_=lambda c: c and "CatalogItem_name" in (
                " ".join(c) if isinstance(c, list) else c
            ))
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            img_el = card.find("img")
            icon_url = img_el.get("src", "") if img_el else ""

            item = Item(
                name=name,
                game="cs2",
                item_type="",
                icon_url=icon_url,
                source=self.source,
            )
            results.append(item.to_dict())

        return results

    async def _get_json(self, session: aiohttp.ClientSession, url: str, params: dict) -> list | dict | None:
        cid  = os.getenv("SKINPORT_CLIENT_ID", "")
        csec = os.getenv("SKINPORT_CLIENT_SECRET", "")
        headers = dict(_API_HEADERS)
        if cid and csec:
            token = base64.b64encode(f"{cid}:{csec}".encode()).decode()
            headers["Authorization"] = f"Basic {token}"

        await asyncio.sleep(REQUEST_DELAY)
        try:
            async with session.get(
                url, params=params, headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 429:
                    print("[SkinportParser] API rate limit – czekam 60s")
                    await asyncio.sleep(60)
                    return None
                if resp.status != 200:
                    print(f"[SkinportParser] API {url} status {resp.status}")
                    return None
                return await resp.json()
        except Exception as e:
            print(f"[SkinportParser] Błąd JSON {url}: {e}")
            return None

    async def fetch_price_history(self, item_name: str) -> list[dict]:
        """
        Fetches full price history from Skinport sales history API.
        Falls back to current-price snapshot (API items / HTML) if history unavailable.
        """
        async with aiohttp.ClientSession() as session:
            # Primary: sales history endpoint (full historical data)
            history = await self._get_json(
                session, HISTORY_URL,
                {"app_id": 730, "currency": "USD", "market_hash_name": item_name},
            )
            if isinstance(history, list) and history:
                print(f"[SkinportParser] /v1/sales/history przykład: {history[0]}")
            prices = self._parse_sales_history(history, item_name) if isinstance(history, list) and history else []

            if prices:
                print(f"[SkinportParser] Historia: {len(prices)} punktów dla '{item_name}'")
                return prices

            # Fallback: current lowest price from items API
            print(f"[SkinportParser] Brak historii dla '{item_name}' (API zwróciło {type(history).__name__} len={len(history) if isinstance(history, (list,dict)) else '?'}), próbuję /v1/items")
            items_data = await self._get_items_cached(session)
            price_val = self._price_from_api(items_data, item_name) if items_data else None

            if price_val is None and items_data:
                print(f"[SkinportParser] '{item_name}' nie znaleziono w /v1/items (exact match). Próbuję HTML.")

            if price_val is None:
                html = await self._get_html(
                    session, MARKET_URL, {"search": item_name, "currency": "USD"}
                )
                price_val = self._price_from_html(html, item_name) if html else None

        if price_val is None:
            print(f"[SkinportParser] Brak ceny dla '{item_name}' we wszystkich źródłach – skin może nie być notowany na Skinport")
            return []

        return [Price(
            item_name=item_name,
            source=self.source,
            price=price_val,
            volume=0,
            timestamp=datetime.now(timezone.utc),
        ).to_dict()]

    async def _get_items_cached(self, session: aiohttp.ClientSession) -> list | None:
        """Fetches /v1/items with Redis cache to avoid rate-limiting across workers."""
        r = aioredis.from_url(REDIS_URL, decode_responses=True)
        try:
            cached = await r.get(ITEMS_CACHE_KEY)
            if cached:
                data = json.loads(cached)
                print(f"[SkinportParser] /v1/items z Redis cache ({len(data)} pozycji)")
                return data

            data = await self._get_json(session, API_URL, {"app_id": 730, "currency": "USD", "tradable": 0})
            if data:
                print(f"[SkinportParser] /v1/items pobrano z API ({len(data)} pozycji), cache TTL={ITEMS_CACHE_TTL}s")
                await r.setex(ITEMS_CACHE_KEY, ITEMS_CACHE_TTL, json.dumps(data))
            return data
        except Exception as e:
            print(f"[SkinportParser] Cache błąd: {e}")
            return None
        finally:
            await r.aclose()

    def _parse_sales_history(self, data: list, item_name: str) -> list[dict]:
        """
        /v1/sales/history returns one dict per item with aggregated period stats:
        {market_hash_name, last_24_hours: {min, avg, volume}, last_7_days: {...},
         last_30_days: {...}, last_90_days: {...}}
        We build synthetic price points from each period using avg price.
        """
        from datetime import timedelta
        results = []
        now = datetime.now(timezone.utc)
        name_lower = item_name.lower()

        for entry in data:
            if not isinstance(entry, dict):
                continue
            if entry.get("market_hash_name", "").lower() != name_lower:
                continue

            # Each period becomes one synthetic data point
            periods = [
                ("last_90_days", 90),
                ("last_30_days", 30),
                ("last_7_days",  7),
                ("last_24_hours", 1),
            ]
            for key, days_ago in periods:
                period = entry.get(key) or {}
                avg    = period.get("avg")
                mn     = period.get("min")
                volume = int(period.get("volume") or 0)
                price_val = avg or mn
                if price_val is None or float(price_val) <= 0:
                    continue
                results.append(Price(
                    item_name=item_name,
                    source=self.source,
                    price=round(float(price_val), 2),
                    volume=volume,
                    timestamp=now - timedelta(days=days_ago),
                ).to_dict())
            break  # only one entry per item

        return results

    def _price_from_api(self, data: list, item_name: str) -> float | None:
        name_lower = item_name.lower().strip()
        best = None

        for entry in data:
            mhn = entry.get("market_hash_name", "").lower().strip()
            raw = entry.get("min_price")
            if raw is None:
                continue
            try:
                price = round(float(raw), 2)
            except (ValueError, TypeError):
                continue

            if mhn == name_lower:
                return price  # exact match — return immediately

            # Partial match as fallback (both names contain each other)
            if best is None and (name_lower in mhn or mhn in name_lower):
                best = price

        if best is not None:
            print(f"[SkinportParser] Użyto partial match dla '{item_name}'")
        return best

    def _price_from_html(self, html: str, item_name: str) -> float | None:
        """Parses Skinport market HTML with BeautifulSoup to extract lowest price."""
        soup = BeautifulSoup(html, "html.parser")
        name_lower = item_name.lower()

        cards = soup.find_all(class_=lambda c: c and "CatalogItem_item" in (
            " ".join(c) if isinstance(c, list) else c
        ))

        for card in cards:
            name_el = card.find(class_=lambda c: c and "CatalogItem_name" in (
                " ".join(c) if isinstance(c, list) else c
            ))
            if not name_el or name_lower not in name_el.get_text().lower():
                continue

            price_el = card.find(class_=lambda c: c and "CatalogItem_priceValue" in (
                " ".join(c) if isinstance(c, list) else c
            ))
            if not price_el:
                continue

            raw = price_el.get_text(strip=True).replace("$", "").replace(",", "").strip()
            try:
                return round(float(raw), 2)
            except ValueError:
                continue

        return None
