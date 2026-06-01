from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Item:
    name: str
    game: str
    item_type: str
    wear: Optional[str] = None
    float_value: Optional[float] = None
    icon_url: Optional[str] = None
    inspect_url: Optional[str] = None
    source: str = "steam"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return asdict(self)
