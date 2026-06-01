from scraper.models.item import Item
from scraper.models.price import Price
from scraper.models.listing import Listing
from scraper.models.scrape_log import ScrapeLog
from datetime import datetime


def test_item_to_dict():
    item = Item(name="AK-47 | Redline", game="cs2", item_type="Rifle", wear="Field-Tested")
    d = item.to_dict()
    assert d["name"] == "AK-47 | Redline"
    assert d["game"] == "cs2"
    assert d["wear"] == "Field-Tested"
    assert d["source"] == "steam"
    assert isinstance(d["created_at"], datetime)


def test_price_to_dict():
    price = Price(item_name="AK-47 | Redline", source="steam", price=15.49, volume=120)
    d = price.to_dict()
    assert d["price"] == 15.49
    assert d["volume"] == 120
    assert d["currency"] == "USD"


def test_listing_to_dict():
    listing = Listing(item_name="AK-47 | Redline", source="steam", price=15.99, quantity=1)
    d = listing.to_dict()
    assert d["price"] == 15.99
    assert d["quantity"] == 1


def test_scrape_log_success():
    log = ScrapeLog(source="steam", status="success", items_scraped=8, duration_seconds=2.5)
    d = log.to_dict()
    assert d["status"] == "success"
    assert d["items_scraped"] == 8


def test_scrape_log_error():
    log = ScrapeLog(source="steam", status="error", error_message="timeout")
    d = log.to_dict()
    assert d["status"] == "error"
    assert d["error_message"] == "timeout"