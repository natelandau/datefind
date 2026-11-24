"""Tests for datefind."""

import json
import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta, tzinfo
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from datefind import find_date, find_dates

fixture_file = Path(__file__).parent / "fixture.txt"


@pytest.mark.parametrize("search", [find_dates, find_date])
@pytest.mark.parametrize("invalid_tz", ["America/California", "/etc/localtime", "Foo/../Bar"])
def test_raise_error_on_invalid_timezone(search: Callable[..., object], invalid_tz: str) -> None:
    """Verify ValueError raised when invalid timezone provided, before any date is searched for."""
    # When/Then: the search raises ValueError naming the timezone
    with pytest.raises(ValueError, match=f"Invalid timezone: {re.escape(invalid_tz)}"):
        search("Hello, world! Today is 2024-01-01.", tz=invalid_tz)


@pytest.mark.parametrize(
    ("text", "first", "expected"),
    [
        ("9819", "month", date(2019, 9, 8)),
        ("2024112", "month", date(2024, 11, 2)),
        ("2111999", "month", date(1999, 2, 11)),
        ("120524", "month", date(2024, 12, 5)),
        ("120524", "day", date(2024, 5, 12)),
        ("202412", "month", date(2024, 12, 1)),
    ],
)
@freeze_time("2024-03-01")
def test_short_digit_dates(
    text: str, first: Literal["month", "day", "year"], expected: date, debug
) -> None:
    """Verify runs of 4 to 7 digits read as dates when the caller opts in."""
    # When: finding dates with short digit runs enabled
    dates = list(find_dates(text, first=first, tz="UTC", short_digit_dates=True))

    # Then: the whole run is one date
    assert [found.datetime.date() for found in dates] == [expected]
    assert dates[0].match == text
    assert dates[0].span == (0, len(text))


@pytest.mark.parametrize(
    ("text", "now", "expected"),
    [
        ("born 12/25/85", date(2026, 11, 23), date(1985, 12, 25)),
        ("march 3rd 75", date(2026, 11, 23), date(2075, 3, 3)),
        ("march 3rd 76", date(2026, 11, 23), date(1976, 3, 3)),
        ("1/2/00", date(2026, 11, 23), date(2000, 1, 2)),
        # The window follows the reference date, not the clock
        ("march 3rd 39", date(1990, 1, 1), date(2039, 3, 3)),
        ("march 3rd 40", date(1990, 1, 1), date(1940, 3, 3)),
        ("Q4'75", date(2026, 11, 23), date(2075, 10, 1)),
        ("Q4'76", date(2026, 11, 23), date(1976, 10, 1)),
    ],
)
def test_two_digit_year_century(text: str, now: date, expected: date, debug) -> None:
    """Verify a two-digit year takes the century that keeps it within 50 years of the reference date."""
    # When: finding dates with a reference date
    dates = list(find_dates(text, tz="UTC", now=now))

    # Then: the year lands in the expected century
    assert [found.datetime.date() for found in dates] == [expected]


