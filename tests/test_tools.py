from datetime import timedelta

from travel_planner.mock_data import parse_date
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


def test_search_flights_is_deterministic_and_round_trip():
    args = {"origin": "SFO", "destination": "HND", "departure_date": "2026-10-10", "return_date": "2026-10-14"}
    first = search_flights.invoke(args)
    assert first == search_flights.invoke(args)
    assert len(first["outbound"]) == 4
    assert len(first["return"]) == 4
    assert all(f["flight_id"].startswith("FL-") for f in first["outbound"])
    prices = [f["price_usd"] for f in first["outbound"]]
    assert prices == sorted(prices)


def test_search_flights_rejects_bad_dates():
    assert search_flights.invoke({"origin": "SFO", "destination": "HND", "departure_date": "10/10/2026"}).startswith(
        "Error"
    )
    assert search_flights.invoke(
        {"origin": "SFO", "destination": "HND", "departure_date": "2026-10-10", "return_date": "2026-10-01"}
    ).startswith("Error")


def test_book_flight():
    flight_id = search_flights.invoke({"origin": "SFO", "destination": "HND", "departure_date": "2026-10-10"})[
        "outbound"
    ][0]["flight_id"]
    booking = book_flight.invoke({"flight_id": flight_id, "passenger_name": "Ada Lovelace"})
    assert booking["status"] == "confirmed"
    assert len(booking["confirmation_code"]) == 6
    assert book_flight.invoke({"flight_id": "BOGUS", "passenger_name": "Ada"}).startswith("Error")


def test_search_hotels_totals_and_budget():
    hotels = search_hotels.invoke({"city": "Tokyo", "check_in": "2026-10-10", "check_out": "2026-10-14"})
    assert len(hotels) == 4
    assert all(h["total_price_usd"] == h["price_per_night_usd"] * 4 for h in hotels)

    cap = hotels[1]["price_per_night_usd"]
    capped = search_hotels.invoke(
        {"city": "Tokyo", "check_in": "2026-10-10", "check_out": "2026-10-14", "max_price_per_night": cap}
    )
    assert all(h["price_per_night_usd"] <= cap for h in capped)


def test_book_hotel_validates():
    ok = book_hotel.invoke(
        {"hotel_id": "HT-ABC123", "check_in": "2026-10-10", "check_out": "2026-10-12", "guest_name": "Ada"}
    )
    assert ok["nights"] == 2
    assert book_hotel.invoke(
        {"hotel_id": "HT-ABC123", "check_in": "2026-10-12", "check_out": "2026-10-10", "guest_name": "Ada"}
    ).startswith("Error")


def test_free_windows_never_overlap_events():
    rng = {"start_date": "2026-10-01", "end_date": "2026-12-31"}
    events = get_calendar_events.invoke(rng)
    windows = find_free_windows.invoke({**rng, "min_days": 1})
    assert events and windows

    busy = set()
    for e in events:
        day = parse_date(e["start_date"])
        while day <= parse_date(e["end_date"]):
            busy.add(day)
            day += timedelta(days=1)
    for w in windows:
        day = parse_date(w["start_date"])
        while day <= parse_date(w["end_date"]):
            assert day not in busy
            day += timedelta(days=1)


def test_calendar_consistent_across_overlapping_ranges():
    wide = get_calendar_events.invoke({"start_date": "2026-10-01", "end_date": "2026-11-30"})
    narrow = get_calendar_events.invoke({"start_date": "2026-10-15", "end_date": "2026-10-31"})
    assert all(e in wide for e in narrow)


def test_activities_and_weather():
    acts = search_activities.invoke({"city": "Tokyo", "date": "2026-10-11", "interests": ["food", "museums"]})
    assert {a["category"] for a in acts} == {"food", "museums"}
    assert search_activities.invoke({"city": "Tokyo", "date": "2026-10-11", "interests": ["skydiving"]}).startswith(
        "Error"
    )
    weather = get_weather_forecast.invoke({"city": "Tokyo", "date": "2026-10-11"})
    assert weather["low_c"] < weather["high_c"]
