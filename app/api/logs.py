import logging
from collections import deque
from datetime import datetime

from fastapi import APIRouter, Query

router = APIRouter()


class MemoryLogHandler(logging.Handler):
    """Keep last N log lines in memory for the UI."""

    def __init__(self, max_lines: int = 500):
        super().__init__()
        self.buffer: deque[dict] = deque(maxlen=max_lines)

    def emit(self, record: logging.LogRecord):
        self.buffer.append({
            "ts": datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        })


log_handler = MemoryLogHandler(max_lines=500)
log_handler.setLevel(logging.INFO)
log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

logging.getLogger().addHandler(log_handler)
logging.getLogger("uvicorn.access").addHandler(log_handler)


@router.get("/logs")
def get_logs(limit: int = Query(default=100, le=500), level: str = Query(default=None)):
    entries = list(log_handler.buffer)
    if level:
        entries = [e for e in entries if e["level"] == level.upper()]
    return list(reversed(entries[-limit:]))