@pytest.mark.parametrize(
    ("text", "now", "tz", "expected"),
    [
        # A date resolves relative words against that day
        ("tomorrow", date(2024, 3, 1), "UTC", datetime(2024, 3, 2, tzinfo=ZoneInfo("UTC"))),
        ("next friday", date(2024, 3, 1), "UTC", datetime(2024, 3, 8, tzinfo=ZoneInfo("UTC"))),
        # An aware datetime is converted to the output timezone, then cut to midnight
        (
            "today",
            datetime(2024, 3, 1, 23, 30, tzinfo=ZoneInfo("UTC")),
            "Asia/Tokyo",
            datetime(2024, 3, 2, tzinfo=ZoneInfo("Asia/Tokyo")),
        ),
        # A naive datetime is read as a wall-clock time in the output timezone
        (
            "3 days ago",
            datetime(2024, 3, 1, 23, 30),
            "Asia/Tokyo",
            datetime(2024, 2, 27, tzinfo=ZoneInfo("Asia/Tokyo")),
        ),
        # The timezone can be a tzinfo object instead of a name
        (
            "yesterday",
            date(2024, 3, 1),
            ZoneInfo("Asia/Tokyo"),
            datetime(2024, 2, 29, tzinfo=ZoneInfo("Asia/Tokyo")),
        ),
        ("2024-01-12", date(2024, 3, 1), UTC, datetime(2024, 1, 12, tzinfo=UTC)),
    ],
)
def test_find_dates_with_reference_date(
    text: str, now: date | datetime, tz: str | tzinfo, expected: datetime, debug
) -> None:
    """Verify dates resolve against the caller's reference date, at midnight in the output timezone."""
    # When: finding dates with an explicit reference date
    dates = list(find_dates(text, tz=tz, now=now))

    # Then: the single date matches exactly, including time of day and timezone
    assert [found.datetime for found in dates] == [expected]
    assert dates[0].datetime.tzinfo == expected.tzinfo


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("01-12", []),
        ("2024-24-12", []),
        ("2024-01-32", []),
        ("march thirtysecond 2025", []),
        ("hello world", []),
        ("2019-99-01", []),
        ("30122022", []),  # fails b/c month is first
        ("01122024", ["2024-01-12"]),
        ("01:12:2024", ["2024-01-12"]),
        ("2024-01-12", ["2024-01-12"]),
        ("2024/01/12", ["2024-01-12"]),
        ("20240112", ["2024-01-12"]),
        ("2024-1-12", ["2024-01-12"]),
        ("2024/1/12", ["2024-01-12"]),
        ("2024112", []),
        ("12112022", ["2022-12-11"]),
        ("2111999", []),
        # Runs of 4 to 7 digits match only with short_digit_dates=True
        ("9819", []),
        ("1985", []),
        ("120524", []),
        ("202412", []),
        ("order 120524 shipped", []),
        # No part of a run longer than 8 digits matches
        ("1234567890", []),
        ("202405121", []),
        # A separator or month name marks the year, so years 1000 to 2999 match
        ("dec 31 1899", ["1899-12-31"]),
        ("12/25/1850", ["1850-12-25"]),
        ("1850-12-25", ["1850-12-25"]),
        ("March 1105", ["1105-03"]),
        ("Q2 1500", ["1500-Q2"]),
        ("2999-12-31", ["2999-12-31"]),
        ("12/25/0999", []),
        ("3000-01-01", []),
        ("call 555-1212", []),
        # A year glued to the quarter needs a year from 1900 to 2099
        ("Q31500", []),
        ("Q32024", ["2024-Q3"]),
        # A day glued to the year after a month name needs a year from 1900 to 2099
        ("March 31105", []),
        ("jan 12500 units", []),
        ("march 21500", []),
        ("March 31999", ["1999-03-03"]),
        # In all-number dates, years outside 1900 to 2099 need a / - or . separator
        ("10 2500 sold", []),
        ("page 12, 1500 words", []),
        ("12 25 1850", []),
        ("1850 12 25", []),
        ("12 . 25 . 1850", ["1850-12-25"]),
        # A numeric month and year without a day needs a year from 1900 to 2099
        ("12/1500", []),
        ("1850.12", []),
        ("price 1500.05", []),
        ("lat 10.1234", []),
        ("pages 10-1500", []),
        # A three-letter month abbreviation inside a longer word is not a month
        ("grammar 1500 words", []),
        ("2500 Market Street", []),
        ("1500 Mayfield Rd", []),
        ("Kumar 1500", []),
        ("2022-12", ["2022-12"]),
        ("12 2022", ["2022-12"]),
        ("03/2025", ["2025-03"]),
        ("2025 march", ["2025-03"]),
        ("2025 March 1", ["2025-03-01"]),
        ("3/1/25", ["2025-03-01"]),
        ("sep. 4", ["2024-09-04"]),
        ("sept. fifth", ["2024-09-05"]),
        ("2022, 12, 24", ["2022-12-24"]),
        ("23 march, 2020", ["2020-03-23"]),
        ("23rd, march-2020", ["2020-03-23"]),
        ("23rd of march 2020", ["2020-03-23"]),
        ("fifteenth march, 2025", ["2025-03-15"]),
        ("twenty fifth of march, 2025", ["2025-03-25"]),
        ("twentyfifth of march, 2025", ["2025-03-25"]),
        ("march 23", ["2024-03-23"]),
        ("march 23 2025", ["2025-03-23"]),
        ("march 21st 2025", ["2025-03-21"]),
        ("march the 23rd 2025", ["2025-03-23"]),
        ("march the 23rd of 2025", ["2025-03-23"]),
        ("march 23rd", ["2024-03-23"]),
        ("march the 22nd", ["2024-03-22"]),
        ("march twenty second", ["2024-03-22"]),
        ("march the twentysecond", ["2024-03-22"]),
        ("march the first of 2025", ["2025-03-01"]),
        # Day before month, without a year
        ("14 feb", ["2024-02-14"]),
        ("25 December", ["2024-12-25"]),
        ("3rd march", ["2024-03-03"]),
        ("twenty fifth of december", ["2024-12-25"]),
        ("31 feb", []),
        # "may" is also a verb, so a bare number before it needs "of", "the", or an ordinal
        ("2nd May", ["2024-05-02"]),
        ("2nd of May", ["2024-05-02"]),
        ("2 of may", ["2024-05-02"]),
        ("second of may", ["2024-05-02"]),
        ("2 may", []),
        ("option 2 may work", []),
        ("Mar 15, 24", ["2024-03-15"]),
        ("March 15 24", ["2024-03-15"]),
        ("march 3rd 99", ["1999-03-03"]),
        ("march 20 2025", ["2025-03-20"]),
        ("march 2025", ["2025-03"]),
        ("january, of 1998", ["1998-01"]),
        ("second january, of 1998", ["1998-01-02"]),
        ("today", ["2024-03-01"]),
        ("yesterday", ["2024-02-29"]),
        ("tomorrow", ["2024-03-02"]),
        ("last week", ["2024-W08"]),
        ("next week", ["2024-W10"]),
        ("last month", ["2024-02"]),
        ("next month", ["2024-04"]),
        ("last year", ["2023"]),
        ("next year", ["2025"]),
        ("this week", ["2024-W09"]),
        ("this month", ["2024-03"]),
        ("this year", ["2024"]),
        ("Q1 2024", ["2024-Q1"]),
        ("Q2 2024", ["2024-Q2"]),
        ("Q3 2024", ["2024-Q3"]),
        ("Q4 2024", ["2024-Q4"]),
        ("q1 2024", ["2024-Q1"]),
        ("Q1-2024", ["2024-Q1"]),
        ("2024 Q1", ["2024-Q1"]),
        ("2024-Q4", ["2024-Q4"]),
        ("Q5 2024", []),
        ("Q1", []),
        # Quarter and half-year forms
        ("2nd quarter of 2024", ["2024-Q2"]),
        ("second quarter 2024", ["2024-Q2"]),
        ("Q4'23", ["2023-Q4"]),
        ("Q4 '23", ["2023-Q4"]),
        ("4Q23", ["2023-Q4"]),
        ("4Q 2023", ["2023-Q4"]),
        ("H1 2024", ["2024-H1"]),
        ("H2 2024", ["2024-H2"]),
        ("2024 H2", ["2024-H2"]),
        ("H1'24", ["2024-H1"]),
        ("1H 2024", ["2024-H1"]),
        ("2H24", ["2024-H2"]),
        ("first half of 2024", ["2024-H1"]),
        ("2nd half 2024", ["2024-H2"]),
        ("H3 2024", []),
        ("5th quarter of 2024", []),
        ("H2", []),
        ("2nd quarter", []),
        # An ISO week gives its Monday
        ("2024-W23", ["2024-W23"]),
        ("2024W23", ["2024-W23"]),
        ("W23 2024", ["2024-W23"]),
        ("week 23 2024", ["2024-W23"]),
        ("week 23 of 2024", ["2024-W23"]),
        ("week 12 2024", ["2024-W12"]),
        ("W23 '24", ["2024-W23"]),
        ("2026-W01", ["2026-W01"]),
        ("2020-W53", ["2020-W53"]),
        ("2021-W53", []),
        ("2024-W54", []),
        ("week 23", []),
        ("W23", []),
        ("2024-W23-2", []),
        # An HTML heading tag or a longer word is not a half year
        ("<h1 2024", []),
        ("</h1 2024", []),
        ("CH1 2024", []),
        # Durations are not half years: a number-first half needs a capital H
        ("1H 20", []),
        ("2h 30m", []),
        ("1h20", []),
        ("Total time 1h45m.", []),
        ("step 1h 2024", []),
        ("In 2020 2h of downtime", []),
        # A count after the part is not its year
        ("1 quarter 2024", []),
        ("3 quarter of 2024", []),
        ("In week 3, 1500 users signed up", []),
        ("In the first half, 1200 people came", []),
        ("H2 1000 kg of hydrogen", []),
        ("H1 1080p", []),
        ("Q3, 1500 units", []),
        ("4Q 1500 units", []),
        ("4th quarter 1500 fans left", []),
        ("Q3, 2024", ["2024-Q3"]),
        # A year glued to a number-first part takes the narrow range, like "Q31500"
        ("4Q1500", []),
        ("4Q2024", ["2024-Q4"]),
        # Digits glued to a year before a number-first part belong to a longer number
        ("SKU 20243Q", []),
        ("2024Q3", ["2024-Q3"]),
        # An apostrophe and two digits before a letter name a decade, not a year
        ("Jan '90s fashion", []),
        ("Q3 '90s", []),
        # A bare W needs a two-digit week, so tax forms are not weeks
        ("Attach your W2 2024 form", []),
        ("week 5 2024", ["2024-W05"]),
        # Bare weekday — next occurrence
        ("Monday", ["2024-03-04"]),
        ("Friday", ["2024-03-08"]),
        ("mon", ["2024-03-04"]),
        ("sunday", ["2024-03-03"]),
        # Relative weekday
        ("next Monday", ["2024-03-04"]),
        ("last Monday", ["2024-02-26"]),
        ("this Monday", ["2024-03-04"]),
        ("this Friday", ["2024-03-01"]),
        ("last Friday", ["2024-02-23"]),
        ("next Friday", ["2024-03-08"]),
        ("next sat", ["2024-03-02"]),
        ("last sun", ["2024-02-25"]),
        ("this wed", ["2024-03-06"]),
        # Bare weekday substring prevention
        ("among friends", []),
        ("sunlight", []),
        ("c'mon", []),
        # Abbreviations that are also English words need a modifier
        ("I sat down on the sun deck", []),
        ("they wed", []),
        # Version numbers after "v" or "version" are not dates
        ("version 2.1.1500", []),
        ("v2.1.1500", []),
        ("V1.2.2024", []),
        ("Version: 1.2.2024", []),
        # Relative count patterns
        ("3 days ago", ["2024-02-27"]),
        ("in 3 days", ["2024-03-04"]),
        ("3 days from now", ["2024-03-04"]),
        ("1 day ago", ["2024-02-29"]),
        ("2 weeks ago", ["2024-02-16"]),
        ("in 2 weeks", ["2024-03-15"]),
        ("2 weeks from now", ["2024-03-15"]),
        ("1 month ago", ["2024-02-01"]),
        ("in 2 months", ["2024-05-01"]),
        ("2 years ago", ["2022-03-01"]),
        ("in 1 year", ["2025-03-01"]),
        ("1 year from now", ["2025-03-01"]),
        ("0 days ago", ["2024-03-01"]),
        ("days ago", []),
        ("in days", []),
        # Word-boundary anchoring for relative counts
        ("spin 3 days", []),
        ("contain 2 weeks", []),
        ("in 2 weekly", []),
        ("in 3 daysx", []),
        ("1000000 days ago", []),
        ("99999999999 days ago", []),
        # Calendar-invalid dates
        ("February 30, 2024", []),
        ("Feb 29 2023", []),
        # Two-letter words are not month abbreviations
        ("No 10", []),
        ("ma 15", []),
        # Word-boundary anchoring for natural dates
        ("this weekend", []),
        ("next monthly", []),
        ("ultimatoday", []),
        # A number followed by a year is not split into month, day, and two-digit year
        ("3, 2024", []),
        # Case-insensitive matching treats long s (U+017F) as "s" and dotted capital I (U+0130) as "i"
        ("la\u017ft week", ["2024-W08"]),
        ("th\u0130s month", ["2024-03"]),
        ("today\u017f", ["2024-03-01"]),
        ("fir\u017ft of march 2024", ["2024-03-01"]),
        ("\u017funday", ["2024-03-03"]),
        ("la\u017ft monday", ["2024-02-26"]),
        ("\u017feptember 5 2024", ["2024-09-05"]),
        ("in 2 day\u017f", ["2024-03-03"]),
        # A count too long to convert to an integer is not a date
        ("in " + "9" * 5000 + " days", []),
        # A weekday before a date is part of that date
        ("Friday, January 5, 2024", ["2024-01-05"]),
        ("Wed, 03 Jan 2024", ["2024-01-03"]),
        ("Sat. 6 January", ["2024-01-06"]),
        ("Friday the 5th of January 2024", ["2024-01-05"]),
        ("Fri 01/05/2024", ["2024-01-05"]),
        ("Thursday 2024-01-04", ["2024-01-04"]),
        # Two days away
        ("day after tomorrow", ["2024-03-03"]),
        ("day before yesterday", ["2024-02-28"]),
        # A day of the month relative to this month
        ("3rd of next month", ["2024-04-03"]),
        ("twentieth of last month", ["2024-02-20"]),
        ("15 of this month", ["2024-03-15"]),
        ("31st of next month", []),
        # A day range after a month name is not a day and a two-digit year
        ("Jan 5-10", []),
        ("Jan 5 - 10", []),
        ("Jan 5-10, 2024", []),
        ("Jan 5\u201310, 2024", []),
        ("Jan 5 \u2013 10, 2024", []),
        ("Jan 5 to 10, 2024", []),
        ("Jan-05-24", ["2024-01-05"]),
        ("Jan 05-24", ["2024-01-05"]),
        ("March 5-2024", ["2024-03-05"]),
        # Unicode spaces, dashes, apostrophes, and full-width digits read as their ASCII forms
        ("January 5,\u00a02024", ["2024-01-05"]),
        ("Jan\u00a05, 2024", ["2024-01-05"]),
        ("2024\u201301\u201305", ["2024-01-05"]),
        ("\uff12\uff10\uff12\uff14-01-05", ["2024-01-05"]),
        # An apostrophe marks a two-digit year
        ("Jan 5 '24", ["2024-01-05"]),
        ("Jan 5 \u201924", ["2024-01-05"]),
        ("Jan '24", ["2024-01"]),
        ("January '24", ["2024-01"]),
        ("Jan \u201924", ["2024-01"]),
        # Without an apostrophe, a number after a month name is a day
        ("Jan 24", ["2024-01-24"]),
        # A decimal number before a comma and a number is not a date
        ("3.8, 10", []),
        ("3-8, 10", []),
        ("3/8, 10", []),
        # A four-digit year after mixed separators still marks a date
        ("12/25, 2024", ["2024-12-25"]),
        ("12-25 2024", ["2024-12-25"]),
        # A counted offset before a date shifts that date
        ("2 weeks after Jan 5, 2024", ["2024-01-19"]),
        ("2 weeks after the 5th of January 2024", ["2024-01-19"]),
        ("2 weeks after Tuesday, Jan 5, 2024", ["2024-01-19"]),
        ("3 days before 2024-01-01", ["2023-12-29"]),
        ("1 year from Feb 29, 2024", []),
    ],
)
@freeze_time("2024-03-01")
def test_find_dates(text, expected, debug):
    """Verify extracting dates from short text returns the expected standard date strings."""
    # When: Finding dates in the text
    dates = list(find_dates(text, first="month", tz="UTC"))

    # Then: each found date covers the whole text and has the expected standard string
    assert [found.value for found in dates] == expected
    for found in dates:
        assert found.match == text
        assert found.span == (0, len(text))


