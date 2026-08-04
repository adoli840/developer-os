from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MEMO_PROJECTS = (
    ("developer-os", "OS"),
    ("btest", "bTest"),
    ("oa", "OA"),
    ("gaia", "Gaia"),
)
MAX_MEMO_BYTES = 256 * 1024


class MemoStore:
    def __init__(self, database: Path) -> None:
        self.database = database
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute("PRAGMA journal_mode = WAL")
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS project_memos (
                        project TEXT PRIMARY KEY,
                        content TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
        try:
            os.chmod(self.database, 0o600)
        except OSError:
            pass

    @staticmethod
    def _validate_project(project: str) -> str:
        slug = str(project).strip().lower()
        if slug not in {item[0] for item in MEMO_PROJECTS}:
            raise ValueError("Unknown memo project.")
        return slug

    @staticmethod
    def _validate_content(content: object) -> str:
        if not isinstance(content, str):
            raise ValueError("Memo content must be text.")
        if len(content.encode("utf-8")) > MAX_MEMO_BYTES:
            raise ValueError("Memo content exceeds 256 KB.")
        return content

    def list_all(self) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            rows = {
                str(row["project"]): row
                for row in connection.execute(
                    "SELECT project, content, updated_at FROM project_memos"
                )
            }
        return {
            "items": [
                {
                    "project": slug,
                    "name": name,
                    "content": str(rows[slug]["content"]) if slug in rows else "",
                    "updated_at": str(rows[slug]["updated_at"]) if slug in rows else None,
                }
                for slug, name in MEMO_PROJECTS
            ]
        }

    def save(self, project: str, content: object) -> dict[str, Any]:
        slug = self._validate_project(project)
        value = self._validate_content(content)
        updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO project_memos (project, content, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(project) DO UPDATE SET
                        content = excluded.content,
                        updated_at = excluded.updated_at
                    """,
                    (slug, value, updated_at),
                )
        return {
            "project": slug,
            "name": dict(MEMO_PROJECTS)[slug],
            "content": value,
            "updated_at": updated_at,
        }
