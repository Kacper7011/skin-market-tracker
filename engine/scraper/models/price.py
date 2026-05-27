from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class Price:
    item_name: str
    source: str                      # np. "steam", "skinport"
    price: float                     # w USD
    volume: int                      # liczba transakcji
    currency: str = "USD"
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return asdict(self)