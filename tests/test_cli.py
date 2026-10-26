"""Tests for command-line behavior."""

from datetime import date, timedelta
from pathlib import Path
import subprocess
import sys

import pytest

from gearcheck.cli import main
from gearcheck.db import (
    get_inspections_for_item,
    get_item_by_name,
    insert_inspection,
    insert_item,
    open_database,
)


def invoke(db_path: Path, *arguments: str) -> int:
    return main(["--db", str(db_path), *arguments])


def assert_user_error(stderr: str, expected: str) -> None:
    lines = stderr.strip().splitlines()
    assert lines == [expected]
    assert "Traceback" not in stderr


@pytest.fixture
def report_today(monkeypatch: pytest.MonkeyPatch) -> date:
    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return cls(2025, 1, 10)

    monkeypatch.setattr("gearcheck.cli.date", FixedDate)
    return FixedDate.today()


@pytest.fixture
def report_database(db_path: Path, report_today: date) -> Path:
    equipment = [
        ("Never", None, "pass"),
        ("Failed", -3, "fail"),
        ("Overdue", -1, "pass"),
        ("Today", 0, "pass"),
        ("Near", 3, "pass"),
        ("Soon", 7, "pass"),
        ("Later", 8, "pass"),
    ]
    with open_database(db_path) as connection:
        for name, due_offset, result in equipment:
            item_id = insert_item(connection, name, "general", 10, report_today.isoformat())
            if due_offset is not None:
                inspection_day = report_today + timedelta(days=due_offset - 10)
                insert_inspection(connection, item_id, inspection_day.isoformat(), result, None)
    return db_path


