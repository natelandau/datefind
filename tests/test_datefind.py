"""Tests for datefind."""

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from datefind import find_dates

fixture_file = Path(__file__).parent / "fixture.txt"


def test_raise_error_on_invalid_timezone():
    """Verify ValueError raised when invalid timezone provided."""
    # Given: An invalid timezone string
    invalid_tz = "America/California"

    # When/Then: find_dates raises ValueError
    with pytest.raises(ValueError, match="Invalid timezone: America/California"):
        find_dates("Hello, world! Today is 2024-01-01.", tz=invalid_tz)


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
        ("01122024", [datetime(2024, 1, 12)]),
        ("01:12:2024", [datetime(2024, 1, 12)]),
        ("2024-01-12", [datetime(2024, 1, 12)]),
        ("2024/01/12", [datetime(2024, 1, 12)]),
        ("20240112", [datetime(2024, 1, 12)]),
        ("2024-1-12", [datetime(2024, 1, 12)]),
        ("2024/1/12", [datetime(2024, 1, 12)]),
        ("2024112", [datetime(2024, 11, 2)]),
        ("12112022", [datetime(2022, 12, 11)]),
        ("2111999", [datetime(1999, 2, 11)]),
        ("2022-12", [datetime(2022, 12, 1)]),
        ("12 2022", [datetime(2022, 12, 1)]),
        ("sep. 4", [datetime(2024, 9, 4)]),
        ("sept. fifth", [datetime(2024, 9, 5)]),
        ("2022, 12, 24", [datetime(2022, 12, 24)]),
        ("23 march, 2020", [datetime(2020, 3, 23)]),
        ("23rd, march-2020", [datetime(2020, 3, 23)]),
        ("23rd of march 2020", [datetime(2020, 3, 23)]),
        ("fifteenth march, 2025", [datetime(2025, 3, 15)]),
        ("twenty fifth of march, 2025", [datetime(2025, 3, 25)]),
        ("twentyfifth of march, 2025", [datetime(2025, 3, 25)]),
        ("march 23", [datetime(2024, 3, 23)]),
        ("march 23 2025", [datetime(2025, 3, 23)]),
        ("march 21st 2025", [datetime(2025, 3, 21)]),
        ("march the 23rd 2025", [datetime(2025, 3, 23)]),
        ("march the 23rd of 2025", [datetime(2025, 3, 23)]),
        ("march 23rd", [datetime(2024, 3, 23)]),
        ("march the 22nd", [datetime(2024, 3, 22)]),
        ("march twenty second", [datetime(2024, 3, 22)]),
        ("march the twentysecond", [datetime(2024, 3, 22)]),
        ("march the first of 2025", [datetime(2025, 3, 1)]),
        ("march 2025", [datetime(2025, 3, 1)]),
        ("january, of 1998", [datetime(1998, 1, 1)]),
        ("second january, of 1998", [datetime(1998, 1, 2)]),
        ("today", [datetime(2024, 3, 1)]),
        ("yesterday", [datetime(2024, 3, 1) - timedelta(days=1)]),
        ("tomorrow", [datetime(2024, 3, 1) + timedelta(days=1)]),
        ("last week", [datetime(2024, 3, 1) - timedelta(days=7)]),
        ("next week", [datetime(2024, 3, 1) + timedelta(days=7)]),
        (
            "last month",
            [datetime(2024, 3, 1).replace(month=2)],
        ),
        (
            "next month",
            [datetime(2024, 3, 1).replace(month=4)],
        ),
        (
            "last year",
            [datetime(2024, 3, 1).replace(year=2023)],
        ),
        (
            "next year",
            [datetime(2024, 3, 1).replace(year=2025)],
        ),
    ],
)
@freeze_time("2024-03-01")
def test_find_dates(text, expected, debug):
    """Verify extracting dates from short text returns expected datetime objects."""
    # Given: Text containing dates and expected datetime

    # When: Finding dates in the text
    dates = list(find_dates(text, first="month", tz="UTC"))

    # Then: Each found date matches expected datetime
    assert len(dates) == len(expected)
    for i, date in enumerate(dates):
        assert date.datetime.strftime("%Y-%m-%d") == expected[i].strftime("%Y-%m-%d")
        assert date.match == text
        assert date.span == (0, len(text))


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
        datetime(2019, 9, 8, tzinfo=ZoneInfo("UTC")),
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
    ]

    # When: Finding dates in the text
    dates = list(find_dates(text, first="month", tz="UTC"))

    # Then: Each found date matches expected datetime
    assert len(dates) == len(expected)
    for i, date in enumerate(dates):
        assert date.datetime.strftime("%Y-%m-%d") == expected[i].strftime("%Y-%m-%d")


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
    ],
)
def test_first_number(text: str, first: str, expected: list[datetime], debug) -> None:
    """Verify extracting dates from text returns expected datetime objects."""
    # Given: Text containing dates and expected datetime
    # When: Finding dates in the text
    dates = list(find_dates(text, first=first, tz="UTC"))

    # Then: Each found date matches expected datetime
    assert len(dates) == len(expected)
    for i, date in enumerate(dates):
        assert date.datetime.strftime("%Y-%m-%d") == expected[i].strftime("%Y-%m-%d")


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
