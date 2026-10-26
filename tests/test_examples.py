"""Executable examples for realistic GearCheck workflows."""

from datetime import date, timedelta
from pathlib import Path
import subprocess
import sys

import pytest

from examples.demo import SCENARIOS, main as demo_main, seed_database
from gearcheck.cli import main
from gearcheck.db import (
    get_all_inspections,
    get_inspections_for_item,
    get_item_by_name,
    get_items,
    open_database,
)
from gearcheck.reports import ItemRecord, build_list_report, build_markdown_report
from gearcheck.status import InspectionRecord


@pytest.fixture
def demo_today(monkeypatch: pytest.MonkeyPatch) -> date:
    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return cls(2026, 10, 26)

    monkeypatch.setattr("examples.demo.date", FixedDate)
    monkeypatch.setattr("gearcheck.cli.date", FixedDate)
    return FixedDate.today()


@pytest.fixture
def workshop_database(db_path: Path, demo_today: date) -> Path:
    seed_database(db_path, "workshop", demo_today)
    return db_path


def _report_data(
    db_path: Path,
) -> tuple[list[ItemRecord], dict[int, list[InspectionRecord]]]:
    with open_database(db_path) as connection:
        items = [
            ItemRecord(row["id"], row["name"], row["category"], row["interval_days"])
            for row in get_items(connection)
        ]
        inspections: dict[int, list[InspectionRecord]] = {}
        for row in get_all_inspections(connection):
            inspections.setdefault(row["item_id"], []).append(
                InspectionRecord(row["id"], date.fromisoformat(row["date"]), row["result"])
            )
    return items, inspections


