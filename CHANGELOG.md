## v1.0.0 (2026-11-24)

### BREAKING CHANGE

- FoundDate is now immutable and slotted.
Assigning to a field raises FrozenInstanceError, and
instances no longer accept new attributes or weak
references. Use dataclasses.replace() to make a changed
copy.
- runs of 4 to 7 digits with no separators, such as 9819
or 120524, no longer match by default. Pass short_digit_dates=True to
find_dates to match them. Two-digit years more than 50 years after the
reference year resolve to the previous century, so "march 3rd 99" is
1999, not 2099.
- relative dates (today, tomorrow, weekdays, "3 days
ago", "next month") no longer carry the current time of day. They
return midnight in the output timezone, like explicit dates. Callers
that need the current time must combine the found date with it.

### Feat

- **api**: report found dates as standard strings (#38)
- **matching**: find ISO weeks and half years (#37)
- **api**: report how precise each found date is (#35)
- **matching**: find day-first dates without a year (#33)
- **matching**: rework year and digit matching (#32)
- **api**: add reference date, return midnight (#31)

### Fix

- **matching**: read web text, apostrophe years, offsets (#36)
- **matching**: find dates next to times, ranges, weekdays
- **matching**: skip version numbers after v or version (#34)
- **matching**: stop matching sat, sun, wed alone (#30)
- **datefind**: stop false matches and invalid dates

### Refactor

- **datefind**: restructure date matching (#29)

## v0.6.0 (2026-10-12)

### Feat

- support python 3.15 (#23)

## v0.5.0 (2026-04-22)

### Feat

- expand supported date pattern categories (#15)

### Refactor

- **datefind**: reduce per-match work (#16)

## v0.4.0 (2026-03-19)

### Feat

- support python 3.14 (#12)

## v0.3.0 (2026-03-19)

### Feat

- find additional natural language dates (#3)

### Refactor

- use FoundDate as return object (#4)

## v0.2.1 (2025-05-28)

### Fix

- remove text attribute from Date object (#2)

## v0.2.0 (2025-05-27)

### Feat

- capture dates in `MM-YYYY` or `YYYY-MM` format

## v0.1.0 (2025-05-27)

### Feat

- capture `the` or `of` separators (#1)
- initial commit
