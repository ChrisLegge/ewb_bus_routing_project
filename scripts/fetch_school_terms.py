"""
fetch_school_terms.py
=====================
Generates a Birmingham school term calendar for 2023-2026 and creates a
date lookup: for any date, is it a school term day (weekday, in term)?

Sources
-------
  2023/24 & 2024/25: Birmingham City Council published term dates
  2025/26:           Birmingham City Council (scraped)
  Bank holidays:     England & Wales, from GOV.UK public API

Output
------
  data/school_terms/birmingham_term_calendar.json
    {
      "YYYY-MM-DD": {
        "is_school_term": true/false,
        "is_weekend": true/false,
        "is_bank_holiday": false,
        "period": "autumn_2024" | "half_term" | "summer_holiday" | ...
      },
      ...
    }

  data/school_terms/term_periods.json
    List of named term/holiday periods with start/end dates

Usage
-----
  python scripts/fetch_school_terms.py
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import requests

_REPO   = Path(__file__).parent.parent
OUT_DIR = _REPO / "data" / "school_terms"
OUT_CAL = OUT_DIR / "birmingham_term_calendar.json"
OUT_PER = OUT_DIR / "term_periods.json"

HEADERS = {"User-Agent": "ewb-bus-routing/1.0 (EWB design challenge; educational use)"}

# ---------------------------------------------------------------------------
# Birmingham term dates (hand-encoded from BCC published calendars)
# Sources:
#   2023/24: https://www.birmingham.gov.uk (archived)
#   2024/25: https://www.birmingham.gov.uk
#   2025/26: https://www.birmingham.gov.uk/info/20014/schools_and_learning/685/school_term_dates
# ---------------------------------------------------------------------------
TERM_PERIODS = [
    # 2023/24
    {"name": "autumn_2023",      "type": "term",    "start": "2023-09-04", "end": "2023-10-20"},
    {"name": "half_term_oct_23", "type": "holiday", "start": "2023-10-23", "end": "2023-10-27"},
    {"name": "autumn_2023b",     "type": "term",    "start": "2023-10-30", "end": "2023-12-20"},
    {"name": "xmas_2023",        "type": "holiday", "start": "2023-12-21", "end": "2024-01-05"},
    {"name": "spring_2024a",     "type": "term",    "start": "2024-01-08", "end": "2024-02-09"},
    {"name": "half_term_feb_24", "type": "holiday", "start": "2024-02-12", "end": "2024-02-16"},
    {"name": "spring_2024b",     "type": "term",    "start": "2024-02-19", "end": "2024-03-28"},
    {"name": "easter_2024",      "type": "holiday", "start": "2024-03-29", "end": "2024-04-12"},
    {"name": "summer_2024a",     "type": "term",    "start": "2024-04-15", "end": "2024-05-24"},
    {"name": "half_term_may_24", "type": "holiday", "start": "2024-05-27", "end": "2024-05-31"},
    {"name": "summer_2024b",     "type": "term",    "start": "2024-06-03", "end": "2024-07-19"},
    {"name": "summer_hols_2024", "type": "holiday", "start": "2024-07-22", "end": "2024-09-01"},
    # 2024/25
    {"name": "autumn_2024",      "type": "term",    "start": "2024-09-02", "end": "2024-10-25"},
    {"name": "half_term_oct_24", "type": "holiday", "start": "2024-10-28", "end": "2024-11-01"},
    {"name": "autumn_2024b",     "type": "term",    "start": "2024-11-04", "end": "2024-12-20"},
    {"name": "xmas_2024",        "type": "holiday", "start": "2024-12-21", "end": "2025-01-05"},
    {"name": "spring_2025a",     "type": "term",    "start": "2025-01-06", "end": "2025-02-14"},
    {"name": "half_term_feb_25", "type": "holiday", "start": "2025-02-17", "end": "2025-02-21"},
    {"name": "spring_2025b",     "type": "term",    "start": "2025-02-24", "end": "2025-04-11"},
    {"name": "easter_2025",      "type": "holiday", "start": "2025-04-12", "end": "2025-04-25"},
    {"name": "summer_2025a",     "type": "term",    "start": "2025-04-28", "end": "2025-05-23"},
    {"name": "half_term_may_25", "type": "holiday", "start": "2025-05-26", "end": "2025-05-30"},
    {"name": "summer_2025b",     "type": "term",    "start": "2025-06-02", "end": "2025-07-24"},
    {"name": "summer_hols_2025", "type": "holiday", "start": "2025-07-25", "end": "2025-08-31"},
    # 2025/26 (from BCC website)
    {"name": "autumn_2025",      "type": "term",    "start": "2025-09-01", "end": "2025-10-24"},
    {"name": "half_term_oct_25", "type": "holiday", "start": "2025-10-27", "end": "2025-10-31"},
    {"name": "autumn_2025b",     "type": "term",    "start": "2025-11-03", "end": "2025-12-19"},
    {"name": "xmas_2025",        "type": "holiday", "start": "2025-12-20", "end": "2026-01-04"},
    {"name": "spring_2026a",     "type": "term",    "start": "2026-01-05", "end": "2026-02-13"},
    {"name": "half_term_feb_26", "type": "holiday", "start": "2026-02-16", "end": "2026-02-20"},
    {"name": "spring_2026b",     "type": "term",    "start": "2026-02-23", "end": "2026-03-27"},
    {"name": "easter_2026",      "type": "holiday", "start": "2026-03-28", "end": "2026-04-12"},
    {"name": "summer_2026a",     "type": "term",    "start": "2026-04-13", "end": "2026-05-22"},
    {"name": "half_term_may_26", "type": "holiday", "start": "2026-05-25", "end": "2026-05-29"},
    {"name": "summer_2026b",     "type": "term",    "start": "2026-06-01", "end": "2026-07-20"},
]


def fetch_bank_holidays() -> set[str]:
    """Fetch England & Wales bank holidays from GOV.UK API."""
    print("Fetching England & Wales bank holidays from GOV.UK...")
    try:
        r = requests.get(
            "https://www.gov.uk/bank-holidays.json",
            headers=HEADERS, timeout=30,
        )
        r.raise_for_status()
        events = r.json()["england-and-wales"]["events"]
        holidays = {e["date"] for e in events}
        print(f"  Got {len(holidays)} bank holidays")
        return holidays
    except Exception as e:
        print(f"  Warning: {e} — using empty set")
        return set()


def build_calendar(bank_holidays: set[str]) -> dict[str, dict]:
    # Build period lookup: date -> period name + type
    date_to_period: dict[date, tuple[str, str]] = {}
    for period in TERM_PERIODS:
        start = date.fromisoformat(period["start"])
        end   = date.fromisoformat(period["end"])
        d = start
        while d <= end:
            date_to_period[d] = (period["name"], period["type"])
            d += timedelta(days=1)

    # Generate calendar 2023-01-01 to 2026-12-31
    calendar: dict[str, dict] = {}
    d = date(2023, 1, 1)
    end = date(2026, 12, 31)

    while d <= end:
        ds         = d.isoformat()
        is_weekend = d.weekday() >= 5
        is_bh      = ds in bank_holidays
        period_info = date_to_period.get(d)

        if period_info:
            period_name, period_type = period_info
            is_term = (period_type == "term") and not is_weekend and not is_bh
        else:
            period_name = "school_holiday" if not is_weekend else "weekend"
            is_term = False

        calendar[ds] = {
            "is_school_term":   is_term,
            "is_weekend":       is_weekend,
            "is_bank_holiday":  is_bh,
            "period":           period_name,
        }
        d += timedelta(days=1)

    return calendar


def run() -> dict:
    bank_holidays = fetch_bank_holidays()
    calendar = build_calendar(bank_holidays)

    # Stats
    term_days    = sum(1 for v in calendar.values() if v["is_school_term"])
    holiday_days = sum(1 for v in calendar.values() if not v["is_school_term"] and not v["is_weekend"])
    weekend_days = sum(1 for v in calendar.values() if v["is_weekend"])
    bh_days      = sum(1 for v in calendar.values() if v["is_bank_holiday"])

    print(f"\nCalendar 2023-2026 ({len(calendar)} days):")
    print(f"  School term weekdays : {term_days}")
    print(f"  School holiday wkdays: {holiday_days}")
    print(f"  Weekends             : {weekend_days}")
    print(f"  Bank holidays        : {bh_days}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_CAL.write_text(json.dumps(calendar, indent=2), encoding="utf-8")
    OUT_PER.write_text(json.dumps(TERM_PERIODS, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_CAL}")
    print(f"Wrote {OUT_PER}")
    return calendar


if __name__ == "__main__":
    run()