def test_as_dict() -> None:
    """Verify as_dict gives plain values that serialize to JSON."""
    # Given: a date found in text
    found = next(find_dates(text="Paid in March 2024.", tz="UTC", now=date(2026, 11, 23)))
    expected = {
        "value": "2024-03",
        "date": "2024-03-01",
        "precision": "month",
        "match": "March 2024",
        "span": [8, 18],
    }

    # When/Then: the dict holds plain values and survives a JSON round trip
    assert found.as_dict() == expected
    assert json.loads(json.dumps(found.as_dict())) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Due Jan 5, 2024 or Feb 1, 2024", "2024-01-05"),
        ("no dates here", None),
    ],
)
def test_find_date(text: str, expected: str | None) -> None:
    """Verify find_date returns the first date in the text, or None when there is none."""
    # When: finding the first date
    found = find_date(text=text, tz="UTC", now=date(2026, 11, 23))

    # Then: it is the earliest date in the text, or None
    assert (found.value if found else None) == expected


@freeze_time("2024-03-01")
def test_find_dates_in_file(debug):
    """Verify extracting dates from a large text input returns expected datetime objects."""
    file = Path(__file__).parent / "fixture.txt"
    text = file.read_text()

    expected = [
        datetime(2025, 3, 22, tzinfo=ZoneInfo("UTC")),
        datetime(1999, 9, 13, tzinfo=ZoneInfo("UTC")),
        datetime(2024, 12, 2, tzinfo=ZoneInfo("UTC")),
        datetime(2023, 7, 4, tzinfo=ZoneInfo("UTC")),
        datetime(2024, 5, 12, tzinfo=ZoneInfo("UTC")),
        datetime(2024, 1, 12, tzinfo=ZoneInfo("UTC")),
        datetime(2024, 1, 9, tzinfo=ZoneInfo("UTC")),
        datetime(2025, 1, 23, tzinfo=ZoneInfo("UTC")),
        datetime(1999, 3, 1, tzinfo=ZoneInfo("UTC")),
        datetime(2024, 2, 1, tzinfo=ZoneInfo("UTC")),
        datetime(2024, 8, 2, tzinfo=ZoneInfo("UTC")),
        datetime(2024, 1, 10, tzinfo=ZoneInfo("UTC")),
        datetime(2024, 4, 1, tzinfo=ZoneInfo("UTC")),
        datetime(1999, 8, 25, tzinfo=ZoneInfo("UTC")),
        datetime(datetime.now(ZoneInfo("UTC")).year, 1, 11, tzinfo=ZoneInfo("UTC")),
        datetime(datetime.now(ZoneInfo("UTC")).year, 3, 11, tzinfo=ZoneInfo("UTC")),
        datetime(1999, 12, 1, tzinfo=ZoneInfo("UTC")),
        datetime(2024, 1, 10, tzinfo=ZoneInfo("UTC")),
        datetime.now(ZoneInfo("UTC")),
        datetime.now(ZoneInfo("UTC")) - timedelta(days=1),
        datetime.now(ZoneInfo("UTC")) + timedelta(days=1),
        datetime.now(ZoneInfo("UTC")) - timedelta(days=7),
        datetime.now(ZoneInfo("UTC")) + timedelta(days=7),
        datetime.now(ZoneInfo("UTC")).replace(year=datetime.now(ZoneInfo("UTC")).year - 1),
        # New paragraph: Q1 2024, 2024 Q3, next Monday, March 15 24, 3 days ago, in 2 weeks,
        # This month, this year's, last Friday
        datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),  # Q1 2024
        datetime(2024, 7, 1, tzinfo=ZoneInfo("UTC")),  # 2024 Q3
        datetime.now(ZoneInfo("UTC"))
        + timedelta(days=(0 - datetime.now(ZoneInfo("UTC")).weekday()) % 7 or 7),  # next Monday
        datetime(2024, 3, 15, tzinfo=ZoneInfo("UTC")),  # March 15, 24
        datetime.now(ZoneInfo("UTC")) - timedelta(days=3),  # 3 days ago
        datetime.now(ZoneInfo("UTC")) + timedelta(days=14),  # in 2 weeks
        datetime.now(ZoneInfo("UTC")),  # This month
        datetime.now(ZoneInfo("UTC")),  # this year's
        datetime.now(ZoneInfo("UTC"))
        - timedelta(days=(datetime.now(ZoneInfo("UTC")).weekday() - 4) % 7 or 7),  # last Friday
    ]

    # When: Finding dates in the text
    dates = list(find_dates(text, first="month", tz="UTC"))

    # Then: Each found date matches expected datetime
    assert len(dates) == len(expected)
    for i, found in enumerate(dates):
        assert found.datetime.strftime("%Y-%m-%d") == expected[i].strftime("%Y-%m-%d")


