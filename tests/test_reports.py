"""Tests for pure list, due, and Markdown report construction."""

from datetime import date, timedelta

import pytest

from gearcheck.reports import (
    ItemRecord,
    build_due_report,
    build_list_report,
    build_markdown_report,
)
from gearcheck.status import InspectionRecord


TODAY = date(2025, 1, 10)
_Equipment = tuple[list[ItemRecord], dict[int, list[InspectionRecord]]]


@pytest.fixture
def report_equipment() -> _Equipment:
    items = [
        ItemRecord(1, "Never", "general", 10),
        ItemRecord(2, "Failed", "safety", 10),
        ItemRecord(3, "Overdue", "tools", 10),
        ItemRecord(4, "Today", "general", 10),
        ItemRecord(5, "Soon", "safety", 10),
        ItemRecord(6, "later", "tools", 10),
    ]
    inspections = {
        2: [InspectionRecord(1, date(2024, 12, 25), "fail")],
        3: [InspectionRecord(2, date(2024, 12, 29), "pass")],
        4: [InspectionRecord(3, date(2024, 12, 31), "pass")],
        5: [InspectionRecord(4, date(2025, 1, 3), "pass")],
        6: [InspectionRecord(5, date(2025, 1, 8), "pass")],
    }
    return items, inspections


def _summary_counts(report: str) -> dict[str, int]:
    summary = report.split("## Summary\n", maxsplit=1)[1].split("\n## ", maxsplit=1)[0]
    counts = {}
    for line in summary.splitlines():
        if line.startswith("- "):
            label, count = line[2:].split(": ", maxsplit=1)
            counts[label] = int(count)
    return counts


def _table_rows(report: str, section: str) -> list[list[str]]:
    table = report.split(f"## {section}\n", maxsplit=1)[1].split("\n## ", maxsplit=1)[0]
    lines = [line for line in table.splitlines() if line.startswith("|")]
    return [[cell.strip() for cell in line.strip("|").split("|")] for line in lines[2:]]


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


def test_markdown_report_counts_one_item_per_category(report_equipment: _Equipment) -> None:
    items, inspections = report_equipment

    counts = _summary_counts(build_markdown_report(items, inspections, TODAY))

    assert counts == {
        "Total": 6,
        "Never inspected": 1,
        "Failed": 1,
        "Overdue": 1,
        "Due today": 1,
        "Due soon": 1,
        "OK": 1,
    }


@pytest.mark.parametrize("copies", [0, 1, 2])
@pytest.mark.parametrize("soon_days", [0, 7])
def test_markdown_report_category_counts_sum_to_total(
    report_equipment: _Equipment, copies: int, soon_days: int
) -> None:
    items, inspections = report_equipment
    expanded_items = []
    expanded_inspections = {}
    for copy in range(copies):
        for item in items:
            item_id = item.id + copy * len(items)
            expanded_items.append(
                ItemRecord(item_id, f"{item.name} {copy}", item.category, item.interval_days)
            )
            expanded_inspections[item_id] = inspections.get(item.id, [])

    counts = _summary_counts(
        build_markdown_report(expanded_items, expanded_inspections, TODAY, soon_days)
    )

    assert set(counts) == {
        "Total", "Never inspected", "Failed", "Overdue", "Due today", "Due soon", "OK"
    }
    assert counts["Total"] == len(items) * copies
    assert sum(count for label, count in counts.items() if label != "Total") == counts["Total"]


@pytest.mark.parametrize(
    ("soon_days", "due_soon", "okay"), [(7, 2, 1), (0, 0, 3)]
)
def test_markdown_report_soon_boundaries(soon_days: int, due_soon: int, okay: int) -> None:
    items = []
    inspections = {}
    for item_id, offset in enumerate((0, 1, 7, 8), start=1):
        items.append(ItemRecord(item_id, f"Due {offset}", "general", 10))
        inspections[item_id] = [
            InspectionRecord(item_id, TODAY + timedelta(days=offset - 10), "pass")
        ]

    counts = _summary_counts(build_markdown_report(items, inspections, TODAY, soon_days))

    assert counts == {
        "Total": 4,
        "Never inspected": 0,
        "Failed": 0,
        "Overdue": 0,
        "Due today": 1,
        "Due soon": due_soon,
        "OK": okay,
    }


def test_markdown_report_attention_membership_and_order(report_equipment: _Equipment) -> None:
    items, inspections = report_equipment

    report = build_markdown_report(items, inspections, TODAY)
    names = [row[0] for row in _table_rows(report, "Needs Attention")]

    assert names == ["Never", "Failed", "Overdue", "Today", "Soon"]
    assert names == [
        row.name for row in build_due_report(items, inspections, TODAY, within_days=7)
    ]


def test_markdown_report_format_and_all_equipment_order(report_equipment: _Equipment) -> None:
    items, inspections = report_equipment

    report = build_markdown_report(items, inspections, TODAY)

    assert report == """# GearCheck Inspection Report
Generated: 2025-01-10

## Summary

- Total: 6
- Never inspected: 1
- Failed: 1
- Overdue: 1
- Due today: 1
- Due soon: 1
- OK: 1

## Needs Attention

| Name | Category | Status | Next Due |
| --- | --- | --- | --- |
| Never | general | NEVER INSPECTED | now |
| Failed | safety | FAILED - OUT OF SERVICE | 2025-01-04 |
| Overdue | tools | OVERDUE (2 days) | 2025-01-08 |
| Today | general | DUE TODAY | 2025-01-10 |
| Soon | safety | OK | 2025-01-13 |

## All Equipment

| Name | Category | Status | Next Due |
| --- | --- | --- | --- |
| Failed | safety | FAILED - OUT OF SERVICE | 2025-01-04 |
| later | tools | OK | 2025-01-18 |
| Never | general | NEVER INSPECTED | now |
| Overdue | tools | OVERDUE (2 days) | 2025-01-08 |
| Soon | safety | OK | 2025-01-13 |
| Today | general | DUE TODAY | 2025-01-10 |
"""
    assert "\033[" not in report


def test_markdown_report_empty_equipment() -> None:
    report = build_markdown_report([], {}, TODAY)

    assert _summary_counts(report) == {
        "Total": 0,
        "Never inspected": 0,
        "Failed": 0,
        "Overdue": 0,
        "Due today": 0,
        "Due soon": 0,
        "OK": 0,
    }
    assert report.count("| Name | Category | Status | Next Due |") == 2
    assert report.count("| --- | --- | --- | --- |") == 2
    assert _table_rows(report, "Needs Attention") == []
    assert _table_rows(report, "All Equipment") == []
