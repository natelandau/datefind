[![Tests](https://github.com/natelandau/datefind/actions/workflows/automated-tests.yml/badge.svg)](https://github.com/natelandau/datefind/actions/workflows/automated-tests.yml) [![codecov](https://codecov.io/gh/natelandau/datefind/graph/badge.svg?token=CXstf6zblD)](https://codecov.io/gh/natelandau/datefind)

# datefind

Find the dates in English text. `datefind` returns each date with the text that matched, its position in the text, and how precise the text is (a day, a week, a month, a quarter, or a year).

```python
from datetime import date

from datefind import find_dates

text = "Invoice sent Friday, January 5, 2024. Payment is due in 2 weeks."

for found in find_dates(text, tz="UTC", now=date(2024, 3, 14)):
    print(found.match, found.datetime.date(), found.precision)
```

```text
Friday, January 5, 2024 2024-01-05 day
in 2 weeks 2024-03-28 day
```

`datefind` reads the year, month, and day only. It does not read times of day.

## Installation

Requires Python 3.11 or higher.

```bash
pip install datefind
```

## Supported formats

The examples use `now=date(2024, 3, 14)`, a Thursday.

| Kind                     | Example text                | Date found | Precision |
| ------------------------ | --------------------------- | ---------- | --------- |
| All numeric              | `2024-01-05`                | 2024-01-05 | day       |
|                          | `01/05/2024`                | 2024-01-05 | day       |
|                          | `20240105`                  | 2024-01-05 | day       |
| Month name               | `January 5th, 2024`         | 2024-01-05 | day       |
|                          | `5 Jan 2024`                | 2024-01-05 | day       |
|                          | `Jan 5 '24`                 | 2024-01-05 | day       |
|                          | `twenty fifth of March`     | 2024-03-25 | day       |
|                          | `March 5`                   | 2024-03-05 | day       |
| Month and year           | `March 2025`                | 2025-03-01 | month     |
|                          | `12/2024`                   | 2024-12-01 | month     |
| Quarter                  | `Q3 2024`, `2024 Q3`        | 2024-07-01 | quarter   |
| Relative word            | `today`                     | 2024-03-14 | day       |
|                          | `day after tomorrow`        | 2024-03-16 | day       |
|                          | `next week`                 | 2024-03-21 | week      |
|                          | `last month`                | 2024-02-14 | month     |
|                          | `next year`                 | 2025-03-14 | year      |
| Counted offset           | `3 days ago`                | 2024-03-11 | day       |
|                          | `in 2 weeks`                | 2024-03-28 | day       |
|                          | `2 weeks after Jan 5, 2024` | 2024-01-19 | day       |
| Day of a relative month  | `3rd of next month`         | 2024-04-03 | day       |
| Weekday                  | `Friday`                    | 2024-03-15 | day       |
|                          | `next Tuesday`              | 2024-03-19 | day       |
|                          | `last Monday`               | 2024-03-11 | day       |

## Usage

### find_dates

`find_dates()` takes a string and returns a generator of `FoundDate` objects, in the order they occur in the text.

**Arguments**

- `text` - The text to search for dates.
- `first` - Which part comes first in an all-number date that can be read more than one way, such as `01/02/03`: `month` (the default), `day`, or `year`.
- `tz` - The timezone of the returned datetimes, as a name such as `America/New_York` or a `tzinfo` object such as `ZoneInfo("Europe/Paris")`. Defaults to the local timezone.
- `now` - The date that relative dates such as `tomorrow` or `3 days ago` resolve against, as a `date` or a `datetime`. An aware `datetime` is converted to `tz`. A naive `datetime` is read as a time in `tz`. Defaults to the current time.
- `short_digit_dates` - If `True`, runs of 4 to 7 digits with no separators, such as `9819` or `120524`, match as dates. Runs of 8 digits, such as `20240512`, always match. Defaults to `False`, because short digit runs in text are usually years, page numbers, or quantities.

Pass `now` to get the same results on every run, for example in tests.

### FoundDate

Each `FoundDate` has these fields:

- `datetime` - The date as a `datetime` at midnight in `tz`.
- `match` - The text that matched, taken from the original text.
- `span` - The start and end positions of `match` in the original text.
- `precision` - The unit of time that the text names: `day`, `week`, `month`, `quarter`, or `year`.

## How dates are read

### Dates that can be read more than one way

An all-number date such as `01/02/03` can put the month, the day, or the year first. The `first` argument decides:

| `first`           | `01/02/03` | `01/02/2024` |
| ----------------- | ---------- | ------------ |
| `month` (default) | 2003-01-02 | 2024-01-02   |
| `day`             | 2003-02-01 | 2024-02-01   |
| `year`            | 2001-02-03 | no date      |

A date that cannot be real in the chosen order, such as `13/01/2024` with `first="month"`, gives no date.

### Years

- Dates with a month name accept years from 1000 to 2999, such as `March 1105` or `dec 31 1899`.
- All-number dates with a day, a month, and a year accept years from 1000 to 2999 when `/`, `-`, or `.` divides the parts, such as `12/25/1850`.
- Every other all-number date must have a year from 1900 to 2099. This applies to dates divided by spaces, a month and year without a day such as `12/2024`, and runs of digits. This rule keeps counts, prices, and ranges such as `10 2500 sold`, `1500.05`, or `pages 10-1500` from matching as dates.
- A two-digit year takes the century that puts it within 50 years of `now`. With `now` in 2026, `75` becomes 2075 and `76` becomes 1976. An apostrophe can mark a two-digit year, as in `Jan 5 '24`.

### Missing parts

- A date without a year takes the year of `now`. `March 5` with `now` in 2024 gives March 5, 2024.
- A month, quarter, or year without a day gives the first day of that period. `March 2025` gives March 1, 2025, and `Q3 2024` gives July 1, 2024.

### Relative dates

- `last`, `this`, and `next` with `week`, `month`, or `year` give the day one period from `now`. `next month` on March 14 gives April 14. The precision is the period, so read the result as "some day in that month".
- A counted offset such as `3 days ago` or `in 2 weeks` gives one day, so its precision is `day`.
- A counted offset before a date shifts that date: `2 weeks after Jan 5, 2024` gives January 19, 2024. If the shift lands on a day that does not exist, as in `1 month after Jan 31, 2024`, there is no date.
- A weekday alone, or with `next`, gives the next one after `now`, never `now` itself. `last` gives the previous one. `this` gives the next one within 0 to 6 days, so it can be `now`.

### What the match includes

A match holds only the words that change the date:

- `next`, `last`, and `this`, as in `next Friday`.
- A counted offset and its direction word, as in `2 weeks after Jan 5, 2024`.
- A weekday directly before a date, as in `Friday, January 5, 2024`. The two give one date, not a date and a separate weekday. If the date states its year and the weekday does not agree with it, as in `Tuesday, January 5, 2024`, the weekday is not part of the match.

Words that only introduce a date, such as `on`, `at`, `by`, `due`, or `the`, are never part of the match. In `due on the 3rd of next month`, the match is `3rd of next month`.

### Text that is not a date

These rules keep common text from matching:

- Because `may` is also a verb, a plain number before it is not a date (`option 2 may work`). Write `2nd May` or `2 of May` instead.
- The weekday abbreviations `sat`, `sun`, and `wed` are also English words. Alone, they match only after `last`, `this`, or `next`. Before a date, they need a comma or a period, as in `Wed, 03 Jan 2024`.
- Month abbreviations such as `mar` or `may` match only as separate words, so `Market` and `Mayfield` are not months. Full month names can touch other letters.
- A version number after `v` or `version`, such as `v2.1.1500`, is not a date.
- A day range in one month, such as `Jan 5-10, 2024` or `Jan 5 to 10`, gives no date. Neither end of the range is reported, so the `10` is not read as the year 2010.
- A date that does not exist, such as `February 30, 2024`, gives no date.

### Times and special characters

- A time after a date, as in `2024-01-05 14:30` or `Jan 5 10pm`, is ignored, and the date before it is found.
- Text copied from web pages and word processors works without cleanup. Non-breaking spaces, en dashes, curly apostrophes, and full-width digits match the same as their plain forms. `match` and `span` refer to the original text.

## Comparison with other libraries

- [dateparser](https://github.com/scrapinghub/dateparser) reads more than 200 languages and times of day. Its `search_dates()` returns pairs of text and datetime without positions in the text, and returns `None` when it finds nothing. Use it for languages other than English or for times.
- [datefinder](https://github.com/akoumjian/datefinder) finds dates and times in English text and returns datetimes. Its `source=True` and `index=True` options change each result into a tuple that holds the matched text and positions.
- `datefind` reads English dates only. Every result holds the matched text, its position, and its precision. It does not fill a missing day with today's day, and it gives no date for a date that does not exist, instead of a nearby one.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for more information.