@pytest.mark.parametrize(
    ("text", "first", "expected"),
    [
        ("2024-01-12", "day", [datetime(2024, 12, 1, tzinfo=ZoneInfo("UTC"))]),
        ("1-12-2024", "day", [datetime(2024, 12, 1, tzinfo=ZoneInfo("UTC"))]),
        ("01-12-24", "day", [datetime(2024, 12, 1, tzinfo=ZoneInfo("UTC"))]),
        ("1-12-24", "day", [datetime(2024, 12, 1, tzinfo=ZoneInfo("UTC"))]),
        ("1-2-24", "day", [datetime(2024, 2, 1, tzinfo=ZoneInfo("UTC"))]),
        ("2024-01-12", "month", [datetime(2024, 1, 12, tzinfo=ZoneInfo("UTC"))]),
        ("1-12-2024", "month", [datetime(2024, 1, 12, tzinfo=ZoneInfo("UTC"))]),
        ("01-12-24", "month", [datetime(2024, 1, 12, tzinfo=ZoneInfo("UTC"))]),
        ("1-12-24", "month", [datetime(2024, 1, 12, tzinfo=ZoneInfo("UTC"))]),
        ("1-2-24", "month", [datetime(2024, 1, 2, tzinfo=ZoneInfo("UTC"))]),
        ("2024-01-12", "year", [datetime(2024, 1, 12, tzinfo=ZoneInfo("UTC"))]),
        ("1-12-2024", "year", []),
        ("01-12-24", "year", [datetime(2001, 12, 24, tzinfo=ZoneInfo("UTC"))]),
        ("2001-12-24", "year", [datetime(2001, 12, 24, tzinfo=ZoneInfo("UTC"))]),
        ("01-2-1", "year", [datetime(2001, 2, 1, tzinfo=ZoneInfo("UTC"))]),
        ("2001-02-1", "year", [datetime(2001, 2, 1, tzinfo=ZoneInfo("UTC"))]),
        ("2001-2-01", "year", [datetime(2001, 2, 1, tzinfo=ZoneInfo("UTC"))]),
        ("16041905", "day", [datetime(1905, 4, 16, tzinfo=ZoneInfo("UTC"))]),
    ],
)
@freeze_time("2024-03-01")
def test_first_number(
    text: str, first: Literal["month", "day", "year"], expected: list[datetime], debug
) -> None:
    """Verify extracting dates from text returns expected datetime objects."""
    # Given: Text containing dates and expected datetime
    # When: Finding dates in the text
    dates = list(find_dates(text, first=first, tz="UTC"))

    # Then: Each found date matches expected datetime
    assert len(dates) == len(expected)
    for i, found in enumerate(dates):
        assert found.datetime.strftime("%Y-%m-%d") == expected[i].strftime("%Y-%m-%d")