@pytest.mark.parametrize("scenario", SCENARIOS)
@pytest.mark.parametrize("today", [date(2026, 10, 26), date(2024, 3, 1), date(2027, 1, 1)])
def test_each_demo_covers_all_report_categories(
    db_path: Path, scenario: str, today: date
) -> None:
    assert seed_database(db_path, scenario, today) == 6
    items, inspections = _report_data(db_path)

    assert {item.name for item in items} == {item.name for item in SCENARIOS[scenario]}
    assert all(
        inspection.date <= today
        for history in inspections.values()
        for inspection in history
    )
    with open_database(db_path) as connection:
        assert all(row["created_at"] == today.isoformat() for row in get_items(connection))
        assert all(row["notes"] for row in get_all_inspections(connection))

    report = build_markdown_report(items, inspections, today)
    assert "- Total: 6\n" in report
    for category in ("Never inspected", "Failed", "Overdue", "Due today", "Due soon", "OK"):
        assert f"- {category}: 1\n" in report


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_demo_module_entrypoint(db_path: Path, scenario: str) -> None:
    result = subprocess.run(
        [
            sys.executable, "-m", "examples.demo", "--db", str(db_path),
            "--scenario", scenario,
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout == f"Created {scenario} demo: 6 items in {db_path}\n"
    assert result.stderr == ""
    with open_database(db_path) as connection:
        assert len(get_items(connection)) == 6


@pytest.mark.parametrize("contents", [b"", b"Do not replace this file.\n"])
def test_demo_refuses_existing_files(
    db_path: Path, capsys: pytest.CaptureFixture[str], contents: bytes
) -> None:
    db_path.write_bytes(contents)

    assert demo_main(["--db", str(db_path)]) == 1
    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == f"Refusing to overwrite existing path: {db_path}\n"
    assert db_path.read_bytes() == contents


def test_demo_refuses_existing_database(
    workshop_database: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    original = workshop_database.read_bytes()

    assert demo_main(["--db", str(workshop_database), "--scenario", "safety"]) == 1

    assert "Refusing to overwrite" in capsys.readouterr().err
    assert workshop_database.read_bytes() == original


def test_demo_requires_explicit_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as error:
        demo_main([])

    assert error.value.code == 2
    assert "--db" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_demo_rejects_unknown_scenario_without_creating_database(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as error:
        demo_main(["--db", str(db_path), "--scenario", "unknown"])

    assert error.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
    assert not db_path.exists()


def test_demo_reports_missing_parent_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = tmp_path / "missing" / "example.db"

    assert demo_main(["--db", str(db_path)]) == 1
    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err.startswith("Cannot create demo database:")
    assert "Traceback" not in captured.err
    assert not db_path.exists()


def test_workshop_report_matches_checked_in_example(
    workshop_database: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--db", str(workshop_database), "report"]) == 0
    captured = capsys.readouterr()
    example = Path(__file__).resolve().parents[1] / "examples" / "workshop-report.md"

    assert captured.out == example.read_text(encoding="utf-8")
    assert captured.err == ""


@pytest.mark.parametrize(
    ("within", "expected_names"),
    [
        ("0", ["Torque wrench", "Floor jack", "Extension lead", "Ladder"]),
        ("3", ["Torque wrench", "Floor jack", "Extension lead", "Ladder", "Cordless drill"]),
        ("7", ["Torque wrench", "Floor jack", "Extension lead", "Ladder", "Cordless drill"]),
    ],
)
def test_workshop_due_windows(
    workshop_database: Path,
    capsys: pytest.CaptureFixture[str],
    within: str,
    expected_names: list[str],
) -> None:
    assert main(["--db", str(workshop_database), "due", "--within", within]) == 0
    captured = capsys.readouterr()

    assert [line.split("|")[0].strip() for line in captured.out.splitlines()[2:]] == expected_names
    assert "\033[" not in captured.out
    assert captured.err == ""


def test_workshop_repair_and_backdated_history(
    workshop_database: Path, demo_today: date, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = ["--db", str(workshop_database)]
    assert main([
        *arguments, "inspect", "floor jack", "--result", "fail",
        "--notes", "Leak remains after first repair.",
    ]) == 0
    assert main([
        *arguments, "inspect", "FLOOR JACK", "--result", "pass",
        "--notes", "Repair verified.",
    ]) == 0
    assert main([
        *arguments, "inspect", "Floor jack", "--result", "fail",
        "--date", (demo_today - timedelta(days=1)).isoformat(),
        "--notes", "Imported earlier failure.",
    ]) == 0
    capsys.readouterr()

    assert main([*arguments, "history", "fLoOr JaCk"]) == 0
    history = capsys.readouterr().out
    assert history.index("Repair verified.") < history.index("Leak remains after first repair.")
    assert history.index("Leak remains after first repair.") < history.index("Imported earlier failure.")

    with open_database(workshop_database) as connection:
        item = get_item_by_name(connection, "Floor jack")
        assert item is not None
        inspections = get_inspections_for_item(connection, item["id"])
        assert [row["result"] for row in inspections] == ["pass", "fail", "fail", "fail", "pass"]

    items, inspections_by_item = _report_data(workshop_database)
    row = next(row for row in build_list_report(items, inspections_by_item, demo_today)
               if row.name == "Floor jack")
    assert row.status == "OK"
    assert row.next_due == demo_today + timedelta(days=30)


def test_workshop_removal_requires_confirmation_and_removes_history(
    workshop_database: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = ["--db", str(workshop_database), "remove", "Floor jack"]

    assert main(arguments) == 1
    assert "without --yes" in capsys.readouterr().err
    with open_database(workshop_database) as connection:
        item = get_item_by_name(connection, "Floor jack")
        assert item is not None
        item_id = item["id"]
        assert len(get_inspections_for_item(connection, item_id)) == 2

    assert main([*arguments, "--yes"]) == 0
    with open_database(workshop_database) as connection:
        assert get_item_by_name(connection, "Floor jack") is None
        assert get_inspections_for_item(connection, item_id) == []
        assert len(get_items(connection)) == 5


def test_new_inventory_demo(
    db_path: Path,
    demo_today: date,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    arguments = ["--db", str(db_path)]
    assert main([*arguments, "list"]) == 0
    assert capsys.readouterr().out == "No items.\n"
    assert main([*arguments, "due"]) == 0
    assert capsys.readouterr().out == "Nothing due.\n"

    equipment = [
        ("Portable work light", 7, "electrical", "Cable, plug, and switch checked."),
        ("Tool trolley", 30, "storage", "Wheels, brakes, and drawers checked."),
    ]
    for name, interval, category, notes in equipment:
        assert main([
            *arguments, "add", name, "--interval", str(interval), "--category", category,
        ]) == 0
        assert capsys.readouterr().out == f"Added: {name} (every {interval} days)\n"

    assert main([*arguments, "list"]) == 0
    assert capsys.readouterr().out.count("NEVER INSPECTED") == 2

    for name, interval, category, notes in equipment:
        assert main([*arguments, "inspect", name, "--result", "pass", "--notes", notes]) == 0
        assert capsys.readouterr().out == f"Recorded: {name} on {demo_today.isoformat()} (pass)\n"

    assert main([*arguments, "list"]) == 0
    assert capsys.readouterr().out.count("\033[32mOK\033[0m") == 2
    assert main([*arguments, "due"]) == 0
    assert capsys.readouterr().out == "Nothing due.\n"
    assert main([*arguments, "due", "--within", "7"]) == 0
    due_output = capsys.readouterr().out
    assert [line.split("|")[0].strip() for line in due_output.splitlines()[2:]] == [
        "Portable work light",
    ]

    output_path = tmp_path / "new-inventory-report.md"
    assert main([*arguments, "report", "--soon", "7", "--out", str(output_path)]) == 0
    captured = capsys.readouterr()
    assert captured.out == f"Report written to {output_path}\n"
    assert captured.err == ""
    report = output_path.read_text(encoding="utf-8")
    assert (
        "- Total: 2\n"
        "- Never inspected: 0\n"
        "- Failed: 0\n"
        "- Overdue: 0\n"
        "- Due today: 0\n"
        "- Due soon: 1\n"
        "- OK: 1\n"
    ) in report
    attention = report.split("## Needs Attention\n", maxsplit=1)[1].split(
        "## All Equipment\n", maxsplit=1
    )[0]
    assert "| Portable work light | electrical | OK |" in attention
    assert "Tool trolley" not in attention


@pytest.mark.parametrize(
    ("within", "expected_names"),
    [
        ("6", []),
        ("7", ["Cable tester"]),
        ("8", ["Cable tester", "Laser level"]),
    ],
)
def test_planning_windows_demo(
    db_path: Path,
    demo_today: date,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    within: str,
    expected_names: list[str],
) -> None:
    arguments = ["--db", str(db_path)]
    equipment = [
        ("Cable tester", 7, "electrical", "Continuity checks passed."),
        ("Laser level", 6, "surveying", "Reference alignment checked."),
    ]
    for name, days_ago, category, notes in equipment:
        assert main([
            *arguments, "add", name, "--interval", "14", "--category", category,
        ]) == 0
        inspection_day = demo_today - timedelta(days=days_ago)
        assert main([
            *arguments, "inspect", name, "--result", "pass",
            "--date", inspection_day.isoformat(), "--notes", notes,
        ]) == 0
    capsys.readouterr()

    items, inspections = _report_data(db_path)
    rows = build_list_report(items, inspections, demo_today)
    assert [row.status for row in rows] == ["OK", "OK"]
    assert [row.next_due for row in rows] == [
        demo_today + timedelta(days=7), demo_today + timedelta(days=8),
    ]

    assert main([*arguments, "due", "--within", within]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    if expected_names:
        assert [line.split("|")[0].strip() for line in captured.out.splitlines()[2:]] == expected_names
    else:
        assert captured.out == "Nothing due.\n"

    output_path = tmp_path / f"planning-{within}-days.md"
    assert main([*arguments, "report", "--soon", within, "--out", str(output_path)]) == 0
    captured = capsys.readouterr()
    assert captured.out == f"Report written to {output_path}\n"
    assert captured.err == ""
    report = output_path.read_text(encoding="utf-8")
    assert (
        "- Total: 2\n"
        "- Never inspected: 0\n"
        "- Failed: 0\n"
        "- Overdue: 0\n"
        "- Due today: 0\n"
        f"- Due soon: {len(expected_names)}\n"
        f"- OK: {2 - len(expected_names)}\n"
    ) in report
    attention = report.split("## Needs Attention\n", maxsplit=1)[1].split(
        "## All Equipment\n", maxsplit=1
    )[0]
    table_lines = [line for line in attention.splitlines() if line.startswith("|")]
    assert [line.split("|")[1].strip() for line in table_lines[2:]] == expected_names
    all_equipment = report.split("## All Equipment\n", maxsplit=1)[1]
    assert "| Cable tester | electrical | OK |" in all_equipment
    assert "| Laser level | surveying | OK |" in all_equipment
    assert "\033[" not in report

    if within == "7":
        assert main([*arguments, "report"]) == 0
        assert capsys.readouterr().out == report
    assert _report_data(db_path) == (items, inspections)
