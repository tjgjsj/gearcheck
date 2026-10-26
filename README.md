# GearCheck

GearCheck is a command-line equipment inspection tracker that stores items and inspection history in SQLite. It tracks inspection intervals, flags equipment that has never been inspected, is due or overdue, or failed its latest inspection, and generates Markdown reports. Item names are matched case-insensitively. Application code uses only the Python standard library; pytest is the only development dependency. See [SPEC.md](SPEC.md) for the behavior contract.

## Setup

1. Work from the project directory:

   ```sh
   cd /Users/tj/gearcheck
   ```

2. Use the project virtual environment at `/Users/tj/gearcheck/venv`. The project targets **Python 3.14**, but the existing local venv currently runs **Python 3.12.10**. For target-version validation, provision a Python 3.14 venv at that same path before continuing. Check its interpreter with:

   ```sh
   /Users/tj/gearcheck/venv/bin/python --version
   ```

3. Optionally activate the existing venv:

   ```sh
   source /Users/tj/gearcheck/venv/bin/activate
   ```

4. If pytest is not already available, install it into the venv:

   ```sh
   /Users/tj/gearcheck/venv/bin/python -m pip install pytest
   ```

No application dependencies or package installation are needed when running from the project directory. Activation is optional because every command below uses the venv interpreter directly.

## Usage

The default database is `./gearcheck.db`. Set a different database with the global `--db PATH` option **before** the command. The examples below cover all seven commands in [SPEC.md](SPEC.md) and use `equipment.db`; run them in order, with removal last.

### Add equipment

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db equipment.db add "Safety harness" --interval 30 --category safety
```

The interval must be a positive integer. The category defaults to `general` if omitted.

### Record an inspection

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db equipment.db inspect "Safety harness" --result pass --notes "No visible damage" --date 2026-01-15
```

Use `pass` or `fail`. Omit `--date` to use today; explicit dates must be valid `YYYY-MM-DD` dates and cannot be in the future. Notes are optional. A latest failed inspection marks the item out of service.

### List equipment

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db equipment.db list
```

Lists all items sorted by name, with category, interval, latest inspection and result, next due date, and status. Only this command's status column uses ANSI colors.

### Find equipment needing attention

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db equipment.db due --within 7
```

Includes never-inspected, failed, and overdue equipment, plus items due within seven days. Omit `--within` to use zero days (due today or earlier). Results put never-inspected items first, then failed items, then remaining items by earliest next due date.

### View inspection history

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db equipment.db history "Safety harness"
```

Shows inspections newest date first; same-day inspections are ordered most recently logged first.

### Generate a Markdown report

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db equipment.db report --soon 14 --out inspection-report.md
```

The report includes summary counts, equipment needing attention, and all equipment. `--soon` defaults to seven days. Omit `--out` to print the report to standard output:

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db equipment.db report
```

### Remove equipment

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db equipment.db remove "Safety harness" --yes
```

Permanently deletes the item and its inspection history. Without `--yes`, removal is refused and nothing changes.

## Runnable examples

Try a realistic workshop with six items covering every report category:

```sh
/Users/tj/gearcheck/venv/bin/python -m examples.demo --db workshop-example.db --scenario workshop
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db workshop-example.db list
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db workshop-example.db due --within 7
```

The example helper requires an explicit, new database path and refuses to overwrite existing files. It uses dates relative to today, so no manual date editing is needed. It does not change GearCheck's commands or use the default database.

See the [examples walkthrough](examples/README.md) for **workshop, safety, and facilities** datasets, repair and backdating workflows, expected errors, and a [sample Markdown report](examples/workshop-report.md).

## Tests

Run from `/Users/tj/gearcheck`:

```sh
/Users/tj/gearcheck/venv/bin/python -m pytest -q
```

Tests use pytest's `tmp_path` for temporary databases; they must never touch `./gearcheck.db` or `demo.db`.
