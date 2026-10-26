"""Create a fresh demo database with inspection dates relative to today."""

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
import sys

from gearcheck.db import insert_inspection, insert_item, open_database


@dataclass(frozen=True)
class DemoInspection:
    days_ago: int
    result: str
    notes: str


@dataclass(frozen=True)
class DemoItem:
    name: str
    category: str
    interval_days: int
    inspections: tuple[DemoInspection, ...] = ()


SCENARIOS = {
    "workshop": (
        DemoItem(
            "Bench grinder", "power tools", 30,
            (DemoInspection(5, "pass", "Guards secure; wheel undamaged."),),
        ),
        DemoItem(
            "Cordless drill", "power tools", 14,
            (DemoInspection(11, "pass", "Chuck and battery checked."),),
        ),
        DemoItem(
            "Extension lead", "electrical", 7,
            (DemoInspection(10, "pass", "Cable and plug checked."),),
        ),
        DemoItem(
            "Floor jack", "lifting", 30,
            (
                DemoInspection(32, "pass", "No leaks during inspection."),
                DemoInspection(2, "fail", "Hydraulic leak; removed from service."),
            ),
        ),
        DemoItem(
            "Ladder", "access", 14,
            (DemoInspection(14, "pass", "Feet and rungs undamaged."),),
        ),
        DemoItem("Torque wrench", "hand tools", 90),
    ),
    "safety": (
        DemoItem(
            "Eye wash station", "emergency", 7,
            (DemoInspection(7, "pass", "Flow and access checked."),),
        ),
        DemoItem(
            "Fall-arrest harness", "PPE", 30,
            (DemoInspection(1, "fail", "Frayed webbing; removed from service."),),
        ),
        DemoItem(
            "Fire extinguisher", "fire safety", 30,
            (DemoInspection(0, "pass", "Gauge and access checked."),),
        ),
        DemoItem(
            "First aid kit", "first aid", 30,
            (DemoInspection(27, "pass", "Contents and expiry dates checked."),),
        ),
        DemoItem(
            "Respirator", "PPE", 7,
            (DemoInspection(9, "pass", "Straps and seals checked."),),
        ),
        DemoItem("Spare harness", "PPE", 30),
    ),
    "facilities": (
        DemoItem(
            "Air compressor", "plant", 30,
            (DemoInspection(32, "pass", "Hoses and guards checked."),),
        ),
        DemoItem(
            "Boiler", "heating", 90,
            (DemoInspection(7, "pass", "Routine inspection completed."),),
        ),
        DemoItem(
            "Emergency light", "emergency", 30,
            (DemoInspection(1, "fail", "Backup battery did not hold charge."),),
        ),
        DemoItem(
            "Generator", "backup power", 30,
            (DemoInspection(27, "pass", "Start and load checks completed."),),
        ),
        DemoItem(
            "Loading door", "access", 7,
            (DemoInspection(7, "pass", "Safety stop checked."),),
        ),
        DemoItem("Sump pump", "drainage", 30),
    ),
}


def seed_database(path: Path, scenario: str, today: date) -> int:
    """Populate a new database without overwriting any existing path."""
    equipment = SCENARIOS[scenario]
    with path.open("xb"):
        pass

    with open_database(path) as connection:
        for item in equipment:
            item_id = insert_item(
                connection, item.name, item.category, item.interval_days,
                today.isoformat(),
            )
            for inspection in item.inspections:
                inspection_day = today - timedelta(days=inspection.days_ago)
                insert_inspection(
                    connection, item_id, inspection_day.isoformat(),
                    inspection.result, inspection.notes,
                )
    return len(equipment)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", type=Path, required=True,
        help="new database path; existing files are never overwritten",
    )
    parser.add_argument("--scenario", choices=tuple(SCENARIOS), default="workshop")
    args = parser.parse_args(argv)

    try:
        count = seed_database(args.db, args.scenario, date.today())
    except FileExistsError:
        print(f"Refusing to overwrite existing path: {args.db}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"Cannot create demo database: {error}", file=sys.stderr)
        return 1

    print(f"Created {args.scenario} demo: {count} items in {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
