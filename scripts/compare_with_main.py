"""Compare find_dates output and scan time between this checkout and a git ref.

Run before landing a change to the date patterns. The script extracts `src/` at the ref
(default `main`), runs the same inputs through both copies under every `first` and
`short_digit_dates` setting, and prints each input whose matches differ. It then times a
scan of a large text with each copy.

Usage:
    uv run python scripts/compare_with_main.py [--ref REF] [--skip-timing]

Exits 1 when any output differs or the scan is more than 10% slower than the ref.
"""

from __future__ import annotations

import argparse
import io
import itertools
import json
import os
import random
import subprocess
import sys
import tarfile
import tempfile
import timeit
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = REPO_ROOT / "tests" / "fixture.txt"
REFERENCE_DAY = date(2026, 11, 23)
FIRST_VALUES = ("month", "day", "year")
FIXTURE_REPEATS = 300
TIMING_ROUNDS = 3
SLOWDOWN_LIMIT = 1.10
MAX_DIFFERENCES_SHOWN = 40

# Values for each slot of a numeric date: day and month edges, invalid parts, two-digit
# years, and four-digit years on both sides of each supported year range
NUMERIC_PARTS = (
    "0",
    "00",
    "1",
    "01",
    "09",
    "12",
    "13",
    "24",
    "29",
    "30",
    "31",
    "32",
    "99",
    "0999",
    "1000",
    "1500",
    "1899",
    "1900",
    "2024",
    "2099",
    "2100",
    "2999",
    "3000",
)
NUMERIC_SEPARATORS = ("/", "-", ".", " ")
MONTH_WORDS = (
    "January",
    "february",
    "MARCH",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
    "jan",
    "Feb.",
    "mar",
    "apr",
    "jun",
    "jul",
    "aug",
    "sep",
    "Sept.",
    "oct",
    "nov",
    "dec",
)
DAY_WORDS = (
    "1",
    "01",
    "1st",
    "2nd",
    "3rd",
    "4th",
    "22nd",
    "29",
    "31st",
    "32",
    "first",
    "twenty-first",
)
YEAR_WORDS = ("99", "1105", "1899", "1999", "2024", "2999", "3000")
MONTH_NAME_TEMPLATES = (
    "{month} {day}, {year}",
    "{day} {month} {year}",
    "{day} of {month} {year}",
    "{day}-{month}-{year}",
    "{year} {month} {day}",
    "{month} {year}",
    "{month} {day}",
    "{day} {month}",
)
RELATIVE_COUNTS = ("1", "3", "a", "one", "twelve")
RELATIVE_UNITS = ("day", "days", "week", "weeks", "month", "months", "year", "years")
WEEKDAY_WORDS = ("monday", "Tue", "wed", "thurs", "fri", "sat", "sun")
PERIOD_MODIFIERS = ("last", "next", "this")
# Text that once produced, or nearly produced, a false match
PROBE_INPUTS = (
    "I sat down on the sun deck",
    "version 1.2.2024",
    "version 2.1.1500",
    "v2.1.1500",
    "2024-03-01T10:00:00Z",
    "dec 31 1899",
    "march 3rd 99",
    "Q1 2024",
    "2024 Q3",
    "the Market in Kumar",
    "today",
    "yesterday's notes",
    "tomorrow",
    "16041905",
    "20240512",
    "someJanuary-elevenththin",
)
DIGIT_RUN_LENGTHS = range(4, 9)
DIGIT_RUNS_PER_LENGTH = 4000
DIGIT_RUN_SEED = 20261123


@dataclass(frozen=True)
class FindDatesSettings:
    """One combination of find_dates options that every input runs under."""

    first: str
    short_digit_dates: bool

    @property
    def label(self) -> str:
        """Name the settings in the report."""
        return f"first={self.first}, short_digit_dates={self.short_digit_dates}"


ALL_SETTINGS = tuple(
    FindDatesSettings(first=first, short_digit_dates=short)
    for first, short in itertools.product(FIRST_VALUES, (False, True))
)


def _numeric_inputs() -> list[str]:
    """Build two- and three-part numeric dates joined by each separator."""
    three_part: list[str] = [
        separator.join(parts)
        for separator in NUMERIC_SEPARATORS
        for parts in itertools.product(NUMERIC_PARTS, repeat=3)
    ]
    two_part: list[str] = [
        separator.join(parts)
        for separator in NUMERIC_SEPARATORS
        for parts in itertools.product(NUMERIC_PARTS, repeat=2)
    ]
    return three_part + two_part