def test_date_object(debug):
    """Verify FoundDate object has expected properties."""
    text = "Hello, world! 2024-01-12 and jan. eighteenth, 2024"
    dates = list(find_dates(text, first="month", tz="UTC"))
    assert len(dates) == 2
    assert dates[0].datetime == datetime(2024, 1, 12, tzinfo=ZoneInfo("UTC"))
    assert dates[0].match == "2024-01-12"
    assert dates[0].span == (14, 24)

    assert dates[1].datetime == datetime(2024, 1, 18, tzinfo=ZoneInfo("UTC"))
    assert dates[1].match == "jan. eighteenth, 2024"
    assert dates[1].span == (29, 50)


@freeze_time("2024-02-29")
def test_leap_year(debug):
    """Verify leap year is handled correctly."""
    text = "last year"
    dates = list(find_dates(text, first="month", tz="UTC"))
    assert len(dates) == 0


@freeze_time("2024-03-31")
def test_last_month(debug):
    """Verify last month is handled correctly."""
    text = "last month"
    dates = list(find_dates(text, first="month", tz="UTC"))
    assert len(dates) == 0


@freeze_time("2024-01-15")
def test_last_month_crosses_year_boundary(debug):
    """Verify 'last month' from January resolves to December of the prior year."""
    # Given: today is January 15, 2024
    # When: parsing "last month"
    dates = list(find_dates("last month", first="month", tz="UTC"))
    # Then: resolves to December 15, 2023
    assert len(dates) == 1
    assert dates[0].datetime.strftime("%Y-%m-%d") == "2023-12-15"


