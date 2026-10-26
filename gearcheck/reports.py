"""Pure list, due, and Markdown report construction."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from .status import InspectionRecord, StatusResult, calculate_status


@dataclass(frozen=True)
class ItemRecord:
    id: int
    name: str
    category: str
    interval_days: int


@dataclass(frozen=True)
class ReportRow:
    item_id: int
    name: str
    category: str
    interval_days: int
    last_inspected: date | None
    last_result: str | None
    next_due: date | None
    status: str


_ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def _name_sort_key(name: str) -> str:
    return name.translate(_ASCII_LOWER)


def _make_row(
    item: ItemRecord,
    inspections: Sequence[InspectionRecord],
    today: date,
) -> ReportRow:
    result: StatusResult = calculate_status(item.interval_days, inspections, today)
    latest = max(inspections, key=lambda inspection: (inspection.date, inspection.id), default=None)
    return ReportRow(
        item_id=item.id,
        name=item.name,
        category=item.category,
        interval_days=item.interval_days,
        last_inspected=latest.date if latest else None,
        last_result=latest.result if latest else None,
        next_due=result.next_due,
        status=result.status,
    )


def build_list_report(
    items: Sequence[ItemRecord],
    inspections_by_item: Mapping[int, Sequence[InspectionRecord]],
    today: date,
) -> list[ReportRow]:
    rows = [
        _make_row(item, inspections_by_item.get(item.id, ()), today)
        for item in items
    ]
    return sorted(rows, key=lambda row: _name_sort_key(row.name))


def build_due_report(
    items: Sequence[ItemRecord],
    inspections_by_item: Mapping[int, Sequence[InspectionRecord]],
    today: date,
    within_days: int,
) -> list[ReportRow]:
    rows = build_list_report(items, inspections_by_item, today)
    due_rows = [
        row
        for row in rows
        if row.last_inspected is None
        or row.last_result == "fail"
        or row.status.startswith("OVERDUE")
        or (
            row.next_due is not None
            and (row.next_due - today).days <= within_days
        )
    ]

    def sort_key(row: ReportRow) -> tuple[int, date, str]:
        if row.last_inspected is None:
            group = 0
        elif row.last_result == "fail":
            group = 1
        else:
            group = 2
        return (
            group,
            row.next_due or date.min,
            _name_sort_key(row.name),
        )

    return sorted(due_rows, key=sort_key)


def _markdown_table(rows: Sequence[ReportRow]) -> str:
    lines = [
        "| Name | Category | Status | Next Due |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        next_due = row.next_due.isoformat() if row.next_due else "now"
        lines.append(f"| {row.name} | {row.category} | {row.status} | {next_due} |")
    return "\n".join(lines)


def build_markdown_report(
    items: Sequence[ItemRecord],
    inspections_by_item: Mapping[int, Sequence[InspectionRecord]],
    today: date,
    soon_days: int = 7,
) -> str:
    """Build a Markdown report without reading the clock or database."""
    rows = build_list_report(items, inspections_by_item, today)
    attention_rows = build_due_report(items, inspections_by_item, today, soon_days)
    counts = {
        "Never inspected": 0,
        "Failed": 0,
        "Overdue": 0,
        "Due today": 0,
        "Due soon": 0,
        "OK": 0,
    }
    for row in rows:
        if row.status == "NEVER INSPECTED":
            category = "Never inspected"
        elif row.status == "FAILED - OUT OF SERVICE":
            category = "Failed"
        elif row.status.startswith("OVERDUE"):
            category = "Overdue"
        elif row.status == "DUE TODAY":
            category = "Due today"
        elif (
            row.status == "OK"
            and row.next_due is not None
            and 1 <= (row.next_due - today).days <= soon_days
        ):
            category = "Due soon"
        else:
            category = "OK"
        counts[category] += 1

    lines = [
        "# GearCheck Inspection Report",
        f"Generated: {today.isoformat()}",
        "",
        "## Summary",
        "",
        f"- Total: {len(rows)}",
    ]
    lines.extend(f"- {category}: {count}" for category, count in counts.items())
    lines.extend(
        [
            "",
            "## Needs Attention",
            "",
            _markdown_table(attention_rows),
            "",
            "## All Equipment",
            "",
            _markdown_table(rows),
        ]
    )
    return "\n".join(lines) + "\n"