def _digit_run_inputs() -> list[str]:
    """Build seeded random digit runs of every length that can read as a date."""
    generator = random.Random(DIGIT_RUN_SEED)  # noqa: S311
    return [
        "".join(generator.choices("0123456789", k=length))
        for length in DIGIT_RUN_LENGTHS
        for _ in range(DIGIT_RUNS_PER_LENGTH)
    ]


def _month_name_inputs() -> list[str]:
    """Build month-name dates in every supported word order."""
    return sorted(
        {
            template.format(month=month, day=day, year=year)
            for template in MONTH_NAME_TEMPLATES
            for month, day, year in itertools.product(MONTH_WORDS, DAY_WORDS, YEAR_WORDS)
        }
    )


def _relative_inputs() -> list[str]:
    """Build counted offsets, period modifiers, and weekday phrases."""
    counted = [
        phrase
        for count, unit in itertools.product(RELATIVE_COUNTS, RELATIVE_UNITS)
        for phrase in (f"{count} {unit} ago", f"in {count} {unit}")
    ]
    modified = [
        f"{modifier} {word}"
        for modifier in PERIOD_MODIFIERS
        for word in ("week", "month", "year", *WEEKDAY_WORDS)
    ]
    return counted + modified + list(WEEKDAY_WORDS)


def build_inputs() -> list[str]:
    """Build the fixed input set both copies run, so a diff names the exact input.

    Returns:
        list[str]: Every input, without duplicates, in a stable order.
    """
    fixture_lines = [line for line in FIXTURE_PATH.read_text().splitlines() if line.strip()]
    groups = (
        PROBE_INPUTS,
        fixture_lines,
        _numeric_inputs(),
        _digit_run_inputs(),
        _month_name_inputs(),
        _relative_inputs(),
    )
    return list(dict.fromkeys(itertools.chain.from_iterable(groups)))


def _import_datefind(expected_source: Path) -> ModuleType:
    """Import datefind and confirm it is the copy under `expected_source`.

    Args:
        expected_source: The `src` directory the caller put on PYTHONPATH.

    Returns:
        ModuleType: The datefind module.

    Raises:
        RuntimeError: If Python imported datefind from somewhere else.
    """
    import datefind  # noqa: PLC0415

    imported_from = Path(datefind.__file__).resolve()
    if not imported_from.is_relative_to(expected_source.resolve()):
        msg = f"Imported datefind from {imported_from}, expected a file under {expected_source}"
        raise RuntimeError(msg)
    return datefind


def record_outputs(source: Path, output_path: Path) -> None:
    """Write every input's matches under every setting to `output_path` as JSON.

    Args:
        source: The `src` directory that holds the datefind copy to run.
        output_path: Where to write the results.
    """
    datefind = _import_datefind(expected_source=source)
    inputs = build_inputs()
    results = {
        settings.label: [
            [
                f"{found.match!r} {found.span[0]}-{found.span[1]} {found.datetime.date()}"
                for found in datefind.find_dates(
                    text,
                    first=settings.first,
                    tz="UTC",
                    now=REFERENCE_DAY,
                    short_digit_dates=settings.short_digit_dates,
                )
            ]
            for text in inputs
        ]
        for settings in ALL_SETTINGS
    }
    output_path.write_text(json.dumps({"inputs": inputs, "results": results}))


def record_scan_time(source: Path) -> None:
    """Print the fastest of several scans of the repeated fixture, in seconds.

    Args:
        source: The `src` directory that holds the datefind copy to time.
    """
    datefind = _import_datefind(expected_source=source)
    text = FIXTURE_PATH.read_text() * FIXTURE_REPEATS
    timer = timeit.Timer(
        lambda: sum(1 for _ in datefind.find_dates(text, tz="UTC", now=REFERENCE_DAY))
    )
    print(min(timer.repeat(repeat=3, number=1)))


