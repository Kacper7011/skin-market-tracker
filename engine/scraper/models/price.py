from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


@dataclass
class Price:
    item_name: str
    source: str
    price: float
    volume: int
    currency: str = "USD"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return asdict(self)
