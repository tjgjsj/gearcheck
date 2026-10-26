# GearCheck - Equipment Inspection Tracker
## Spec v1.0
### Purpose
A small command-line tool that tracks equipment, records inspections, and
flags anything overdue or out of service.
### Constraints
- Python 3.14. Application code uses the standard library only
(argparse, sqlite3, datetime, pathlib). pytest is used for tests only.
- Run as: python -m gearcheck <command> [options]
- Data lives in a SQLite file. Default: ./gearcheck.db
A global option --db PATH overrides the location. It comes before
the command: python -m gearcheck --db demo.db list
### Exit codes
- 0 on success.
- 1 on user errors the app detects: unknown item, duplicate name, bad
interval, bad or future date, remove without --yes. Print a clear
one-line message to stderr, with no Python traceback. Validate
--interval and --date in application code, not with argparse type=
functions, so these cases exit with 1.
- Syntax errors that argparse itself catches (missing required option,
unknown flag, a --result other than pass/fail) keep argparse's
standard usage message and exit code 2.
### Data model
- items: id, name (required, unique, case-insensitive), category
(default "general"), interval_days (integer > 0), created_at (YYYY-MM-DD)
- inspections: id, item_id (references items), date (YYYY-MM-DD),
result ("pass" or "fail"), notes (optional)
- Item names are matched case-insensitively in every command.
### Commands
1. add NAME --interval DAYS [--category CAT]
Adds an item. Prints: Added: NAME (every DAYS days)
Errors: name already exists; DAYS is not a positive integer.
2. inspect NAME --result pass|fail [--notes TEXT] [--date YYYY-MM-DD]
Logs an inspection. --date defaults to today.
Errors: unknown item; invalid date; date in the future.
3. list
Table of all items: name, category, interval, last inspected
(or "never"), last result, next due, status. Sorted by name.
The list status column uses ANSI colors: green for "OK", yellow for
"DUE TODAY", and red for "OVERDUE" and "FAILED" statuses.
"NEVER INSPECTED" remains uncolored. Other commands do not use colors.
4. due [--within DAYS]
Items that need attention: never inspected, failed, overdue, or with a
next due date within DAYS days of today (default 0 = due today or
earlier). Sort: never inspected first, then failed, then by next due
date, oldest first. Prints "Nothing due." if the list is empty.
5. history NAME
All inspections for one item, newest date first (same-day ties:
most recently logged first).
6. remove NAME --yes
Deletes the item and its inspections. Without --yes, refuse with
exit code 1 and change nothing.
### Status rules (checked in this order)
1. No inspections -> "NEVER INSPECTED" (next due: "now")
2. Latest result is "fail" -> "FAILED - OUT OF SERVICE"
3. today > next_due -> "OVERDUE (N days)" where N = today - next_due
4. today == next_due -> "DUE TODAY"
5. otherwise -> "OK"
next_due = date of the latest inspection + interval_days.
"Latest" means the most recent inspection date. If several inspections
share that date, the most recently logged one counts.
Status is computed by a pure function that receives `today` as a
parameter. It must not read the system clock or touch the database.
### Testing requirements
- pytest. Every test uses a temporary database (pytest tmp_path);
tests never touch ./gearcheck.db.
- Cover every status rule, plus: duplicate add, non-positive interval,
inspect unknown item, future date rejected, case-insensitive names,
due sorting, same-day tie, remove refuses without --yes, exit code 1
on user errors. Verify the list status colors and that other statuses and
commands remain uncolored.
### Out of scope for v1.0
Colors outside the list status column, config files, network access,
third-party packages.
## Spec v1.1 - Report command
7. report [--out FILE] [--soon DAYS]
Produces a Markdown report. --soon defaults to 7.
- Line 1: "# GearCheck Inspection Report"
- Line 2: "Generated: YYYY-MM-DD"
- "## Summary": counts for Total, Never inspected, Failed, Overdue,
Due today, Due soon (status OK, next due 1 to DAYS days away), and
OK (everything else). The six category counts add up to Total.
- "## Needs Attention": Markdown table (Name | Category | Status |
Next Due) of every item that is not plain OK, same sort as `due`.
- "## All Equipment": Markdown table of every item, sorted by name.
- With --out FILE: write the file and print "Report written to FILE".
Without --out: print the report to stdout.
- Report text is built by a pure function (items + today in, string
out) so it can be unit tested without a database.
- Tests: category counts for a fixture with one item in each category;
--out writes the file; counts add up to Total.
