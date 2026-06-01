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
    with patch("scraper.parsers.steam.steam_session") as mock_session:
        mock_session.get_cookies.return_value = {}
        result = await parser.fetch_price_history("AK-47 | Redline (Field-Tested)")
        assert result == []


@pytest.mark.asyncio
async def test_fetch_price_history_with_session(parser):
    mock_cookies = {"sessionid": "abc123", "steamLoginSecure": "secure_token"}
    mock_response = {"success": True, "prices": [["Jun 01 2024 01: +0", 10.5, "3"]]}
    with patch("scraper.parsers.steam.steam_session") as mock_session:
        mock_session.get_cookies.return_value = mock_cookies
        with patch.object(parser, "_get", new=AsyncMock(return_value=mock_response)):
            result = await parser.fetch_price_history("AK-47 | Redline (Field-Tested)")
            assert len(result) == 1
            assert result[0]["price"] == 10.5
            assert result[0]["volume"] == 3


@pytest.mark.asyncio
async def test_fetch_price_history_session_refresh(parser):
    mock_cookies = {"sessionid": "abc123", "steamLoginSecure": "secure_token"}
    with patch("scraper.parsers.steam.steam_session") as mock_session:
        mock_session.get_cookies.return_value = mock_cookies
        mock_session.refresh.return_value = True
        # First call returns success=False (expired), second returns empty (after refresh)
        with patch.object(
            parser, "_get",
            new=AsyncMock(side_effect=[{"success": False}, {"success": True, "prices": []}])
        ):
            result = await parser.fetch_price_history("AK-47 | Redline (Field-Tested)")
            assert result == []
            mock_session.refresh.assert_called_once()