# Repository guidance

- `SPEC.md` is the behavior contract for the CLI, data model, status rules, and required tests; follow it rather than guessing or expanding v1 scope.
- Target Python 3.14; application code is standard-library-only, with pytest for tests. The checked-in local `venv` currently runs Python 3.12.10—do not mistake it for the target version.
- Run the CLI as `python -m gearcheck`; global `--db PATH` comes before the command. The default database is `./gearcheck.db`.
- Run tests with `venv/bin/python -m pytest`. Tests must use `tmp_path`, never the default database.
## Project rules (added by Tony - always follow)
- Python: always use /Users/tj/gearcheck/venv/bin/python. Never bare
`python` or `python3`.
- Run tests with: /Users/tj/gearcheck/venv/bin/python -m pytest -q
- SPEC.md is the source of truth. If a request conflicts with SPEC.md,
stop and ask before changing anything.
- Application code: Python standard library only. pytest is the only
dev dependency. Do not pip install anything else.
- Tests must use pytest's tmp_path for databases. Never touch
./gearcheck.db or demo.db in tests.
- Status and report logic stay pure functions that take `today` as a
parameter.
- Never modify anything inside venv/.
- Do not run git commit or git push. Tony makes all commits.
- Keep changes small. After each change, summarize what changed and why.