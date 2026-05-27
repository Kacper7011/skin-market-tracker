from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class ScrapeLog:
    source: str
    status: str                      # "success" | "error"
    items_scraped: int = 0
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    worker_id: Optional[int] = None
    started_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return asdict(self)