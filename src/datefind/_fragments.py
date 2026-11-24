"""Raw regex fragments and lookup tables for datefind patterns."""

from enum import Enum


class FirstNumber(Enum):
    """Enum for the first number to find in ambiguous dates."""

    MONTH = "month"
    DAY = "day"
    YEAR = "year"


SEP_CHARS = r"-\/:,._\+@ "  # Define separator chars for reuse
SEP_CLASS = rf"[{SEP_CHARS}]"
# The separators other than "-", which between a day and a number marks a range ("Jan 5-10")
SEP_CLASS_WITHOUT_HYPHEN = rf"[{SEP_CHARS.removeprefix('-')}]"
# The separators other than ",", which before a number often starts a count ("week 3, 1500 users")
SEP_CLASS_WITHOUT_COMMA = rf"[{SEP_CHARS.replace(',', '')}]"
# Separators that do not mark a numeric year ("12 25 2024"). "-", "/", and "." do, and
# mixed with a weak separator they belong to other numbers ("3.8, 10", "pages 3-8, 10").
WEAK_SEP_CLASS = "[" + "".join(char for char in SEP_CHARS if char not in "-/.") + "]"
# Unicode forms of ASCII characters the patterns match, each mapped to one character so
# that positions in the converted text are positions in the original. Covers text copied
# from web pages and word processors: non-breaking and other spaces, dashes, curly
# apostrophes, and full-width digits and separators. Also the long s and dotted capital I,
# which case-insensitive matching treats as "s" and "i" but str.lower() does not.
ASCII_EQUIVALENTS: dict[int, str] = {
    0x017F: "s",
    0x0130: "i",
    **dict.fromkeys((0x00A0, *range(0x2000, 0x200B), 0x202F, 0x205F, 0x3000), " "),
    **dict.fromkeys((*range(0x2010, 0x2016), 0x2212, 0xFE58, 0xFE63, 0xFF0D), "-"),
    **dict.fromkeys((0x2018, 0x2019, 0x02BC, 0x2032), "'"),
    **{0xFF10 + digit: str(digit) for digit in range(10)},
    0xFF0F: "/",
    0xFF0E: ".",
    0xFF0C: ",",
    0xFF1A: ":",
}
SEP_CHARS_REGEX = rf"{SEP_CLASS}*?"
DD_FLEXIBLE = r"[12][0-9]|3[01]|0?[1-9]"
DD = r"0[1-9]|[12][0-9]|3[01]"
MM = r"0[1-9]|1[012]"
MM_FLEXIBLE = r"1[012]|0?[1-9]"
# Years where a month name or a / - . separator marks the year
YYYY = r"1\d\d\d|2\d\d\d"
# Years where only position or a weak separator, such as a space, marks the year
YYYY_NARROW = r"19\d\d|20\d\d"
YYYY_FLEXIBLE = rf"{YYYY}|\d\d"
YYYY_NARROW_FLEXIBLE = rf"{YYYY_NARROW}|\d\d"


# Full month names can touch other letters ("someJanuary"). Abbreviations must stand
# alone, so "mar" in "Market" or "Kumar" is not March. One lookaround pair around all
# abbreviations keeps the scan fast.
MONTH_FULL_NAMES = (
    r"january|february|march|april|june|july|august|september|october|november|december"
)
MONTH_ABBREVIATIONS = r"jan|feb|mar|apr|may|jun|jul|aug|sept?|oct|nov|dec"
MONTH = rf"{MONTH_FULL_NAMES}|(?<!\p{{L}})(?:{MONTH_ABBREVIATIONS})(?!\p{{L}})"
# In day order, which is also the pattern's alternation order. A space marks where
# compound ordinals accept a separator ("twenty first", "twenty-first", "twentyfirst").
ORDINAL_DAY_WORDS_IN_ORDER = (
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
    "sixth",
    "seventh",
    "eighth",
    "ninth",
    "tenth",
    "eleventh",
    "twelfth",
    "thirteenth",
    "fourteenth",
    "fifteenth",
    "sixteenth",
    "seventeenth",
    "eighteenth",
    "nineteenth",
    "twentieth",
    "twenty first",
    "twenty second",
    "twenty third",
    "twenty fourth",
    "twenty fifth",
    "twenty sixth",
    "twenty seventh",
    "twenty eighth",
    "twenty ninth",
    "thirtieth",
    "thirty first",
)
# Keyed by the word with separators removed
ORDINAL_DAY_NUMBERS: dict[str, int] = {
    word.replace(" ", ""): day
    for day, word in enumerate(iterable=ORDINAL_DAY_WORDS_IN_ORDER, start=1)
}
ORDINAL_DAY_WORDS = "|".join(
    word.replace(" ", SEP_CHARS_REGEX) for word in ORDINAL_DAY_WORDS_IN_ORDER
)
DIGIT_SUFFIXES = r"st|th|rd|nd"
TODAY = r"today'?s?"
YESTERDAY = r"yesterday'?s?"
TOMORROW = r"tomorrow'?s?"
DAY_AFTER_TOMORROW = rf"day{SEP_CLASS}+after{SEP_CLASS}+{TOMORROW}"
DAY_BEFORE_YESTERDAY = rf"day{SEP_CLASS}+before{SEP_CLASS}+{YESTERDAY}"
# An hour with minutes or with am/pm, such as "14:30", "9:15", "3pm", or "10 p.m.". ISO 8601
# also writes the end of a day as "24:00".
TIME_OF_DAY = r"(?:(?:[01]?\d|2[0-3])(?::[0-5]\d|\s?[ap]\.?m\.?(?!\p{L}))|24:00)"
# Offset, in units, of "<modifier> week", "<modifier> month", "<modifier> year"
PERIOD_MODIFIER_OFFSETS: dict[str, int] = {"last": -1, "next": 1, "this": 0}
UNAMBIGUOUS_WEEKDAYS = (
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tues?|thu|thurs?|fri"
)
# Also common English words, so they count as weekdays only after last, this, or next
WEEKDAY_ABBREVIATIONS_THAT_ARE_WORDS = r"wed|sat|sun"
WEEKDAYS = rf"{UNAMBIGUOUS_WEEKDAYS}|{WEEKDAY_ABBREVIATIONS_THAT_ARE_WORDS}"
