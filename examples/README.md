# GearCheck examples

This guide walks through all seven GearCheck commands using disposable sample data. No extra application dependencies are needed. Run commands in **macOS Terminal**, not in the OpenCode chat box.

Equipment, notes, and inspection intervals are illustrative, not safety guidance. Follow the applicable manufacturer and site requirements for real equipment.

- [Preparation](#preparation)
- [Demo 1: workshop](#demo-1-workshop)
- [Demo 2: safety equipment](#demo-2-safety-equipment)
- [Demo 3: facilities equipment](#demo-3-facilities-equipment)
- [Demo 4: same-day repairs](#demo-4-same-day-repairs)
- [Demo 5: backdated inspections](#demo-5-backdated-inspections)
- [Demo 6: adding and removing equipment](#demo-6-adding-and-removing-equipment)
- [Error examples](#error-examples)
- [Repeat safely](#repeat-safely)
- [Troubleshooting](#troubleshooting)
- [Run the tests](#run-the-tests)

## Preparation

### 1. Open Terminal and enter the project directory

Paste this block into Terminal, then press Return:

```sh
cd /Users/tj/gearcheck
pwd
/Users/tj/gearcheck/venv/bin/python --version
```

`pwd` should print `/Users/tj/gearcheck`. The checked-in local virtual environment currently reports `Python 3.12.10`; the project's target version is **Python 3.14**. These instructions use the existing interpreter and do not change the environment. Stop if the interpreter cannot be found.

Keep using this **same Terminal tab** for the rest of the guide. Paste only the contents of `sh` code blocks, not the Markdown fence markers or the expected output. Run one block at a time and check its result before continuing. Each command belongs on its own line.

### 2. Create a fresh folder for this run

```sh
DEMO_DIR=$(mktemp -d "${TMPDIR:-/tmp}/gearcheck-demo.XXXXXX")
printf 'Demo files: %s\n' "$DEMO_DIR"
```

You should see `Demo files:` followed by a new directory path. Stop if the path is empty or `mktemp` reports an error. `$DEMO_DIR` is a shell variable holding that path; leave it exactly as written in later commands. Quotes around paths keep spaces from breaking commands.

All demo databases and generated reports will go into this folder, **not** the project's `gearcheck.db`, `demo.db`, or checked-in report example. The folder is temporary and the operating system may eventually remove it. See [Repeat safely](#repeat-safely) for keeping results or starting another run.

### 3. Choose a demo and follow its steps in order

- Demos 1, 2, and 3 use separate databases; you can run any or all of them after preparation.
- Demos 4, 5, and 6 use Demo 1's workshop database. Run Demo 4 before Demo 5.
- Perform each write step once to match the expected inspection counts. Each `inspect` command appends a new record; it does not edit a previous record.
- Complete a scenario on the same calendar day you seed it. Inspection dates are relative to that day, so statuses naturally change on later days.

Every application command below puts the global `--db PATH` option **before** the command name. Do not omit it: without it, GearCheck uses `./gearcheck.db`.

## Demo 1: workshop

**Goal:** see every report category, inspect history, find work due, and save a report.

### 1. Seed the workshop database

```sh
/Users/tj/gearcheck/venv/bin/python -m examples.demo --db "$DEMO_DIR/workshop-example.db" --scenario workshop
```

Expected output is `Created workshop demo: 6 items in .../workshop-example.db`, with your actual demo folder in place of `...`. The helper creates the database and inspection history automatically. If it refuses to overwrite a file, follow [Repeat safely](#repeat-safely); do not delete your existing database to continue.

### 2. List all six items

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" list
```

The output is a table sorted by name. It includes category, interval, last inspected date, last result, next due date, and status. Check these starting values; actual calendar dates appear instead of the relative dates shown here:

| Item | List status | Report category | Next due |
| --- | --- | --- | --- |
| Bench grinder | OK | OK | in 25 days |
| Cordless drill | OK | Due soon | in 3 days |
| Extension lead | OVERDUE (3 days) | Overdue | 3 days ago |
| Floor jack | FAILED - OUT OF SERVICE | Failed | in 28 days |
| Ladder | DUE TODAY | Due today | today |
| Torque wrench | NEVER INSPECTED | Never inspected | now |

Only the list's status column is colored: green for `OK`, yellow for `DUE TODAY`, red for overdue or failed, and no color for `NEVER INSPECTED`.

### 3. Compare today's work with the next seven days

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" due
```

Expected rows, in order: **Torque wrench, Floor jack, Extension lead, Ladder**. Never-inspected items come first, then failures, then the remaining items by next due date. The failed floor jack needs attention even though its scheduled due date is in the future.

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" due --within 7
```

The same four rows appear, followed by **Cordless drill**. The bench grinder is excluded because it is not due for another 25 days. Unlike `list`, `due` output is not colored.

### 4. Read the floor jack's existing history

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" history "Floor jack"
```

The output starts with `History: Floor jack`. Expect two inspections, newest first:

1. A failure from two days ago: `Hydraulic leak; removed from service.`
2. A pass from 32 days ago: `No leaks during inspection.`

### 5. Generate and save a Markdown report

First print a report in Terminal:

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" report
```

It starts with `# GearCheck Inspection Report` and today's date. Check the summary:

```text
- Total: 6
- Never inspected: 1
- Failed: 1
- Overdue: 1
- Due today: 1
- Due soon: 1
- OK: 1
```

The report also includes Needs Attention and All Equipment tables. `Due soon` is a report category, not a separate list status: the cordless drill is `OK` in the table but counted as due soon within the default seven-day window.

Now save the report and read the saved file:

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" report --out "$DEMO_DIR/workshop-report.md"
cat "$DEMO_DIR/workshop-report.md"
```

The first command prints `Report written to .../workshop-report.md`. The second displays that file. `--out` **replaces an existing report at the same path**; reports are snapshots and do not automatically update after inspections change.

The checked-in [workshop-report.md](workshop-report.md) shows this starting report for **2026-10-26**. Your dates will differ when running on another day, but the starting counts should match. The tests verify the checked-in snapshot against the application.

## Demo 2: safety equipment

**Goal:** inspect a separate inventory and plan the next two weeks. This demo does not change the workshop database.

### 1. Create and list the safety inventory

```sh
/Users/tj/gearcheck/venv/bin/python -m examples.demo --db "$DEMO_DIR/safety-example.db" --scenario safety
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/safety-example.db" list
```

Expect `Created safety demo: 6 items in .../safety-example.db`, followed by these list entries:

| Item | Starting status | Next due |
| --- | --- | --- |
| Eye wash station | DUE TODAY | today |
| Fall-arrest harness | FAILED - OUT OF SERVICE | in 29 days |
| Fire extinguisher | OK | in 30 days |
| First aid kit | OK | in 3 days |
| Respirator | OVERDUE (2 days) | 2 days ago |
| Spare harness | NEVER INSPECTED | now |

### 2. Check the failed harness and upcoming work

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/safety-example.db" history "Fall-arrest harness"
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/safety-example.db" due --within 14
```

The history has one failed inspection from yesterday with notes `Frayed webbing; removed from service.` The due table lists **Spare harness, Fall-arrest harness, Respirator, Eye wash station, First aid kit**, in that order. The fire extinguisher is outside the 14-day window.

### 3. Save a two-week report

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/safety-example.db" report --soon 14 --out "$DEMO_DIR/safety-report.md"
cat "$DEMO_DIR/safety-report.md"
```

Expect six total items and one in each summary category. The first aid kit is the one due-soon item, and the fire extinguisher is the one remaining `OK` item. Needs Attention contains the same five names as the previous due table.

## Demo 3: facilities equipment

**Goal:** compare a month-long work list with a report limited to today's attention items. This demo uses its own database.

### 1. Create and list the facilities inventory

```sh
/Users/tj/gearcheck/venv/bin/python -m examples.demo --db "$DEMO_DIR/facilities-example.db" --scenario facilities
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/facilities-example.db" list
```

Expect `Created facilities demo: 6 items in .../facilities-example.db`, followed by:

| Item | Starting status | Next due |
| --- | --- | --- |
| Air compressor | OVERDUE (2 days) | 2 days ago |
| Boiler | OK | in 83 days |
| Emergency light | FAILED - OUT OF SERVICE | in 29 days |
| Generator | OK | in 3 days |
| Loading door | DUE TODAY | today |
| Sump pump | NEVER INSPECTED | now |

### 2. Find work for the next 30 days

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/facilities-example.db" due --within 30
```

Expected order: **Sump pump, Emergency light, Air compressor, Loading door, Generator**. The boiler is excluded because it is not due for 83 days.

### 3. Make a today-only report

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/facilities-example.db" report --soon 0 --out "$DEMO_DIR/facilities-report.md"
cat "$DEMO_DIR/facilities-report.md"
```

Expected summary: **Total 6; Never inspected 1; Failed 1; Overdue 1; Due today 1; Due soon 0; OK 2**.

Needs Attention lists only **Sump pump, Emergency light, Air compressor, Loading door**. The generator and boiler remain in All Equipment. `--soon 0` excludes future-due passing items from Needs Attention; failed equipment still needs attention regardless of its next due date.

## Demo 4: same-day repairs

**Prerequisite:** seed the workshop in Demo 1. This section changes its inspection history. Run all steps in order on the same day, once each, for the counts below to match.

### 1. Record a failed inspection today

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" inspect "floor jack" --result fail --notes "Leak remains after first repair."
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" list
```

The inspection command prints `Recorded: Floor jack on YYYY-MM-DD (fail)`, using today's actual date. The floor jack remains `FAILED - OUT OF SERVICE`.

### 2. Record a successful inspection after the repair

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" inspect "FLOOR JACK" --result pass --notes "Repair verified."
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" list
```

Expect `Recorded: Floor jack on YYYY-MM-DD (pass)`. The floor jack is now `OK`, with its next due date 30 days from today. Names are matched case-insensitively, so `floor jack` and `FLOOR JACK` refer to the same item.

Both inspections default to today because `--date` was omitted. For inspections on the same date, the most recently logged one determines the status. In real use, record a pass only after an actual inspection passes.

### 3. Verify that older failures were retained

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" history "Floor jack"
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" report
```

History now has four rows: today's pass, today's failure, the original failure from two days ago, then the pass from 32 days ago. In the report, **Failed decreases to 0** and **OK increases to 2**; the total stays 6. The previously saved workshop report does not change unless you run `report --out` again.

## Demo 5: backdated inspections

**Prerequisite:** finish Demo 4 first, in this same run. Its successful inspection must already exist so you can see that a later-entered historical failure does not replace it.

### 1. Calculate yesterday's date

```sh
YESTERDAY=$(/Users/tj/gearcheck/venv/bin/python -c 'from datetime import date, timedelta; print(date.today() - timedelta(days=1))')
printf 'Backdated inspection date: %s\n' "$YESTERDAY"
```

Check that the printed date is yesterday in `YYYY-MM-DD` format. Leave `$YESTERDAY` as written in the next command; the shell substitutes the calculated value.

### 2. Record the historical failure and check the result

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" inspect "Floor jack" --result fail --date "$YESTERDAY" --notes "Imported earlier failure."
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" history "Floor jack"
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" list
```

History now has five inspections: today's pass, today's failure, yesterday's imported failure, the failure from two days ago, and the oldest pass. The floor jack **stays `OK`**.

Inspection date takes priority over logging order. The backdated failure was entered last, but it is older than today's pass. Explicit dates must be valid `YYYY-MM-DD` dates and cannot be in the future.

## Demo 6: adding and removing equipment

**Prerequisite:** seed the workshop in Demo 1. This exercise adds and then deletes only a new practice item; the original six items remain.

### 1. Add a practice item

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" add "Spare socket set" --interval 30 --category "hand tools"
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" history "Spare socket set"
```

Expect `Added: Spare socket set (every 30 days)`, then `History: Spare socket set` and `No inspections.` It has status `NEVER INSPECTED` until an inspection is recorded.

### 2. Record its first inspection

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" inspect "spare socket set" --result pass --notes "No cracks or rounded edges."
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" history "Spare socket set"
```

Expect one passing inspection dated today, including the notes you supplied.

### 3. Try removal without confirmation

This next command is **supposed to fail**. Run `echo $?` immediately afterward, without another command in between, to see the previous command's exit code:

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" remove "SPARE SOCKET SET"
echo $?
```

Expect `Refusing to remove SPARE SOCKET SET without --yes.` followed by `1`. Confirm the item and inspection still exist:

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" history "Spare socket set"
```

### 4. Confirm removal and verify it

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" remove "Spare socket set" --yes
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" list
```

Expect `Removed: Spare socket set`. The list returns to the original six items. Confirmed removal permanently deletes both this item and its inspection history, so only use `--yes` when you intend to delete them.

## Error examples

**Prerequisite:** seed the workshop in Demo 1. These commands deliberately fail without changing the equipment. Run them in order in your normal interactive Terminal, not in a script configured to stop on errors. Each `echo $?` prints the preceding command's exit code.

```sh
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" add "ladder" --interval 14
echo $?

/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" add "Spare drill" --interval 0
echo $?

/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" inspect "Missing tool" --result pass
echo $?

/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" inspect "Ladder" --result pass --date 2026-02-30
echo $?

TOMORROW=$(/Users/tj/gearcheck/venv/bin/python -c 'from datetime import date, timedelta; print(date.today() + timedelta(days=1))')
/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" inspect "Ladder" --result pass --date "$TOMORROW"
echo $?

/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" due --within -1
echo $?

/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" remove "Ladder"
echo $?

/Users/tj/gearcheck/venv/bin/python -m gearcheck --db "$DEMO_DIR/workshop-example.db" inspect "Ladder" --result unknown
echo $?
```

Compare the results in the same order:

| Example | Expected error | Exit code |
| --- | --- | --- |
| Duplicate name | `Item already exists: ladder.` | 1 |
| Zero interval | `--interval must be a positive integer.` | 1 |
| Unknown item | `Unknown item: Missing tool.` | 1 |
| Invalid calendar date | `Invalid date: 2026-02-30 (expected YYYY-MM-DD).` | 1 |
| Future date | `Inspection date cannot be in the future.` | 1 |
| Negative look-ahead window | `--within must be a non-negative integer.` | 1 |
| Unconfirmed removal | `Refusing to remove Ladder without --yes.` | 1 |
| Invalid result choice | A usage message and an error saying `unknown` is not a valid choice | 2 |

User errors go to standard error without a Python traceback. Argument syntax errors use argparse's usage message. A successful command exits with `0`.

## Repeat safely

The seed helper refuses to overwrite any existing file, even an empty file or an earlier demo database. To repeat the demos from a clean starting point, create another folder rather than deleting or reusing databases:

```sh
printf 'Previous demo files: %s\n' "$DEMO_DIR"
DEMO_DIR=$(mktemp -d "${TMPDIR:-/tmp}/gearcheck-demo.XXXXXX")
printf 'New demo files: %s\n' "$DEMO_DIR"
```

Check that the new path is nonempty. The earlier folder remains unchanged; the variable now points to the new folder. Restart as follows:

- **Demo 1, 2, or 3:** start at that demo's seed step.
- **Demo 4 or 6:** seed the workshop using Demo 1, step 1, then run the desired demo.
- **Demo 5:** seed the workshop using Demo 1, step 1, complete Demo 4, then run Demo 5.

You do not need to delete files or alter the project's real databases.

To inspect the **current** run's files in Finder:

```sh
open "$DEMO_DIR"
```

Copy reports somewhere permanent using Finder if you want to keep them beyond this temporary session. If you open a new Terminal tab or lose the value of `DEMO_DIR`, the simplest safe restart is to repeat [Preparation](#preparation), then seed the demos again in the newly created folder.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| `No module named gearcheck` or `No module named examples` | Run `cd /Users/tj/gearcheck`, then retry. The commands must run from the project directory. |
| `/Users/tj/gearcheck/venv/bin/python` cannot be found | Stop and resolve the missing project environment before proceeding; do not substitute a different interpreter. |
| The demo-folder path is empty, or a database path looks like `/workshop-example.db` | Repeat Preparation in the same Terminal tab. Do not continue with an empty `DEMO_DIR`. |
| `Refusing to overwrite existing path` | Create a new demo folder as described in Repeat safely, then reseed there. |
| `No items.` or unexpected missing equipment | Check that `--db` uses the exact filename seeded for that scenario. A different filename opens or creates a different database. |
| Dates or summary counts no longer match | A write step may have been repeated, or a day has passed. Start a fresh run and perform each step once in order. |
| A saved report still shows a repaired item as failed | Reports are static files. Run `report --out` again to regenerate it; this replaces that output file. |

## Run the tests

Run the full suite from the project directory:

```sh
cd /Users/tj/gearcheck
/Users/tj/gearcheck/venv/bin/python -m pytest -q
```

All tests should pass; the current suite has 77 tests. [`tests/test_examples.py`](../tests/test_examples.py) checks all three datasets, calendar boundaries, the report snapshot, existing-file protection, and the repair, backdating, and removal workflows. Test databases live under pytest's `tmp_path`, not in your demo folder or the project's real databases.
