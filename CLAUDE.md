# datefind

Library that finds dates in free text. Public API: `find_dates` and `FoundDate`, exported from `src/datefind/__init__.py`. Every `_`-prefixed module is private.

## Commands

- Test: `uv run duty test`. Extra args go to pytest: `uv run duty test -k leap`. Coverage below 90% fails.
- Lint: `uv run duty lint` (ruff, ty, typos, prek hooks).

## Code map

- `_fragments.py`: regex fragments and word lookup tables.
- `_patterns.py`: `pattern_table` lists every `DatePattern`; `compile_date_regex` joins them into one regex. Table order is alternation order, so an earlier row wins when two patterns match at the same position.
- `_resolvers.py`: turns one match's named groups plus a reference `now` into a `datetime`. Return `None` when the text is not a real date (February 30).
- `_search.py`: scans text and yields `FoundDate` for each resolved match.

## Tests

- Add a date format or false-match case as a row in the `test_find_dates` parametrize table in `tests/test_datefind.py`.
- Pin the clock with `@freeze_time` in any test that resolves a relative date ("last week", "monday").
- Warnings fail the suite (`filterwarnings = ["error"]`).
