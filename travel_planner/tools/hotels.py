from langchain.tools import tool

from travel_planner.mock_data import generate_hotels, parse_date, short_code


def _nights(check_in: str, check_out: str) -> int | str:
    try:
        nights = (parse_date(check_out) - parse_date(check_in)).days
    except ValueError as e:
        return f"Error: invalid date ({e}). Use YYYY-MM-DD."
    if nights < 1:
        return "Error: check_out must be after check_in."
    return nights


@tool
def search_hotels(
    city: str,
    check_in: str,
    check_out: str,
    guests: int = 1,
    max_price_per_night: int | None = None,
) -> list[dict] | str:
    """Search hotels in a city for a date range.

    Args:
        city: Destination city, e.g. "Tokyo".
        check_in: Check-in date as YYYY-MM-DD.
        check_out: Check-out date as YYYY-MM-DD.
        guests: Number of guests.
        max_price_per_night: Optional nightly budget cap in USD.
    """
    nights = _nights(check_in, check_out)
    if isinstance(nights, str):
        return nights
    hotels = generate_hotels(city, nights, guests)
    if max_price_per_night is not None:
        hotels = [h for h in hotels if h["price_per_night_usd"] <= max_price_per_night]
    return hotels or f"No hotels in {city} under ${max_price_per_night}/night."


@tool
def book_hotel(hotel_id: str, check_in: str, check_out: str, guest_name: str) -> dict | str:
    """Book a specific hotel by its hotel_id from search_hotels results.

    Args:
        hotel_id: The exact hotel_id returned by search_hotels, e.g. "HT-1A2B3C".
        check_in: Check-in date as YYYY-MM-DD.
        check_out: Check-out date as YYYY-MM-DD.
        guest_name: Full name of the lead guest.
    """
    if not hotel_id.startswith("HT-"):
        return f"Error: unknown hotel_id {hotel_id!r}. Use an id from search_hotels."
    nights = _nights(check_in, check_out)
    if isinstance(nights, str):
        return nights
    return {
        "status": "confirmed",
        "hotel_id": hotel_id,
        "guest_name": guest_name,
        "check_in": check_in,
        "check_out": check_out,
        "nights": nights,
        "confirmation_code": short_code("hotel-booking", hotel_id, check_in, check_out, guest_name),
    }
