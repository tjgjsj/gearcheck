"""Tests for pure list and due report construction."""

from datetime import date

from gearcheck.reports import (
    ItemRecord,
    build_due_report,
    build_list_report,
)
from gearcheck.status import InspectionRecord


TODAY = date(2025, 1, 10)


def test_list_report_sorts_names_and_computes_fields() -> None:
    items = [
        ItemRecord(2, "zebra", "tools", 10),
        ItemRecord(1, "Alpha", "safety", 5),
    ]
    inspections = {
        1: [InspectionRecord(1, date(2025, 1, 8), "pass")],
    }

    rows = build_list_report(items, inspections, TODAY)

    assert [row.name for row in rows] == ["Alpha", "zebra"]
    assert rows[0].category == "safety"
    assert rows[0].interval_days == 5
    assert rows[0].last_inspected == date(2025, 1, 8)
    assert rows[0].last_result == "pass"
    assert rows[0].next_due == date(2025, 1, 13)
    assert rows[0].status == "OK"
    assert rows[1].last_inspected is None
    assert rows[1].status == "NEVER INSPECTED"


def test_due_report_filters_and_sorts_by_attention_group_then_due_date() -> None:
    items = [
        ItemRecord(1, "Never", "general", 10),
        ItemRecord(2, "Failed", "general", 100),
        ItemRecord(3, "Overdue", "general", 10),
        ItemRecord(4, "Today", "general", 10),
        ItemRecord(5, "Soon", "general", 10),
        ItemRecord(6, "Later", "general", 10),
    ]
    inspections = {
        2: [InspectionRecord(1, date(2025, 1, 1), "fail")],
        3: [InspectionRecord(2, date(2024, 12, 29), "pass")],
        4: [InspectionRecord(3, date(2024, 12, 31), "pass")],
        5: [InspectionRecord(4, date(2025, 1, 3), "pass")],
        6: [InspectionRecord(5, date(2025, 1, 4), "pass")],
    }

    rows = build_due_report(items, inspections, TODAY, within_days=3)

    assert [row.name for row in rows] == [
        "Never",
        "Failed",
        "Overdue",
        "Today",
        "Soon",
    ]


def test_due_report_is_empty_when_no_items_need_attention() -> None:
    items = [ItemRecord(1, "Later", "general", 10)]
    inspections = {1: [InspectionRecord(1, date(2025, 1, 5), "pass")]}

    rows = build_due_report(items, inspections, TODAY, within_days=0)

    assert rows == []
