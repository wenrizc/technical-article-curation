from __future__ import annotations

import sqlite3
from threading import RLock

from tac.infrastructure.db import store as db


class TagVocabularyCache:
    def __init__(self) -> None:
        self._lock = RLock()
        self._names: tuple[str, ...] = ()

    def refresh(self, conn: sqlite3.Connection) -> tuple[str, ...]:
        names = tuple(db.active_tag_names(conn))
        with self._lock:
            self._names = names
        return names

    def names(self) -> tuple[str, ...]:
        with self._lock:
            return self._names
