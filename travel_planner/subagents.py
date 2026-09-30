from deepagents import SubAgent

from travel_planner.tools import (
    book_flight,
    book_hotel,
    find_free_windows,
    get_calendar_events,
    get_weather_forecast,
    search_activities,
    search_flights,
    search_hotels,
)

STATELESS_RULES = """\
You are called once per task and keep no memory between calls, so finish the whole job in this single run.
Your final message is the only thing the coordinator sees: make it compact markdown with every detail it needs.
Never invent IDs, prices, or confirmation codes. Only report what your tools returned.
If a tool returns an error, fix the input and retry once, then report the error."""

flight_booker: SubAgent = {
    "name": "flight-booker",
    "description": (
        "Searches and books flights. For a search, give origin, destination, departure date, optional return date, "
        "passenger count, and budget/preferences; it returns a ranked shortlist with flight_ids. For a booking, give "
        "the exact flight_id(s) and the lead passenger's full name; it returns confirmation codes."
    ),
    "system_prompt": f"""You are a flight specialist.

{STATELESS_RULES}

Search mode: call search_flights, then return the best 3 outbound (and return, if round trip) options as a table with
flight_id, airline, departure time, duration, stops, and total price. Recommend one and say why in one line.

Booking mode: call book_flight exactly once per flight_id you were given. Do not search first and do not substitute a
different flight.""",
    "tools": [search_flights, book_flight],
}

hotel_booker: SubAgent = {
    "name": "hotel-booker",
    "description": (
        "Searches and books hotels. For a search, give city, check-in/check-out dates, guest count, and budget/"
        "neighborhood preferences; it returns a ranked shortlist with hotel_ids. For a booking, give the exact "
        "hotel_id, dates, and lead guest's full name; it returns a confirmation code."
    ),
    "system_prompt": f"""You are a hotel specialist.

{STATELESS_RULES}

Search mode: call search_hotels, then return the best 3 options as a table with hotel_id, name, neighborhood, rating,
nightly price, and total price. Recommend one and say why in one line.

Booking mode: call book_hotel exactly once with the hotel_id and dates you were given. Do not search first and do not
substitute a different hotel.""",
    "tools": [search_hotels, book_hotel],
}

calendar_checker: SubAgent = {
    "name": "calendar-checker",
    "description": (
        "Finds free dates in the traveler's calendar when their dates are flexible. Give a date range and trip "
        "length; it returns conflicting events and free windows long enough for the trip."
    ),
    "system_prompt": f"""You are a calendar assistant.

{STATELESS_RULES}

Call get_calendar_events and find_free_windows for the requested range, using the trip length as min_days.
Return: (1) whether the requested dates are free, (2) any conflicting events, (3) up to 3 free windows that fit.""",
    "tools": [get_calendar_events, find_free_windows],
}

activity_planner: SubAgent = {
    "name": "activity-planner",
    "description": (
        "Plans day-by-day activities. Give the city, the exact dates, the traveler's interests, and where they are "
        "staying; it returns a weather-aware day-by-day plan."
    ),
    "system_prompt": f"""You are a local activities planner.

{STATELESS_RULES}

For each date: call get_weather_forecast and search_activities with the traveler's interests (valid interests: food,
museums, outdoors, nightlife, culture, shopping). Choose 2-3 activities per day, preferring indoor ones when rain is
likely. Return a day-by-day plan with the weather, each activity's activity_id, title, duration, and price, and an
estimated daily activity cost.""",
    "tools": [search_activities, get_weather_forecast],
}

SUBAGENTS: list[SubAgent] = [calendar_checker, flight_booker, hotel_booker, activity_planner]
