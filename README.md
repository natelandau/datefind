[![Tests](https://github.com/natelandau/datefind/actions/workflows/test.yml/badge.svg)](https://github.com/natelandau/datefind/actions/workflows/test.yml) [![codecov](https://codecov.io/gh/natelandau/datefind/graph/badge.svg?token=CXstf6zblD)](https://codecov.io/gh/natelandau/datefind)

# datefind

A python module for locating dates within text. Use this package to search for dates and convert them to datetime objects.

Finds dates in many different formats.

-   All numeric - `2024-01-01`, `01/01/2024`, `01012024`
-   Natural language - `January 1st, 2024`, `March nineteenth, 2024`, `twenty fifth of January`
-   Fuzzy dates - `today`, `yesterday`, `tomorrow`, `last week`, `next week`

> [!NOTE]\
> datefind is designed to be used with year, month, and day only. It does not support hours, minutes, seconds, or microseconds.

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

>>> Date(
    date=datetime.datetime(2024, 1, 1, 0, 0, tzinfo=zoneinfo.ZoneInfo(key='America/New_York')),
    text='2024-01-01 and 2024-01-02',
    match='2024-01-01',
    span=(0, 10)
    )
>>> Date(
    date=datetime.datetime(2024, 1, 2, 0, 0, tzinfo=zoneinfo.ZoneInfo(key='America/New_York')),
    text='2024-01-01 and 2024-01-02',
    match='2024-01-02',
    span=(15, 25)
    )
```

### find_dates

The `find_dates()` function is the main entry point for the datefind package. It takes a string of text and returns a generator of Date objects.

**Arguments**

-   `text` - The text to search for dates.
-   `first` - The first number to find in ambiguous dates. (one of `month`, `day`, `year`) Default is `month`
-   `tz` - The timezone to use. Defaults to the local timezone.

For each date found, a Date object is returned. The Date object has the following properties:

-   `date` - The datetime object.
-   `text` - The full original text.
-   `match` - The matched portion of the text.
-   `span` - The span of the matched text in the original text.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for more information.
