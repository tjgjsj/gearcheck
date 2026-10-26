"""Tests for pure status calculation."""

from datetime import date

import pytest

from gearcheck.status import InspectionRecord, calculate_status


TODAY = date(2025, 1, 11)


def test_never_inspected_status() -> None:
    result = calculate_status(10, [], TODAY)

    assert result.status == "NEVER INSPECTED"
    assert result.next_due is None


def test_latest_failure_is_out_of_service() -> None:
    result = calculate_status(
        10,
        [InspectionRecord(1, date(2025, 1, 1), "fail")],
        TODAY,
    )

    assert result.status == "FAILED - OUT OF SERVICE"
    assert result.next_due == date(2025, 1, 11)


def test_overdue_status_includes_number_of_days() -> None:
    result = calculate_status(
        10,
        [InspectionRecord(1, date(2025, 1, 1), "pass")],
        date(2025, 1, 12),
    )

    assert result.status == "OVERDUE (1 days)"
    assert result.next_due == date(2025, 1, 11)


def test_due_today_status() -> None:
    result = calculate_status(
        10,
        [InspectionRecord(1, date(2025, 1, 1), "pass")],
        date(2025, 1, 11),
    )

    assert result.status == "DUE TODAY"


def test_future_due_status_is_ok() -> None:
    result = calculate_status(
        10,
        [InspectionRecord(1, date(2025, 1, 2), "pass")],
        TODAY,
    )

    assert result.status == "OK"
    assert result.next_due == date(2025, 1, 12)


def test_latest_is_selected_by_date_not_insertion_id() -> None:
    result = calculate_status(
        10,
        [
            InspectionRecord(99, date(2025, 1, 1), "fail"),
            InspectionRecord(2, date(2025, 1, 4), "pass"),
        ],
        TODAY,
    )

    assert result.status == "OK"
    assert result.next_due == date(2025, 1, 14)


@pytest.mark.parametrize(
    ("latest_result", "expected_status"),
    [("pass", "DUE TODAY"), ("fail", "FAILED - OUT OF SERVICE")],
)
def test_same_day_tie_uses_most_recent_log(
    latest_result: str, expected_status: str
) -> None:
    inspections = [
        InspectionRecord(1, date(2025, 1, 1), "fail"),
        InspectionRecord(2, date(2025, 1, 1), latest_result),
    ]

    result = calculate_status(10, inspections, TODAY)

    assert result.status == expected_status
