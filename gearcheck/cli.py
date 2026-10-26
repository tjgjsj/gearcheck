"""Command-line interface for GearCheck."""

import argparse
from datetime import date
from pathlib import Path
import sqlite3
import sys
from collections import defaultdict
from collections.abc import Sequence

from .db import (
    delete_item,
    get_all_inspections,
    get_inspections_for_item,
    get_item_by_name,
    get_items,
    insert_inspection,
    insert_item,
    open_database,
)
from .reports import (
    ItemRecord,
    ReportRow,
    build_due_report,
    build_list_report,
    build_markdown_report,
)
from .status import InspectionRecord


_ANSI_GREEN = "\033[32m"
_ANSI_YELLOW = "\033[33m"
_ANSI_RED = "\033[31m"
_ANSI_RESET = "\033[0m"


class UserError(Exception):
    """An expected error caused by invalid user input or missing data."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gearcheck")
    parser.add_argument("--db", type=Path, default=Path("./gearcheck.db"))
    commands = parser.add_subparsers(dest="command", required=True)

    add_parser = commands.add_parser("add", help="add an item")
    add_parser.add_argument("name")
    add_parser.add_argument("--interval", required=True)
    add_parser.add_argument("--category", default="general")

    inspect_parser = commands.add_parser("inspect", help="record an inspection")
    inspect_parser.add_argument("name")
    inspect_parser.add_argument("--result", choices=("pass", "fail"), required=True)
    inspect_parser.add_argument("--notes")
    inspect_parser.add_argument("--date")

    commands.add_parser("list", help="list all items")

    due_parser = commands.add_parser("due", help="list items needing attention")
    due_parser.add_argument("--within", default="0")

    history_parser = commands.add_parser("history", help="show inspection history")
    history_parser.add_argument("name")

    remove_parser = commands.add_parser("remove", help="remove an item")
    remove_parser.add_argument("name")
    remove_parser.add_argument("--yes", action="store_true")

    report_parser = commands.add_parser("report", help="produce a Markdown inspection report")
    report_parser.add_argument("--out", type=Path)
    report_parser.add_argument("--soon", default="7")

    return parser


def _positive_integer(value: str, option: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise UserError(f"{option} must be a positive integer.") from None
    if parsed <= 0:
        raise UserError(f"{option} must be a positive integer.")
    return parsed


def _non_negative_integer(value: str, option: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise UserError(f"{option} must be a non-negative integer.") from None
    if parsed < 0:
        raise UserError(f"{option} must be a non-negative integer.")
    return parsed


def _inspection_date(value: str, today: date) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise UserError(f"Invalid date: {value} (expected YYYY-MM-DD).") from None
    if parsed.isoformat() != value:
        raise UserError(f"Invalid date: {value} (expected YYYY-MM-DD).")
    if parsed > today:
        raise UserError("Inspection date cannot be in the future.")
    return parsed


def _item_records(connection: sqlite3.Connection) -> list[ItemRecord]:
    return [
        ItemRecord(
            id=row["id"],
            name=row["name"],
            category=row["category"],
            interval_days=row["interval_days"],
        )
        for row in get_items(connection)
    ]


def _inspection_records(
    connection: sqlite3.Connection,
) -> dict[int, list[InspectionRecord]]:
    records: dict[int, list[InspectionRecord]] = defaultdict(list)
    for row in get_all_inspections(connection):
        records[row["item_id"]].append(
            InspectionRecord(
                id=row["id"],
                date=date.fromisoformat(row["date"]),
                result=row["result"],
            )
        )
    return dict(records)


def _colored_status_cell(status: str, width: int) -> str:
    if status == "OK":
        color = _ANSI_GREEN
    elif status == "DUE TODAY":
        color = _ANSI_YELLOW
    elif status.startswith("OVERDUE") or status == "FAILED - OUT OF SERVICE":
        color = _ANSI_RED
    else:
        return status.ljust(width)
    return f"{color}{status}{_ANSI_RESET}" + " " * (width - len(status))


def _display_table(
    rows: Sequence[ReportRow], *, color_status: bool = False
) -> str:
    headers = (
        "NAME",
        "CATEGORY",
        "INTERVAL",
        "LAST INSPECTED",
        "LAST RESULT",
        "NEXT DUE",
        "STATUS",
    )
    values = [
        (
            row.name,
            row.category,
            str(row.interval_days),
            row.last_inspected.isoformat() if row.last_inspected else "never",
            row.last_result or "-",
            row.next_due.isoformat() if row.next_due else "now",
            row.status,
        )
        for row in rows
    ]
    widths = [
        max(len(header), *(len(row[index]) for row in values))
        if values
        else len(header)
        for index, header in enumerate(headers)
    ]
    lines = [" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers))]
    lines.append("-+-".join("-" * width for width in widths))
    for row in values:
        cells = [
            _colored_status_cell(value, widths[index])
            if color_status and index == len(headers) - 1
            else value.ljust(widths[index])
            for index, value in enumerate(row)
        ]
        lines.append(" | ".join(cells))
    return "\n".join(lines)


def _run(args: argparse.Namespace) -> None:
    today = date.today()

    if args.command == "remove" and not args.yes:
        raise UserError(f"Refusing to remove {args.name} without --yes.")

    if args.command == "add":
        interval = _positive_integer(args.interval, "--interval")
        with open_database(args.db) as connection:
            try:
                insert_item(
                    connection,
                    args.name,
                    args.category,
                    interval,
                    today.isoformat(),
                )
            except sqlite3.IntegrityError:
                if get_item_by_name(connection, args.name) is not None:
                    raise UserError(f"Item already exists: {args.name}.") from None
                raise
        print(f"Added: {args.name} (every {interval} days)")
        return

    if args.command == "inspect":
        inspection_day = (
            _inspection_date(args.date, today) if args.date is not None else today
        )
        with open_database(args.db) as connection:
            item = get_item_by_name(connection, args.name)
            if item is None:
                raise UserError(f"Unknown item: {args.name}.")
            insert_inspection(
                connection,
                item["id"],
                inspection_day.isoformat(),
                args.result,
                args.notes,
            )
        print(f"Recorded: {item['name']} on {inspection_day.isoformat()} ({args.result})")
        return

    if args.command == "list":
        with open_database(args.db) as connection:
            rows = build_list_report(
                _item_records(connection), _inspection_records(connection), today
            )
        if not rows:
            print("No items.")
        else:
            print(_display_table(rows, color_status=True))
        return

    if args.command == "due":
        within = _non_negative_integer(args.within, "--within")
        with open_database(args.db) as connection:
            rows = build_due_report(
                _item_records(connection),
                _inspection_records(connection),
                today,
                within,
            )
        if not rows:
            print("Nothing due.")
        else:
            print(_display_table(rows))
        return

    if args.command == "report":
        soon = _non_negative_integer(args.soon, "--soon")
        with open_database(args.db) as connection:
            report = build_markdown_report(
                _item_records(connection),
                _inspection_records(connection),
                today,
                soon,
            )
        if args.out is None:
            print(report, end="")
        else:
            args.out.write_text(report, encoding="utf-8")
            print(f"Report written to {args.out}")
        return

    if args.command == "history":
        with open_database(args.db) as connection:
            item = get_item_by_name(connection, args.name)
            if item is None:
                raise UserError(f"Unknown item: {args.name}.")
            inspections = get_inspections_for_item(connection, item["id"])
        print(f"History: {item['name']}")
        if not inspections:
            print("No inspections.")
        else:
            print("DATE       | RESULT | NOTES")
            for inspection in inspections:
                print(
                    f"{inspection['date']} | {inspection['result']}  | "
                    f"{inspection['notes'] or ''}"
                )
        return

    if args.command == "remove":
        with open_database(args.db) as connection:
            item = get_item_by_name(connection, args.name)
            if item is None:
                raise UserError(f"Unknown item: {args.name}.")
            delete_item(connection, item["id"])
        print(f"Removed: {item['name']}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        _run(args)
    except UserError as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0
