from langchain.tools import tool

from travel_planner.mock_data import generate_flights, parse_date, short_code


@tool
def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None = None,
    passengers: int = 1,
) -> dict | str:
    """Search flights between two airports or cities.

    Args:
        origin: Origin airport code or city, e.g. "SFO".
        destination: Destination airport code or city, e.g. "HND" or "Tokyo".
        departure_date: Outbound date as YYYY-MM-DD.
        return_date: Optional return date as YYYY-MM-DD for a round trip.
        passengers: Number of passengers; prices are totals for all passengers.
    """
    try:
        outbound = parse_date(departure_date)
        inbound = parse_date(return_date) if return_date else None
    except ValueError as e:
        return f"Error: invalid date ({e}). Use YYYY-MM-DD."
    if inbound and inbound < outbound:
        return "Error: return_date is before departure_date."

    results = {"outbound": generate_flights(origin, destination, departure_date, passengers)}
    if return_date:
        results["return"] = generate_flights(destination, origin, return_date, passengers)
    return results


@tool
def book_flight(flight_id: str, passenger_name: str) -> dict | str:
    """Book a specific flight by its flight_id from search_flights results.

    Args:
        flight_id: The exact flight_id returned by search_flights, e.g. "FL-1A2B3C".
        passenger_name: Full name of the lead passenger.
    """
    if not flight_id.startswith("FL-"):
        return f"Error: unknown flight_id {flight_id!r}. Use an id from search_flights."
    return {
        "status": "confirmed",
        "flight_id": flight_id,
        "passenger_name": passenger_name,
        "confirmation_code": short_code("flight-booking", flight_id, passenger_name),
    }
