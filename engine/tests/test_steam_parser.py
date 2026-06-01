import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from scraper.parsers.steam import SteamParser


@pytest.fixture
def parser():
    return SteamParser()


def test_parse_wear_field_tested(parser):
    assert parser._parse_wear("AK-47 | Redline (Field-Tested)") == "Field-Tested"


def test_parse_wear_factory_new(parser):
    assert parser._parse_wear("AWP | Dragon Lore (Factory New)") == "Factory New"


def test_parse_wear_none(parser):
    assert parser._parse_wear("Sticker | Katowice 2014") is None


def test_parse_wear_battle_scarred(parser):
    assert parser._parse_wear("M4A4 | Howl (Battle-Scarred)") == "Battle-Scarred"


@pytest.mark.asyncio
async def test_search_items_empty_response(parser):
    with patch.object(parser, "_get", new=AsyncMock(return_value=None)):
        result = await parser.search_items("AK-47 Redline")
        assert result == []


@pytest.mark.asyncio
async def test_search_items_failed_response(parser):
    with patch.object(parser, "_get", new=AsyncMock(return_value={"success": False})):
        result = await parser.search_items("AK-47 Redline")
        assert result == []


@pytest.mark.asyncio
async def test_search_items_success(parser):
    mock_response = {
        "success": True,
        "results": [
            {
                "name": "AK-47 | Redline (Field-Tested)",
                "asset_description": {
                    "type": "Rifle",
                    "icon_url": "abc123",
                }
            }
        ]
    }
    with patch.object(parser, "_get", new=AsyncMock(return_value=mock_response)):
        result = await parser.search_items("AK-47 Redline")
        assert len(result) == 1
        assert result[0]["name"] == "AK-47 | Redline (Field-Tested)"
        assert result[0]["wear"] == "Field-Tested"


@pytest.mark.asyncio
async def test_fetch_price_history_no_cookies(parser):
    with patch("scraper.parsers.steam.STEAM_SESSION_ID", ""):
        with patch("scraper.parsers.steam.STEAM_LOGIN_SECURE", ""):
            result = await parser.fetch_price_history("AK-47 | Redline (Field-Tested)")
            assert result == []