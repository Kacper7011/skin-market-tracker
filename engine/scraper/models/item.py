from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class Item:
    name: str                        # np. "AK-47 | Redline"
    game: str                        # np. "cs2"
    item_type: str                   # np. "Rifle", "Knife", "Sticker"
    wear: Optional[str] = None       # np. "Field-Tested"
    float_value: Optional[float] = None
    icon_url: Optional[str] = None
    inspect_url: Optional[str] = None
    source: str = "steam"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return asdict(self)