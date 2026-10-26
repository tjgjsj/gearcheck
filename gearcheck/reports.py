"""Pure list and due report construction."""

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
