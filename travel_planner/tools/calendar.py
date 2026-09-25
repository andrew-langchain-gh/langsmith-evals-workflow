from datetime import timedelta

from langchain.tools import tool

from travel_planner.mock_data import generate_calendar_events, parse_date


@tool
def get_calendar_events(start_date: str, end_date: str) -> list[dict] | str:
    """List the user's calendar events that overlap a date range.

    Args:
        start_date: First day of the range as YYYY-MM-DD.
        end_date: Last day of the range (inclusive) as YYYY-MM-DD.
    """
    try:
        start, end = parse_date(start_date), parse_date(end_date)
    except ValueError as e:
        return f"Error: invalid date ({e}). Use YYYY-MM-DD."
    if end < start:
        return "Error: end_date is before start_date."
    return generate_calendar_events(start, end)


@tool
def find_free_windows(start_date: str, end_date: str, min_days: int = 1) -> list[dict] | str:
    """Find stretches of consecutive days with no calendar events.

    Args:
        start_date: First day of the search range as YYYY-MM-DD.
        end_date: Last day of the search range (inclusive) as YYYY-MM-DD.
        min_days: Minimum length of a free window in days.
    """
    try:
        start, end = parse_date(start_date), parse_date(end_date)
    except ValueError as e:
        return f"Error: invalid date ({e}). Use YYYY-MM-DD."
    if end < start:
        return "Error: end_date is before start_date."

    busy = set()
    for event in generate_calendar_events(start, end):
        day, last = parse_date(event["start_date"]), parse_date(event["end_date"])
        while day <= last:
            busy.add(day)
            day += timedelta(days=1)

    windows = []
    window_start = None
    day = start
    while day <= end + timedelta(days=1):
        free = day <= end and day not in busy
        if free and window_start is None:
            window_start = day
        elif not free and window_start is not None:
            window_end = day - timedelta(days=1)
            length = (window_end - window_start).days + 1
            if length >= min_days:
                windows.append(
                    {"start_date": window_start.isoformat(), "end_date": window_end.isoformat(), "days": length}
                )
            window_start = None
        day += timedelta(days=1)
    return windows
