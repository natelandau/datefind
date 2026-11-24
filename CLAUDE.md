# datefind

Library that finds dates in free text. Public API: `find_dates`, `FoundDate`, and the `DatePrecision` type, exported from `src/datefind/__init__.py`. Every `_`-prefixed module is private.

## Commands

- Test: `uv run duty test`. Extra args go to pytest: `uv run duty test -k leap`. Coverage below 90% fails.
- Lint: `uv run duty lint` (ruff check, ruff format check, ty, typos, prek hooks).
- Run checks only through the duty tasks above, never `pytest` or `prek` directly. The `test` (no args) and `prek` tasks run through gate-cache, which skips a check that already passed on the same files. Treat an `already passed on` line as a pass. Run `uv run gate-cache --skill` before changing a gate in `duties.py`.
- Compare with main: `uv run python scripts/compare_with_main.py` (about 1 minute). Run before committing a change to `_fragments.py` or `_patterns.py`. Every listed output difference is a regression unless the change intends it; a scan over 1.10x main's time is a regression.

## Code map

- `_fragments.py`: regex fragments and word lookup tables.
- `_patterns.py`: `pattern_table` lists every `DatePattern`; `compile_date_regex` joins them into one regex. Table order is alternation order, so an earlier row wins when two patterns match at the same position.
- `_resolvers.py`: turns one match's named groups plus a reference `today` into a `date`. Return `None` when the text is not a real date (February 30).
- `_search.py`: converts look-alike Unicode characters to ASCII one for one (`ASCII_EQUIVALENTS`), scans, yields `FoundDate` per resolved match at midnight in the output timezone. Holds checks too slow for the combined regex, run once per match: version prefix ("v2.1.1500"), weekday before a date (merged into the span when it agrees), counted offset before a date ("2 weeks after Jan 5"). Put a new lookbehind-style rule here when it slows `scripts/compare_with_main.py` past 1.10x.

## Public API rules

- New information about a match: a new `FoundDate` field. Never an option that changes what `find_dates` yields (a tuple, an extra item).
- An option whose `False` is unclear, or with more than two choices: a string value such as `prefer="past" | "future" | "nearest"`, not a boolean.
- No dates found: yield nothing. Never return or yield `None`.

## Tests

- Add a date format or false-match case as a row in the `test_find_dates` parametrize table in `tests/test_datefind.py`.
- Pin the reference day in any test that resolves a relative date ("last week", "monday"): pass `now=` to `find_dates`, or `@freeze_time` to test the default clock.
- Warnings fail the suite (`filterwarnings = ["error"]`).