@freeze_time("2024-12-15")
def test_next_month_crosses_year_boundary(debug):
    """Verify 'next month' from December resolves to January of the next year."""
    # Given: today is December 15, 2024
    # When: parsing "next month"
    dates = list(find_dates("next month", first="month", tz="UTC"))
    # Then: resolves to January 15, 2025
    assert len(dates) == 1
    assert dates[0].datetime.strftime("%Y-%m-%d") == "2025-01-15"


@freeze_time("2024-03-31")
def test_relative_count_month_end_edge(debug):
    """Verify 'in 1 month' from March 31 returns no match (April has no 31st)."""
    # Given: today is March 31, 2024
    # When: parsing "in 1 month"
    dates = list(find_dates("in 1 month", first="month", tz="UTC"))
    # Then: no date resolved (April 31 is invalid)
    assert len(dates) == 0


@freeze_time("2024-02-29")
def test_relative_count_leap_day(debug):
    """Verify '1 year ago' from Feb 29 returns no match (2023 is not a leap year)."""
    # Given: today is Feb 29, 2024 (leap day)
    # When: parsing "1 year ago"
    dates = list(find_dates("1 year ago", first="month", tz="UTC"))
    # Then: no date resolved (Feb 29, 2023 does not exist)
    assert len(dates) == 0


