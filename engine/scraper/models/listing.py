from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Listing:
    item_name: str
    source: str
    price: float
    quantity: int
    currency: str = "USD"
    wear: Optional[str] = None
    float_value: Optional[float] = None
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return asdict(self)
