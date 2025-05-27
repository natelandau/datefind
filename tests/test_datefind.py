"""Tests for datefind."""

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

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
    ("text", "first", "expected"),
    [
        pytest.param(
            "march twenty second 2025 and sep. thirteenth 1999 and also DEC second 2024",
            "month",
            [
                datetime(2025, 3, 22, tzinfo=ZoneInfo("UTC")),
                datetime(1999, 9, 13, tzinfo=ZoneInfo("UTC")),
                datetime(2024, 12, 2, tzinfo=ZoneInfo("UTC")),
            ],
            id="MONTH-NUMBER-YYYY",
        ),
        pytest.param(
            "05 12 24 and 9819 is another day",
            "month",
            [
                datetime(2024, 5, 12, tzinfo=ZoneInfo("UTC")),
                datetime(2019, 9, 8, tzinfo=ZoneInfo("UTC")),
            ],
            id="MM-DD-YY (xx_xx_xx) month",
        ),
        pytest.param(
            "Hello, world! 2024-01-12 and 2024-1-9.",
            "MONTH",
            [
                datetime(2024, 1, 12, tzinfo=ZoneInfo("UTC")),
                datetime(2024, 1, 9, tzinfo=ZoneInfo("UTC")),
            ],
            id="YYYY-MM-DD (yyyy_xx_xx) month",
        ),
        pytest.param(
            "Hello, world! 2024-1-12 and 2024-12-9.",
            "day",
            [
                datetime(2024, 12, 1, tzinfo=ZoneInfo("UTC")),
                datetime(2024, 9, 12, tzinfo=ZoneInfo("UTC")),
            ],
            id="YYYY-DD-MM (yyyy_xx_xx) day",
        ),
        pytest.param(
            "Hello, world! 2024-01-12 and 2024-1-9.",
            "year",
            [
                datetime(2024, 1, 12, tzinfo=ZoneInfo("UTC")),
                datetime(2024, 1, 9, tzinfo=ZoneInfo("UTC")),
            ],
            id="YYYY-MM-DD (yyyy_xx_xx) year",
        ),
        pytest.param(
            "Someday it will be January 23rd, 2025 but its March 1st, 1999.",
            "month",
            [
                datetime(2025, 1, 23, tzinfo=ZoneInfo("UTC")),
                datetime(1999, 3, 1, tzinfo=ZoneInfo("UTC")),
            ],
            id="MONTH-DD-YYYY",
        ),
        pytest.param(
            "february 1st 2024 and aug-2-2024",
            "month",
            [
                datetime(2024, 2, 1, tzinfo=ZoneInfo("UTC")),
                datetime(2024, 8, 2, tzinfo=ZoneInfo("UTC")),
            ],
            id="MONTH-DD-YYYY",
        ),
        pytest.param(
            "foo 10-January-2024 bar and 1-april-2024",
            "month",
            [
                datetime(2024, 1, 10, tzinfo=ZoneInfo("UTC")),
                datetime(2024, 4, 1, tzinfo=ZoneInfo("UTC")),
            ],
            id="DD-MONTH-YYYY",
        ),
        pytest.param(
            "foo mar 11 feb bar or January-eleventh",
            "month",
            [
                datetime(datetime.now(ZoneInfo("UTC")).year, 3, 11, tzinfo=ZoneInfo("UTC")),
                datetime(datetime.now(ZoneInfo("UTC")).year, 1, 11, tzinfo=ZoneInfo("UTC")),
            ],
            id="MONTH-DD",
        ),
        pytest.param(
            "it's 1999 December 1st and 2024 jan 10th",
            "month",
            [
                datetime(1999, 12, 1, tzinfo=ZoneInfo("UTC")),
                datetime(2024, 1, 10, tzinfo=ZoneInfo("UTC")),
            ],
            id="YYYY_MONTH_DD",
        ),
        pytest.param(
            "foo 1999 dec bar",
            "month",
            [datetime(1999, 12, 1, tzinfo=ZoneInfo("UTC"))],
            id="YYYY-MONTH",
        ),
        pytest.param(
            "foo dec 1999 bar and january 2024 something",
            "month",
            [
                datetime(1999, 12, 1, tzinfo=ZoneInfo("UTC")),
                datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
            ],
            id="MONTH-YYYY",
        ),
        pytest.param(
            "today and yesterday and tomorrow and last week and next week",
            "month",
            [
                datetime.now(ZoneInfo("UTC")),
                datetime.now(ZoneInfo("UTC")) - timedelta(days=1),
                datetime.now(ZoneInfo("UTC")) + timedelta(days=1),
                datetime.now(ZoneInfo("UTC")) - timedelta(days=7),
                datetime.now(ZoneInfo("UTC")) + timedelta(days=7),
            ],
            id="Natural date",
        ),
    ],
)
def test_find_dates(text: str, first: str, expected: list[datetime], debug) -> None:
    """Verify extracting dates from text returns expected datetime objects."""
    # Given: Text containing dates and expected datetime

    # When: Finding dates in the text
    dates = list(find_dates(text, first=first, tz="UTC"))

    # Then: Each found date matches expected datetime
    assert len(dates) == len(expected)
    for i, date in enumerate(dates):
        assert date.date.strftime("%Y-%m-%d") == expected[i].strftime("%Y-%m-%d")


def test_date_object(debug):
    """Verify Date object has expected properties."""
    text = "Hello, world! 2024-01-12 and jan. eighteenth, 2024"
    dates = list(find_dates(text, first="month", tz="UTC"))
    assert len(dates) == 2
    assert dates[0].date == datetime(2024, 1, 12, tzinfo=ZoneInfo("UTC"))
    assert dates[0].text == text
    assert dates[0].match == "2024-01-12"
    assert dates[0].span == (14, 24)

    assert dates[1].date == datetime(2024, 1, 18, tzinfo=ZoneInfo("UTC"))
    assert dates[1].text == text
    assert dates[1].match == "jan. eighteenth, 2024"
    assert dates[1].span == (29, 50)