@freeze_time("2024-03-01")
def test_find_dates_partial_match_in_word_context(debug):
    """Verify weekday patterns match only whole words, not substrings of other words."""
    # Given: text where a full weekday word appears alongside a word that contains a weekday substring
    text = "thursday thunder"

    # When: finding dates
    dates = list(find_dates(text, first="month", tz="UTC"))

    # Then: only the full weekday word matches; "thu" inside "thunder" does not
    assert len(dates) == 1
    assert dates[0].datetime.strftime("%Y-%m-%d") == "2024-03-07"
    assert dates[0].match == "thursday"
    assert dates[0].span == (0, 8)


def test_find_dates_after_word_ending_in_v(debug):
    """Verify only a standalone "v" marks a version number, not a word that ends in v."""
    # Given: a date after a word ending in "v"
    text = "dev 1.2.2024"

    # When: finding dates
    dates = list(find_dates(text, first="month", tz="UTC"))

    # Then: the date still matches
    assert [(found.match, found.datetime.date()) for found in dates] == [
        ("1.2.2024", date(2024, 1, 2))
    ]


@freeze_time("2024-03-01")
def test_find_dates_month_name_after_number(debug):
    """Verify a month name preceded by a number still anchors a month-first date."""
    # Given: a month-first date that follows an unrelated number
    text = "item 5 January 3, 2024"

    # When: finding dates
    dates = list(find_dates(text, first="month", tz="UTC"))

    # Then: the full month-first date matches
    assert len(dates) == 1
    assert dates[0].datetime.strftime("%Y-%m-%d") == "2024-01-03"
    assert dates[0].match == "January 3, 2024"