def test_add_item_output_and_defaults(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = invoke(db_path, "add", "Pump", "--interval", "30")

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "Added: Pump (every 30 days)"
    with open_database(db_path) as connection:
        item = get_item_by_name(connection, "pump")
        assert item is not None
        assert item["category"] == "general"
        assert item["interval_days"] == 30
        assert item["created_at"] == date.today().isoformat()


def test_duplicate_add_is_case_insensitive_user_error(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert invoke(db_path, "add", "Pump", "--interval", "30") == 0
    capsys.readouterr()

    exit_code = invoke(db_path, "add", "pUMP", "--interval", "10")
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert_user_error(captured.err, "Item already exists: pUMP.")


@pytest.mark.parametrize("interval", ["0", "-2", "many"])
def test_bad_interval_is_application_user_error(
    db_path: Path,
    capsys: pytest.CaptureFixture[str],
    interval: str,
) -> None:
    exit_code = invoke(db_path, "add", "Pump", "--interval", interval)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert_user_error(captured.err, "--interval must be a positive integer.")


def test_inspect_unknown_item_is_user_error(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = invoke(db_path, "inspect", "Missing", "--result", "pass")
    captured = capsys.readouterr()

    assert exit_code == 1
    assert_user_error(captured.err, "Unknown item: Missing.")


@pytest.mark.parametrize("inspection_date", ["2025-02-30", "20250101"])
def test_invalid_inspection_date_is_user_error(
    db_path: Path,
    capsys: pytest.CaptureFixture[str],
    inspection_date: str,
) -> None:
    invoke(db_path, "add", "Pump", "--interval", "10")

    exit_code = invoke(
        db_path,
        "inspect",
        "Pump",
        "--result",
        "pass",
        "--date",
        inspection_date,
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert_user_error(
        captured.err,
        f"Invalid date: {inspection_date} (expected YYYY-MM-DD).",
    )


def test_future_inspection_date_is_user_error(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    invoke(db_path, "add", "Pump", "--interval", "10")
    future_date = (date.today() + timedelta(days=1)).isoformat()

    exit_code = invoke(
        db_path, "inspect", "Pump", "--result", "pass", "--date", future_date
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert_user_error(captured.err, "Inspection date cannot be in the future.")


def test_names_are_case_insensitive_across_commands(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert invoke(db_path, "add", "Pump", "--interval", "10") == 0
    assert invoke(db_path, "inspect", "pUmP", "--result", "pass") == 0
    assert invoke(db_path, "history", "PUMP") == 0
    history = capsys.readouterr().out
    assert "History: Pump" in history

    assert invoke(db_path, "remove", "pump", "--yes") == 0
    with open_database(db_path) as connection:
        assert get_item_by_name(connection, "Pump") is None


def test_inspect_defaults_date_to_today(db_path: Path) -> None:
    invoke(db_path, "add", "Pump", "--interval", "10")

    assert invoke(db_path, "inspect", "Pump", "--result", "pass") == 0
    with open_database(db_path) as connection:
        item = get_item_by_name(connection, "Pump")
        assert item is not None
        inspections = get_inspections_for_item(connection, item["id"])
        assert inspections[0]["date"] == date.today().isoformat()


@pytest.mark.parametrize("within", ["one", "-1"])
def test_invalid_within_is_user_error(
    db_path: Path,
    capsys: pytest.CaptureFixture[str],
    within: str,
) -> None:
    exit_code = invoke(db_path, "due", "--within", within)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert_user_error(captured.err, "--within must be a non-negative integer.")


def test_due_empty_message(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert invoke(db_path, "due") == 0

    assert capsys.readouterr().out.strip() == "Nothing due."


def test_list_colors_only_the_specified_statuses(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    today = date.today()
    items = [
        ("Okay", 10, today),
        ("Due", 10, today - timedelta(days=10)),
        ("Late", 10, today - timedelta(days=11)),
        ("Failed", 10, today),
        ("Never", 10, None),
    ]
    for name, interval, inspection_day in items:
        assert invoke(db_path, "add", name, "--interval", str(interval)) == 0
        if inspection_day is not None:
            result = "fail" if name == "Failed" else "pass"
            assert invoke(
                db_path,
                "inspect",
                name,
                "--result",
                result,
                "--date",
                inspection_day.isoformat(),
            ) == 0
    capsys.readouterr()

    assert invoke(db_path, "list") == 0
    listing = capsys.readouterr().out

    assert "\033[32mOK\033[0m" in listing
    assert "\033[33mDUE TODAY\033[0m" in listing
    assert "\033[31mOVERDUE (1 days)\033[0m" in listing
    assert "\033[31mFAILED - OUT OF SERVICE\033[0m" in listing
    assert "NEVER INSPECTED" in listing
    assert "\033[0mNEVER INSPECTED" not in listing

    assert invoke(db_path, "due") == 0
    due_output = capsys.readouterr().out
    assert "\033[" not in due_output


def test_remove_without_yes_refuses_and_leaves_item_unchanged(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    invoke(db_path, "add", "Pump", "--interval", "10")

    exit_code = invoke(db_path, "remove", "Pump")
    captured = capsys.readouterr()

    assert exit_code == 1
    assert_user_error(captured.err, "Refusing to remove Pump without --yes.")
    with open_database(db_path) as connection:
        assert get_item_by_name(connection, "Pump") is not None


def test_history_same_day_ties_show_most_recent_first(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    invoke(db_path, "add", "Pump", "--interval", "10")
    today = date.today().isoformat()
    invoke(db_path, "inspect", "Pump", "--result", "pass", "--date", today)
    invoke(db_path, "inspect", "Pump", "--result", "fail", "--date", today)

    assert invoke(db_path, "history", "Pump") == 0
    output = capsys.readouterr().out
    history = output.split("DATE       | RESULT | NOTES\n", maxsplit=1)[1]
    assert history.index("fail") < history.index("pass")


def test_argparse_syntax_errors_keep_exit_code_two(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as missing_option:
        main(["--db", str(db_path), "add", "Pump"])
    assert missing_option.value.code == 2
    assert "usage:" in capsys.readouterr().err

    with pytest.raises(SystemExit) as invalid_result:
        main(["--db", str(db_path), "inspect", "Pump", "--result", "maybe"])
    assert invalid_result.value.code == 2
    assert "usage:" in capsys.readouterr().err


def test_module_entrypoint_uses_custom_database(db_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "gearcheck",
            "--db",
            str(db_path),
            "add",
            "Pump",
            "--interval",
            "10",
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "Added: Pump (every 10 days)"
    assert result.stderr == ""


def test_report_stdout_defaults_to_seven_days(
    report_database: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert invoke(report_database, "report") == 0
    captured = capsys.readouterr()

    assert captured.err == ""
    assert captured.out == """# GearCheck Inspection Report
Generated: 2025-01-10

## Summary

- Total: 7
- Never inspected: 1
- Failed: 1
- Overdue: 1
- Due today: 1
- Due soon: 2
- OK: 1

## Needs Attention

| Name | Category | Status | Next Due |
| --- | --- | --- | --- |
| Never | general | NEVER INSPECTED | now |
| Failed | general | FAILED - OUT OF SERVICE | 2025-01-07 |
| Overdue | general | OVERDUE (1 days) | 2025-01-09 |
| Today | general | DUE TODAY | 2025-01-10 |
| Near | general | OK | 2025-01-13 |
| Soon | general | OK | 2025-01-17 |

## All Equipment

| Name | Category | Status | Next Due |
| --- | --- | --- | --- |
| Failed | general | FAILED - OUT OF SERVICE | 2025-01-07 |
| Later | general | OK | 2025-01-18 |
| Near | general | OK | 2025-01-13 |
| Never | general | NEVER INSPECTED | now |
| Overdue | general | OVERDUE (1 days) | 2025-01-09 |
| Soon | general | OK | 2025-01-17 |
| Today | general | DUE TODAY | 2025-01-10 |
"""
    assert "\033[" not in captured.out


@pytest.mark.parametrize(
    ("soon", "due_soon", "okay", "attention_names"),
    [
        ("0", 0, 3, ["Never", "Failed", "Overdue", "Today"]),
        ("3", 1, 2, ["Never", "Failed", "Overdue", "Today", "Near"]),
    ],
)
def test_report_soon_override(
    report_database: Path,
    capsys: pytest.CaptureFixture[str],
    soon: str,
    due_soon: int,
    okay: int,
    attention_names: list[str],
) -> None:
    assert invoke(report_database, "report", "--soon", soon) == 0
    captured = capsys.readouterr()

    assert captured.err == ""
    assert f"- Due soon: {due_soon}\n" in captured.out
    assert f"- OK: {okay}\n" in captured.out
    attention = captured.out.split("## Needs Attention\n", maxsplit=1)[1].split(
        "## All Equipment\n", maxsplit=1
    )[0]
    rows = attention.strip().splitlines()[2:]
    assert [row.split("|")[1].strip() for row in rows] == attention_names


def test_report_out_writes_file(
    report_database: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert invoke(report_database, "report", "--soon", "3") == 0
    expected = capsys.readouterr().out
    output_path = tmp_path / "inspection report.md"

    assert invoke(report_database, "report", "--soon", "3", "--out", str(output_path)) == 0
    captured = capsys.readouterr()

    assert output_path.read_text(encoding="utf-8") == expected
    assert captured.out == f"Report written to {output_path}\n"
    assert captured.err == ""


@pytest.mark.parametrize("soon", ["many", "-1"])
def test_invalid_report_soon_is_user_error(
    db_path: Path, capsys: pytest.CaptureFixture[str], soon: str
) -> None:
    exit_code = invoke(db_path, "report", "--soon", soon)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert_user_error(captured.err, "--soon must be a non-negative integer.")
    assert not db_path.exists()
