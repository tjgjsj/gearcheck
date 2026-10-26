"""Pure status calculation for equipment inspections."""

from dataclasses import dataclass
from datetime import date, timedelta
from collections.abc import Sequence


@dataclass(frozen=True)
class InspectionRecord:
    id: int
    date: date
    result: str


@dataclass(frozen=True)
class StatusResult:
    next_due: date | None
    status: str


def calculate_status(
    interval_days: int,
    inspections: Sequence[InspectionRecord],
    today: date,
) -> StatusResult:
    """Calculate an item's status without reading the clock or database."""
    if not inspections:
        return StatusResult(next_due=None, status="NEVER INSPECTED")

    latest = max(inspections, key=lambda inspection: (inspection.date, inspection.id))
    next_due = latest.date + timedelta(days=interval_days)

    if latest.result == "fail":
        return StatusResult(next_due=next_due, status="FAILED - OUT OF SERVICE")

    if today > next_due:
        overdue_days = (today - next_due).days
        return StatusResult(
            next_due=next_due,
            status=f"OVERDUE ({overdue_days} days)",
        )

    if today == next_due:
        return StatusResult(next_due=next_due, status="DUE TODAY")

    return StatusResult(next_due=next_due, status="OK")
