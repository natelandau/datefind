[![Tests](https://github.com/natelandau/datefind/actions/workflows/automated-tests.yml/badge.svg)](https://github.com/natelandau/datefind/actions/workflows/automated-tests.yml) [![codecov](https://codecov.io/gh/natelandau/datefind/graph/badge.svg?token=CXstf6zblD)](https://codecov.io/gh/natelandau/datefind)

# datefind

A python module for locating dates within text. Use this package to search for dates and convert them to datetime objects.

Finds dates in many different formats.

- All numeric - `2024-01-01`, `01/01/2024`, `01012024`, etc.
- Natural language - `January 1st, 2024`, `March nineteenth, 2024`, `twenty fifth of January`, `Mar 15, 24`, etc.
- Fuzzy dates - `today`, `yesterday`, `tomorrow`, `last week`, `this week`, `next week`, etc.
- Relative offsets - `3 days ago`, `in 2 weeks`, `1 year from now`, etc.
- Weekdays - `Monday`, `next Friday`, `last Tuesday`, etc. The abbreviations `sat`, `sun`, and `wed` are also English words, so they match only after `last`, `this`, or `next`.
- Quarters - `Q1 2024`, `2024 Q3`, etc.

> [!NOTE]\
> `datefind` is designed to be used with year, month, and day only. It does not support hours, minutes, seconds, or microseconds.

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
        span=(0, 10)
    )
>>> FoundDate(
        datetime=datetime.datetime(2024, 1, 2, 0, 0, tzinfo=zoneinfo.ZoneInfo(key='America/New_York')),
        match='2024-01-02',
        span=(15, 25)
    )
```

### find_dates

The `find_dates()` function is the main entry point for the datefind package. It takes a string of text and returns a generator of `FoundDate` objects.

**Arguments**

- `text` - The text to search for dates.
- `first` - The first number to find in ambiguous dates. (one of `month`, `day`, `year`) Default is `month`
- `tz` - The timezone to use, as a name such as `America/New_York` or a `tzinfo` object such as `ZoneInfo("Europe/Paris")`. Defaults to the local timezone.
- `now` - The date that relative dates such as `tomorrow` or `3 days ago` resolve against, as a `date` or a `datetime`. An aware `datetime` is converted to `tz`. A naive `datetime` is read as a time in `tz`. Defaults to the current time.

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

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for more information.
