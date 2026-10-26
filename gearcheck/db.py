"""SQLite persistence for GearCheck."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3


SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL COLLATE NOCASE UNIQUE,
    category      TEXT NOT NULL DEFAULT 'general',
    interval_days INTEGER NOT NULL CHECK (interval_days > 0),
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inspections (
    id      INTEGER PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    date    TEXT NOT NULL,
    result  TEXT NOT NULL CHECK (result IN ('pass', 'fail')),
    notes   TEXT
);

CREATE INDEX IF NOT EXISTS inspections_item_date_id
    ON inspections(item_id, date DESC, id DESC);
"""


@contextmanager
def open_database(path: str | Path) -> Iterator[sqlite3.Connection]:
    """Open a database, ensure the schema exists, and close it on exit."""
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        connection.executescript(SCHEMA)
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def insert_item(
    connection: sqlite3.Connection,
    name: str,
    category: str,
    interval_days: int,
    created_at: str,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO items (name, category, interval_days, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (name, category, interval_days, created_at),
    )
    return int(cursor.lastrowid)


def get_item_by_name(
    connection: sqlite3.Connection, name: str
) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM items WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchone()


def get_items(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(connection.execute("SELECT * FROM items ORDER BY name COLLATE NOCASE"))


def insert_inspection(
    connection: sqlite3.Connection,
    item_id: int,
    inspection_date: str,
    result: str,
    notes: str | None,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO inspections (item_id, date, result, notes)
        VALUES (?, ?, ?, ?)
        """,
        (item_id, inspection_date, result, notes),
    )
    return int(cursor.lastrowid)


def get_inspections_for_item(
    connection: sqlite3.Connection, item_id: int
) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            """
            SELECT * FROM inspections
            WHERE item_id = ?
            ORDER BY date DESC, id DESC
            """,
            (item_id,),
        )
    )


def get_all_inspections(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            "SELECT * FROM inspections ORDER BY item_id, date DESC, id DESC"
        )
    )


def delete_item(connection: sqlite3.Connection, item_id: int) -> None:
    connection.execute("DELETE FROM items WHERE id = ?", (item_id,))
