[![Tests](https://github.com/natelandau/datefind/actions/workflows/automated-tests.yml/badge.svg)](https://github.com/natelandau/datefind/actions/workflows/automated-tests.yml) [![codecov](https://codecov.io/gh/natelandau/datefind/graph/badge.svg?token=CXstf6zblD)](https://codecov.io/gh/natelandau/datefind)

# datefind

A python module for locating dates within text. Use this package to search for dates and convert them to datetime objects.

Finds dates in many different formats.

- All numeric - `2024-01-01`, `01/01/2024`, `01012024`, etc.
- Natural language - `January 1st, 2024`, `March nineteenth, 2024`, `twenty fifth of January`, `Mar 15, 24`, `14 Feb`, `3rd March`, etc. Because `may` is also a verb, a plain number before it is not a date (`option 2 may work`). Write `2nd May` or `2 of May` instead.
- Fuzzy dates - `today`, `yesterday`, `tomorrow`, `day after tomorrow`, `day before yesterday`, `last week`, `this week`, `next week`, etc.
- Relative offsets - `3 days ago`, `in 2 weeks`, `1 year from now`, etc.
- A day in a relative month - `3rd of next month`, `twentieth of last month`, `15 of this month`.
- Weekdays - `Monday`, `next Friday`, `last Tuesday`, etc. The abbreviations `sat`, `sun`, and `wed` are also English words, so they match only after `last`, `this`, or `next`.
- Quarters - `Q1 2024`, `2024 Q3`, etc.

A weekday directly before a date is part of that date. `Friday, January 5, 2024` and `Wed, 03 Jan 2024` each give one date, not a date and a separate weekday.

A day range in one month, such as `Jan 5-10, 2024` or `Jan 5 to 10`, gives no date. Neither end of the range is reported, so the `10` is not read as the year 2010.

Dates with month names accept years from 1000 to 2999, such as `March 1105` or `dec 31 1899`. All-number dates with a day, a month, and a year accept years from 1000 to 2999 when `/`, `-`, or `.` divides the parts, such as `12/25/1850`. Every other all-number date must have a year from 1900 to 2099: dates with other separators such as spaces, a month and year without a day such as `12/2024`, and runs of digits with no separators. This keeps counts, prices, and ranges such as `10 2500 sold`, `1500.05`, or `pages 10-1500` from matching as dates.

Month abbreviations such as `mar` or `may` match only as separate words, so `Market` and `Mayfield` are not months. Full month names can touch other letters.

> [!NOTE]\
> `datefind` finds the year, month, and day only. It does not read hours, minutes, seconds, or microseconds. A time after a date, as in `2024-01-05 14:30` or `Jan 5 10pm`, is ignored, and the date before it is found.

## Installation

Requires Python 3.11 or higher.

```bash
pip install datefind
```

## Usage

```python
from datefind import find_dates

string = "2024-01-01 and 2024-01-02"

for date in find_dates(string, tz="America/New_York"):
    print(date)

>>> FoundDate(
        datetime=datetime.datetime(2024, 1, 1, 0, 0, tzinfo=zoneinfo.ZoneInfo(key='America/New_York')),
        match='2024-01-01',
        span=(0, 10),
        precision='day'
    )
>>> FoundDate(
        datetime=datetime.datetime(2024, 1, 2, 0, 0, tzinfo=zoneinfo.ZoneInfo(key='America/New_York')),
        match='2024-01-02',
        span=(15, 25),
        precision='day'
    )
```

### find_dates

The `find_dates()` function is the main entry point for the datefind package. It takes a string of text and returns a generator of `FoundDate` objects.

**Arguments**

- `text` - The text to search for dates.
- `first` - The first number to find in ambiguous dates. (one of `month`, `day`, `year`) Default is `month`
- `tz` - The timezone to use, as a name such as `America/New_York` or a `tzinfo` object such as `ZoneInfo("Europe/Paris")`. Defaults to the local timezone.
- `now` - The date that relative dates such as `tomorrow` or `3 days ago` resolve against, as a `date` or a `datetime`. An aware `datetime` is converted to `tz`. A naive `datetime` is read as a time in `tz`. Defaults to the current time.
- `short_digit_dates` - If `True`, runs of 4 to 7 digits with no separators, such as `9819` or `120524`, match as dates. Runs of 8 digits, such as `20240512`, always match. Defaults to `False`, because short digit runs in text are usually years, page numbers, or quantities.

A two-digit year takes the century that puts it within 50 years of `now`. With `now` in 2026, `75` becomes 2075 and `76` becomes 1976.

Pass `now` to get the same results on every run, for example in tests:

```python
from datetime import date

from datefind import find_dates

dates = list(find_dates("call me tomorrow", tz="UTC", now=date(2024, 3, 1)))

>>> dates[0].datetime
datetime.datetime(2024, 3, 2, 0, 0, tzinfo=zoneinfo.ZoneInfo(key='UTC'))
```

For each date found, a `FoundDate` object is returned. The FoundDate object has the following properties:

- `datetime` - The datetime object, at midnight in `tz`.
- `match` - The matched portion of the text.
- `span` - The span of the matched text in the original text.
- `precision` - The unit of time that the text names: `day`, `week`, `month`, `quarter`, or `year`. Counted offsets such as `3 months ago` name one day, so their precision is `day`. A month, quarter, or year with no day returns the first day of that period. For example, `March 2025` returns March 1, 2025. A period relative to `now`, such as `next month` or `last week`, returns the day one period from `now`. For example, `next month` on November 23 returns December 23.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for more information.
