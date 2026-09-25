from langchain.tools import tool

from travel_planner.mock_data import ACTIVITY_CATALOG, generate_activities, generate_weather, parse_date


@tool
def search_activities(city: str, date: str, interests: list[str] | None = None) -> list[dict] | str:
    """Search things to do in a city on a given day.

    Args:
        city: City to search, e.g. "Tokyo".
        date: Day of the activity as YYYY-MM-DD.
        interests: Categories to include. Options: food, museums, outdoors, nightlife, culture,
            shopping. Defaults to all.
    """
    try:
        parse_date(date)
    except ValueError as e:
        return f"Error: invalid date ({e}). Use YYYY-MM-DD."
    categories = [i.strip().lower() for i in interests] if interests else list(ACTIVITY_CATALOG)
    unknown = [c for c in categories if c not in ACTIVITY_CATALOG]
    if unknown:
        return f"Error: unknown interests {unknown}. Options: {list(ACTIVITY_CATALOG)}."
    return generate_activities(city, date, categories)


@tool
def get_weather_forecast(city: str, date: str) -> dict | str:
    """Get the weather forecast for a city on a given day.

    Args:
        city: City name, e.g. "Tokyo".
        date: Day as YYYY-MM-DD.
    """
    try:
        parse_date(date)
    except ValueError as e:
        return f"Error: invalid date ({e}). Use YYYY-MM-DD."
    return generate_weather(city, date)
