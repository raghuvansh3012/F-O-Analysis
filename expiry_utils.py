"""
Expiry Utilities — Data-Driven Weekly Expiry Detection
=======================================================
Scans NIFTY option chain data to dynamically identify weekly expiry dates.
No hardcoded expiry day (Tuesday/Thursday etc.) — everything comes from actual data.

Key concepts:
- "Weekly expiry": A regularly occurring expiry (~every 7 days). 
  Could be any weekday depending on NSE rules & holidays.
- "Monthly expiry cycle" for month M:
    - Contains all weekly expiries that fall in calendar month M
    - STARTS from: day after previous month's last weekly expiry
    - ENDS at: month M's last weekly expiry
  Example: Sep 2026 cycle = Aug 26 (day after Aug 25 expiry) to Sep 22 (Sep's last weekly)
"""

import os
import glob
import datetime
import calendar
from collections import defaultdict

try:
    import pandas as pd
except ImportError:
    pd = None

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
OPTION_CHAIN_DIR = os.path.join(DATA_DIR, "option_chain_data")


# ============================================================
# 1. EXTRACT EXPIRY DATES FROM DATA
# ============================================================

def get_all_expiry_dates_from_data():
    """
    Scans all option_chain_data/*.csv files and extracts unique EXPIRY_DT values.
    Returns a sorted list of datetime.date objects.
    """
    if pd is None:
        return []

    all_expiries = set()
    csv_files = glob.glob(os.path.join(OPTION_CHAIN_DIR, "*_nifty_options.csv"))

    for f in csv_files:
        try:
            df = pd.read_csv(f, usecols=['EXPIRY_DT'])
            for exp in df['EXPIRY_DT'].unique():
                try:
                    dt = pd.to_datetime(exp, format='mixed', dayfirst=True).date()
                    all_expiries.add(dt)
                except Exception:
                    pass
        except Exception:
            pass

    return sorted(all_expiries)


# ============================================================
# 2. FILTER WEEKLY vs QUARTERLY/YEARLY EXPIRIES
# ============================================================

def filter_weekly_expiries(all_expiries):
    """
    Separates weekly expiries from quarterly/yearly ones.
    
    Logic: Weekly expiries have at least one neighbor within 14 days.
    Quarterly expiries (e.g., Sep 29, Dec 29) are isolated — their nearest 
    neighbor is 30+ days away.
    
    Why 14 days? Normal weekly gap = 7 days. But sometimes a week is skipped
    due to holidays, making the gap ~14 days (e.g., Aug 11 → Aug 25 = 14 days).
    """
    if len(all_expiries) < 2:
        return list(all_expiries)

    weekly = []
    for i, exp in enumerate(all_expiries):
        distances = []
        if i > 0:
            distances.append((exp - all_expiries[i - 1]).days)
        if i < len(all_expiries) - 1:
            distances.append((all_expiries[i + 1] - exp).days)

        min_distance = min(distances) if distances else float('inf')

        # Weekly expiries have at least one neighbor within 14 days
        if min_distance <= 14:
            weekly.append(exp)

    return weekly


# ============================================================
# 3. GROUP INTO MONTHLY EXPIRY CYCLES
# ============================================================

def get_monthly_expiry_boundaries(weekly_expiries):
    """
    Groups weekly expiries by calendar month and finds the LAST weekly expiry
    for each month. This last expiry = monthly expiry boundary.
    
    Returns sorted list of (year, month, last_expiry_date) tuples.
    Example: [(2026, 7, date(2026,7,28)), (2026, 8, date(2026,8,25))]
    """
    month_groups = defaultdict(list)
    for exp in weekly_expiries:
        month_groups[(exp.year, exp.month)].append(exp)

    boundaries = []
    for (year, month), dates in month_groups.items():
        boundaries.append((year, month, max(dates)))

    boundaries.sort(key=lambda x: x[2])
    return boundaries


# ============================================================
# 4. GET CURRENT EXPIRY CYCLE
# ============================================================

def get_current_expiry_cycle(today=None):
    """
    Returns (cycle_start, cycle_end, label) for the current monthly expiry series.
    
    Algorithm:
    1. Extract all expiry dates from option chain data
    2. Filter to weekly expiries only
    3. Group by month → find last weekly expiry per month
    4. Find which cycle 'today' falls in:
       - If today <= month's last expiry → we're in that month's cycle
       - cycle_start = day after PREVIOUS month's last expiry
       - cycle_end = THIS month's last expiry
    5. If today > all known expiries → we're in the NEXT cycle
       - cycle_start = day after last known month's last expiry
       - cycle_end = estimated (end of next calendar month)
    
    Returns:
        tuple: (cycle_start: date, cycle_end: date, label: str)
    """
    if today is None:
        today = datetime.date.today()

    all_expiries = get_all_expiry_dates_from_data()
    weekly = filter_weekly_expiries(all_expiries)

    if not weekly:
        # Fallback: no option chain data at all — use calendar month
        return _fallback_calendar_month(today)

    boundaries = get_monthly_expiry_boundaries(weekly)

    if not boundaries:
        return _fallback_calendar_month(today)

    # Find which cycle today falls in
    for i, (year, month, last_expiry) in enumerate(boundaries):
        if today <= last_expiry:
            # Today is within this month's cycle
            if i > 0:
                prev_last_expiry = boundaries[i - 1][2]
                cycle_start = prev_last_expiry + datetime.timedelta(days=1)
            else:
                # First known cycle — start from the first weekly expiry's week start
                first_expiry_of_month = min(
                    d for d in weekly if d.year == year and d.month == month
                )
                # Go back to find start (day after previous week's expiry or start of data)
                # Simple: start from 7 days before the first expiry of this month
                cycle_start = first_expiry_of_month - datetime.timedelta(days=6)

            cycle_end = last_expiry
            label = _make_cycle_label(cycle_start, cycle_end, year, month)
            return (cycle_start, cycle_end, label)

    # Today is AFTER all known monthly boundaries → we're in the next cycle
    last_boundary = boundaries[-1]
    last_year, last_month, last_expiry = last_boundary
    cycle_start = last_expiry + datetime.timedelta(days=1)

    # Estimate cycle_end: find the last day-of-week-matching-expiry in the next month
    next_month = last_month + 1
    next_year = last_year
    if next_month > 12:
        next_month = 1
        next_year += 1

    # Estimate: project the weekly pattern forward
    # Find the day-of-week of recent expiries
    expiry_weekday = last_expiry.weekday()
    cycle_end = _estimate_last_weekly_expiry(next_year, next_month, expiry_weekday)

    label = _make_cycle_label(cycle_start, cycle_end, next_year, next_month)
    return (cycle_start, cycle_end, label)


