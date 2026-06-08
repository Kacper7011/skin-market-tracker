from abc import ABC, abstractmethod


class BaseParser(ABC):
    source: str = ""

    @abstractmethod
    async def fetch_price_history(self, item_name: str) -> list[dict]:
        """Pobiera historię cen dla danego przedmiotu."""
        pass

    @abstractmethod
    async def search_items(self, query: str, count: int = 10) -> list[dict]:
        """Wyszukuje przedmioty po nazwie."""
        pass
