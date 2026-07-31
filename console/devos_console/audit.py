from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


class AuditLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def write(self, event: str, **values: Any) -> None:
        record = {
            "at": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **values,
        }
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n")

    def recent(self, limit: int = 30) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        with self._lock, self.path.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()[-max(1, min(limit, 100)) :]
        records: list[dict[str, Any]] = []
        for line in lines:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                records.append(value)
        return list(reversed(records))