def _estimate_last_weekly_expiry(year, month, weekday):
    """
    Estimates the last weekly expiry of a month by finding the last occurrence
    of the given weekday in that month.
    
    Note: This is used only when actual data is not available yet for that month.
    The estimate self-corrects once data is downloaded.
    """
    last_day = calendar.monthrange(year, month)[1]
    dt = datetime.date(year, month, last_day)
    while dt.weekday() != weekday:
        dt -= datetime.timedelta(days=1)
    return dt


def _fallback_calendar_month(today):
    """Fallback when no option chain data exists — uses calendar month boundaries."""
    first_of_month = today.replace(day=1)
    last_day = calendar.monthrange(today.year, today.month)[1]
    last_of_month = today.replace(day=last_day)
    label = today.strftime("%b %Y") + " Series"
    return (first_of_month, last_of_month, label)


def _make_cycle_label(cycle_start, cycle_end, year, month):
    """Creates a display label like 'Sep Series (26 Aug - 22 Sep)'"""
    month_name = datetime.date(year, month, 1).strftime("%b")
    start_str = cycle_start.strftime("%d %b")
    end_str = cycle_end.strftime("%d %b")
    return f"{month_name} Series ({start_str} - {end_str})"


# ============================================================
# 5. HELPER FUNCTIONS FOR CONSUMER SCRIPTS
# ============================================================

def get_trading_days_in_cycle(today=None):
    """
    Returns count of weekdays (Mon-Fri) from cycle_start to today.
    Used by run_fno_analysis.py to know how many days to fetch.
    """
    if today is None:
        today = datetime.date.today()

    cycle_start, cycle_end, _ = get_current_expiry_cycle(today)

    count = 0
    current = cycle_start
    end = min(today, cycle_end)
    while current <= end:
        if current.weekday() < 5:
            count += 1
        current += datetime.timedelta(days=1)

    return max(count, 1)  # At least 1 day


def get_all_weekly_expiries_in_cycle(today=None):
    """
    Returns all weekly expiry dates that fall within the current cycle.
    Used for grouping data into weeks in the visualization.
    """
    if today is None:
        today = datetime.date.today()

    cycle_start, cycle_end, _ = get_current_expiry_cycle(today)
    weekly = filter_weekly_expiries(get_all_expiry_dates_from_data())

    return [d for d in weekly if cycle_start <= d <= cycle_end]


def is_new_cycle_started(today=None):
    """
    Checks if today is within the first 2 days of a new cycle.
    Used by cleanup script to know when to delete old data.
    """
    if today is None:
        today = datetime.date.today()

    cycle_start, _, _ = get_current_expiry_cycle(today)
    diff = (today - cycle_start).days
    return 0 <= diff <= 2


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  EXPIRY UTILS — Data-Driven Expiry Detection")
    print("=" * 60)

    all_exp = get_all_expiry_dates_from_data()
    print(f"\nAll expiry dates from data ({len(all_exp)}):")
    for d in all_exp:
        print(f"  {d} ({d.strftime('%A')})")

    weekly = filter_weekly_expiries(all_exp)
    print(f"\nWeekly expiries only ({len(weekly)}):")
    for d in weekly:
        print(f"  {d} ({d.strftime('%A')})")

    boundaries = get_monthly_expiry_boundaries(weekly)
    print(f"\nMonthly expiry boundaries:")
    for year, month, last_exp in boundaries:
        month_name = datetime.date(year, month, 1).strftime("%B %Y")
        print(f"  {month_name}: last weekly expiry = {last_exp} ({last_exp.strftime('%A')})")

    today = datetime.date.today()
    cycle_start, cycle_end, label = get_current_expiry_cycle(today)
    print(f"\nToday: {today}")
    print(f"Current cycle: {label}")
    print(f"  Start: {cycle_start}")
    print(f"  End:   {cycle_end}")
    print(f"  Trading days so far: {get_trading_days_in_cycle(today)}")
    print(f"  New cycle started?: {is_new_cycle_started(today)}")

    weekly_in_cycle = get_all_weekly_expiries_in_cycle(today)
    print(f"  Weekly expiries in cycle: {weekly_in_cycle}")
