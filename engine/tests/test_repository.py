import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from scraper.db.repository import Repository
from datetime import datetime, timezone


@pytest.fixture
def mock_repo():
    with patch("scraper.db.repository.motor.motor_asyncio.AsyncIOMotorClient") as mock_client:
        mock_db = MagicMock()
        mock_client.return_value.__getitem__.return_value = mock_db
        repo = Repository()
        repo.db = mock_db
        yield repo


@pytest.mark.asyncio
async def test_upsert_item(mock_repo):
    mock_repo.db.items.update_one = AsyncMock(return_value=None)
    item = {
        "name": "AK-47 | Redline",
        "source": "steam",
        "game": "cs2",
    }
    await mock_repo.upsert_item(item)
    mock_repo.db.items.update_one.assert_called_once()


@pytest.mark.asyncio
async def test_insert_price(mock_repo):
    mock_repo.db.prices.insert_one = AsyncMock(return_value=None)
    price = {
        "item_name": "AK-47 | Redline",
        "source": "steam",
        "price": 15.49,
        "volume": 120,
        "timestamp": datetime.now(timezone.utc),
    }
    await mock_repo.insert_price(price)
    mock_repo.db.prices.insert_one.assert_called_once_with(price)


@pytest.mark.asyncio
async def test_get_item_not_found(mock_repo):
    mock_repo.db.items.find_one = AsyncMock(return_value=None)
    result = await mock_repo.get_item("nieistniejący", "steam")
    assert result is None


@pytest.mark.asyncio
async def test_replace_listings_empty(mock_repo):
    mock_repo.db.listings.delete_many = AsyncMock(return_value=None)
    mock_repo.db.listings.insert_many = AsyncMock(return_value=None)
    await mock_repo.replace_listings("AK-47 | Redline", "steam", [])
    mock_repo.db.listings.delete_many.assert_called_once()
    mock_repo.db.listings.insert_many.assert_not_called()