def _extract_ref_source(ref: str, destination: Path) -> Path:
    """Extract `src/` at `ref` into `destination`.

    Args:
        ref: The git ref to extract.
        destination: An empty directory to extract into.

    Returns:
        Path: The extracted `src` directory.
    """
    archive = subprocess.run(
        ["git", "archive", "--format=tar", ref, "src"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(path=destination, filter="data")
    return destination / "src"


def _run_worker(source: Path, arguments: list[str]) -> str:
    """Run this script in a fresh interpreter that imports datefind from `source`.

    Args:
        source: The `src` directory to put first on PYTHONPATH.
        arguments: The worker command and its arguments.

    Returns:
        str: The worker's standard output.
    """
    environment = {**os.environ, "PYTHONPATH": str(source)}
    completed = subprocess.run(
        [sys.executable, __file__, *arguments, "--source", str(source)],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        msg = f"Worker {arguments} for {source} exited {completed.returncode}, expected 0:\n{completed.stderr}"
        raise RuntimeError(msg)
    return completed.stdout


def compare_outputs(ref_source: Path, branch_source: Path, workdir: Path, ref: str) -> bool:
    """Print every input whose matches differ between the ref and this checkout.

    Args:
        ref_source: The ref's `src` directory.
        branch_source: This checkout's `src` directory.
        workdir: A scratch directory for the workers' JSON files.
        ref: The ref name, for the report.

    Returns:
        bool: True when every output matches.
    """
    ref_path = workdir / "ref.json"
    branch_path = workdir / "branch.json"
    _run_worker(source=ref_source, arguments=["record-outputs", "--output", str(ref_path)])
    _run_worker(source=branch_source, arguments=["record-outputs", "--output", str(branch_path)])
    ref_data = json.loads(ref_path.read_text())
    branch_data = json.loads(branch_path.read_text())
    if ref_data["inputs"] != branch_data["inputs"]:
        msg = "The two runs built different input sets, expected identical inputs"
        raise RuntimeError(msg)

    inputs: list[str] = ref_data["inputs"]
    difference_count = 0
    for label, ref_results in ref_data["results"].items():
        branch_results = branch_data["results"][label]
        for text, ref_found, branch_found in zip(inputs, ref_results, branch_results, strict=True):
            if ref_found == branch_found:
                continue
            difference_count += 1
            if difference_count <= MAX_DIFFERENCES_SHOWN:
                print(f"[{label}] {text!r}")
                print(f"    {ref}: {ref_found}")
                print(f"    branch: {branch_found}")

    total = len(inputs) * len(ALL_SETTINGS)
    if difference_count > MAX_DIFFERENCES_SHOWN:
        print(f"... {difference_count - MAX_DIFFERENCES_SHOWN} more differences not shown")
    print(f"Output: {difference_count} of {total} runs differ from {ref}")
    return difference_count == 0


def compare_scan_time(ref_source: Path, branch_source: Path, ref: str) -> bool:
    """Time a large scan with each copy, alternating runs so drift hits both equally.

    Args:
        ref_source: The ref's `src` directory.
        branch_source: This checkout's `src` directory.
        ref: The ref name, for the report.

    Returns:
        bool: True when the branch is no more than 10% slower than the ref.
    """
    ref_times: list[float] = []
    branch_times: list[float] = []
    for _ in range(TIMING_ROUNDS):
        ref_times.append(float(_run_worker(source=ref_source, arguments=["record-scan-time"])))
        branch_times.append(
            float(_run_worker(source=branch_source, arguments=["record-scan-time"]))
        )
    ref_best = min(ref_times)
    branch_best = min(branch_times)
    ratio = branch_best / ref_best
    print(f"Scan time: {ref} {ref_best:.3f}s, branch {branch_best:.3f}s ({ratio:.2f}x)")
    return ratio <= SLOWDOWN_LIMIT


def _parse_arguments() -> argparse.Namespace:
    """Read the command line.

    Returns:
        argparse.Namespace: The parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ref", default="main", help="git ref to compare against")
    parser.add_argument("--skip-timing", action="store_true", help="compare output only")
    workers = parser.add_subparsers(dest="worker", help=argparse.SUPPRESS)
    outputs_worker = workers.add_parser("record-outputs")
    outputs_worker.add_argument("--source", type=Path, required=True)
    outputs_worker.add_argument("--output", type=Path, required=True)
    timing_worker = workers.add_parser("record-scan-time")
    timing_worker.add_argument("--source", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    """Run the comparison, or one worker step when called by the comparison.

    Returns:
        int: The process exit code.
    """
    arguments = _parse_arguments()
    if arguments.worker == "record-outputs":
        record_outputs(source=arguments.source, output_path=arguments.output)
        return 0
    if arguments.worker == "record-scan-time":
        record_scan_time(source=arguments.source)
        return 0

    with tempfile.TemporaryDirectory() as workdir_name:
        workdir = Path(workdir_name)
        ref_source = _extract_ref_source(ref=arguments.ref, destination=workdir / "ref")
        branch_source = REPO_ROOT / "src"
        outputs_match = compare_outputs(
            ref_source=ref_source, branch_source=branch_source, workdir=workdir, ref=arguments.ref
        )
        speed_ok = arguments.skip_timing or compare_scan_time(
            ref_source=ref_source, branch_source=branch_source, ref=arguments.ref
        )
    return 0 if outputs_match and speed_ok else 1


if __name__ == "__main__":
    sys.exit(main())