@pytest.mark.parametrize(
    ("text", "expected_match", "expected_date"),
    [
        ("05 Jan 2024 10:00:00", "05 Jan 2024", date(2024, 1, 5)),
        ("Wed, 03 Jan 2024 10:00:00 +0000", "Wed, 03 Jan 2024", date(2024, 1, 3)),
        ("2024-01-05 14:30", "2024-01-05", date(2024, 1, 5)),
        ("1/5/2024 9:15 am", "1/5/2024", date(2024, 1, 5)),
        ("Jan 5, 2024, 3 PM", "Jan 5, 2024", date(2024, 1, 5)),
        ("Jan 5 10:00:00", "Jan 5", date(2024, 1, 5)),
        ("Jan 5 10pm", "Jan 5", date(2024, 1, 5)),
        ("Jan 5 10 p.m.", "Jan 5", date(2024, 1, 5)),
        ("14 Feb 10:00", "14 Feb", date(2024, 2, 14)),
        ("next friday 3pm", "next friday", date(2024, 3, 8)),
        ("today 10:30", "today", date(2024, 3, 1)),
        ("March 5 24:00", "March 5", date(2024, 3, 5)),
    ],
)
def test_find_dates_followed_by_time(
    text: str, expected_match: str, expected_date: date, debug
) -> None:
    """Verify a time of day after a date leaves the date found and is not read as part of it."""
    # When: finding dates in text where a time follows the date
    dates = list(find_dates(text, tz="UTC", now=date(2024, 3, 1)))

    # Then: only the date part matches
    assert [(found.match, found.datetime.date()) for found in dates] == [
        (expected_match, expected_date)
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # A range across two months gives both dates
        (
            "Jan 28 - 3 Feb",
            [("Jan 28", date(2024, 1, 28)), ("3 Feb", date(2024, 2, 3))],
        ),
        (
            "Jan 5 - 10 March",
            [("Jan 5", date(2024, 1, 5)), ("10 March", date(2024, 3, 10))],
        ),
        # "sat" is a verb unless punctuation marks it as a weekday
        ("we sat 2 jan 2024", [("2 jan 2024", date(2024, 1, 2))]),
        # A bare number before a possessive month counts items, not days
        ("page 2 of this month's issue", [("this month's", date(2024, 3, 1))]),
        ("the day after tomorrow", [("day after tomorrow", date(2024, 3, 3))]),
        ("on the 3rd of next month", [("3rd of next month", date(2024, 4, 3))]),
        # A weekday already part of an earlier date is not also part of the next date
        (
            "next Friday, January 5",
            [("next Friday", date(2024, 3, 8)), ("January 5", date(2024, 1, 5))],
        ),
        # A weekday that disagrees with its date is not part of the date, nor a date of its own
        ("Tuesday, January 5, 2024", [("January 5, 2024", date(2024, 1, 5))]),
        # Without a stated year the year is a guess, so the weekday stays part of the date
        ("Tuesday, January 5", [("Tuesday, January 5", date(2024, 1, 5))]),
        # A weekday between an offset and its date is part of that date
        (
            "2 weeks after Friday, Jan 5, 2024",
            [("2 weeks after Friday, Jan 5, 2024", date(2024, 1, 19))],
        ),
        # "from" before the first day of a range is not an offset
        (
            "3 years from 2020-01-01 to 2023-01-01",
            [("2020-01-01", date(2020, 1, 1)), ("2023-01-01", date(2023, 1, 1))],
        ),
        # A half year inside a sentence
        ("revenue rose in H1 2024.", [("H1 2024", date(2024, 1, 1))]),
        # A decade after a day is not its year
        ("Jan 5 '90s", [("Jan 5", date(2024, 1, 5))]),
        # A number before a part of a year does not stop it from matching
        ("Table 3 week 12 2024", [("week 12 2024", date(2024, 3, 18))]),
        ("Up 5 first quarter 2024", [("first quarter 2024", date(2024, 1, 1))]),
        (
            "H1 2024 H2 2024",
            [("H1 2024", date(2024, 1, 1)), ("H2 2024", date(2024, 7, 1))],
        ),
        ("Revenue 2023 H1 2024 down", [("H1 2024", date(2024, 1, 1))]),
        # A weekday not directly before a date stays a date of its own
        (
            "Monday, then January 5",
            [("Monday", date(2024, 3, 4)), ("January 5", date(2024, 1, 5))],
        ),
    ],
)
def test_find_dates_partial_phrases(text: str, expected: list[tuple[str, date]], debug) -> None:
    """Verify phrases around a date yield the whole date or nothing, never a wrong date."""
    # When: finding dates in the phrase
    dates = list(find_dates(text, tz="UTC", now=date(2024, 3, 1)))

    # Then: the matched text and date are exactly as expected
    assert [(found.match, found.datetime.date()) for found in dates] == expected
