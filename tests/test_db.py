"""Tests for SQLite persistence and constraints."""

import sqlite3

import pytest

from gearcheck.db import (
    delete_item,
    get_inspections_for_item,
    get_item_by_name,
    insert_inspection,
    insert_item,
)


def test_name_lookup_is_ascii_case_insensitive(connection: sqlite3.Connection) -> None:
    item_id = insert_item(connection, "Pump A", "general", 30, "2025-01-01")

    item = get_item_by_name(connection, "pUmP a")

    assert item is not None
    assert item["id"] == item_id
    assert item["category"] == "general"


def test_unique_name_constraint_is_ascii_case_insensitive(
    connection: sqlite3.Connection,
) -> None:
    insert_item(connection, "Pump A", "general", 30, "2025-01-01")

    with pytest.raises(sqlite3.IntegrityError):
        insert_item(connection, "pUMP a", "general", 10, "2025-01-01")


def test_item_interval_must_be_positive(connection: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        insert_item(connection, "Pump A", "general", 0, "2025-01-01")


def test_inspections_order_by_date_then_log_order(
    connection: sqlite3.Connection,
) -> None:
    item_id = insert_item(connection, "Pump A", "general", 30, "2025-01-01")
    insert_inspection(connection, item_id, "2025-01-02", "pass", None)
    insert_inspection(connection, item_id, "2025-01-03", "pass", None)
    insert_inspection(connection, item_id, "2025-01-03", "fail", "second log")

    inspections = get_inspections_for_item(connection, item_id)

    assert [(row["date"], row["result"]) for row in inspections] == [
        ("2025-01-03", "fail"),
        ("2025-01-03", "pass"),
        ("2025-01-02", "pass"),
    ]


def test_removing_item_cascades_to_inspections(
    connection: sqlite3.Connection,
) -> None:
    item_id = insert_item(connection, "Pump A", "general", 30, "2025-01-01")
    insert_inspection(connection, item_id, "2025-01-02", "pass", None)

    delete_item(connection, item_id)

    assert connection.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM inspections").fetchone()[0] == 0
