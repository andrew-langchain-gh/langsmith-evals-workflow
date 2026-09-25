"""Deterministic mock data generators.

Every generator seeds its RNG from the call arguments, so identical queries
always return identical results while any city or date still works.
"""

import hashlib
import random
from datetime import date, timedelta

AIRLINES = ["United", "Delta", "American", "JAL", "ANA", "Lufthansa", "Air France", "British Airways", "Alaska"]

CITY_NEIGHBORHOODS = {
    "tokyo": ["Shinjuku", "Shibuya", "Ginza", "Asakusa", "Roppongi"],
    "paris": ["Le Marais", "Saint-Germain", "Montmartre", "Latin Quarter", "Opéra"],
    "london": ["Covent Garden", "Shoreditch", "South Bank", "Kensington", "Soho"],
    "new york": ["Midtown", "SoHo", "Lower East Side", "Upper West Side", "Williamsburg"],
    "rome": ["Trastevere", "Monti", "Centro Storico", "Prati", "Testaccio"],
}
GENERIC_NEIGHBORHOODS = ["Old Town", "Downtown", "Riverside", "Arts District", "Harbor"]

HOTEL_BRANDS = ["Grand", "Park", "Boutique", "Central", "Garden", "Royal", "Harbor View", "Loft"]
HOTEL_SUFFIXES = ["Hotel", "Inn", "Suites", "Residences", "House"]

ACTIVITY_CATALOG = {
    "food": ["Street food walking tour", "Cooking class", "Market tasting crawl", "Chef's tasting dinner"],
    "museums": ["National museum visit", "Modern art gallery", "History museum guided tour", "Science museum"],
    "outdoors": ["Park and garden walk", "Day hike", "Bike tour", "River cruise"],
    "nightlife": ["Rooftop bar crawl", "Live jazz club", "Night market"],
    "culture": ["Historic temple/cathedral tour", "Traditional performance", "Architecture walk"],
    "shopping": ["Local design district", "Vintage shopping tour", "Department store food hall"],
}
INDOOR_CATEGORIES = {"museums", "shopping", "culture"}

WEATHER_CONDITIONS = ["sunny", "partly cloudy", "cloudy", "light rain", "rain"]

CALENDAR_EVENT_TITLES = [
    "Team offsite",
    "Quarterly planning",
    "Dentist appointment",
    "Friend's wedding",
    "Conference talk",
    "Product launch",
    "Family visit",
]


def seeded_rng(*parts: object) -> random.Random:
    key = "|".join(str(p).strip().lower() for p in parts)
    seed = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big")
    return random.Random(seed)


def short_code(*parts: object, length: int = 6) -> str:
    key = "|".join(str(p).strip().lower() for p in parts)
    return hashlib.sha256(key.encode()).hexdigest()[:length].upper()


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def neighborhoods_for(city: str) -> list[str]:
    return CITY_NEIGHBORHOODS.get(city.strip().lower(), GENERIC_NEIGHBORHOODS)


def generate_flights(origin: str, destination: str, departure_date: str, passengers: int) -> list[dict]:
    rng = seeded_rng("flights", origin, destination, departure_date)
    flights = []
    for _ in range(4):
        airline = rng.choice(AIRLINES)
        stops = rng.choice([0, 0, 1, 1, 2])
        depart_hour = rng.randint(6, 22)
        duration_minutes = rng.randint(90, 780) + stops * rng.randint(60, 180)
        price_per_person = rng.randint(180, 1400) - stops * 80
        flight_id = f"FL-{short_code(origin, destination, departure_date, airline, depart_hour)}"
        flights.append(
            {
                "flight_id": flight_id,
                "airline": airline,
                "origin": origin.upper(),
                "destination": destination.upper(),
                "date": departure_date,
                "departure_time": f"{depart_hour:02d}:{rng.choice(['00', '15', '30', '45'])}",
                "duration": f"{duration_minutes // 60}h {duration_minutes % 60}m",
                "stops": stops,
                "price_usd": max(price_per_person, 99) * passengers,
            }
        )
    return sorted(flights, key=lambda f: f["price_usd"])


def generate_hotels(city: str, nights: int, guests: int) -> list[dict]:
    rng = seeded_rng("hotels", city)
    hotels = []
    for neighborhood in rng.sample(neighborhoods_for(city), 4):
        name = f"{rng.choice(HOTEL_BRANDS)} {neighborhood} {rng.choice(HOTEL_SUFFIXES)}"
        nightly = rng.randint(90, 520) + (guests - 1) * 25
        hotels.append(
            {
                "hotel_id": f"HT-{short_code(city, name)}",
                "name": name,
                "city": city.title(),
                "neighborhood": neighborhood,
                "rating": round(rng.uniform(3.6, 4.9), 1),
                "price_per_night_usd": nightly,
                "total_price_usd": nightly * nights,
            }
        )
    return sorted(hotels, key=lambda h: h["price_per_night_usd"])


def generate_calendar_events(start: date, end: date) -> list[dict]:
    """Events are anchored to ISO weeks so overlapping queries agree."""
    events = []
    week_start = start - timedelta(days=start.weekday())
    while week_start <= end:
        rng = seeded_rng("calendar", week_start.isoformat())
        if rng.random() < 0.6:
            event_start = week_start + timedelta(days=rng.randint(0, 6))
            event_end = event_start + timedelta(days=rng.choice([0, 0, 1, 2]))
            if event_end >= start and event_start <= end:
                events.append(
                    {
                        "title": rng.choice(CALENDAR_EVENT_TITLES),
                        "start_date": event_start.isoformat(),
                        "end_date": event_end.isoformat(),
                    }
                )
        week_start += timedelta(days=7)
    return events


def generate_activities(city: str, day: str, interests: list[str]) -> list[dict]:
    rng = seeded_rng("activities", city, day, *sorted(interests))
    activities = []
    for category in interests:
        for title in rng.sample(ACTIVITY_CATALOG[category], 2):
            activities.append(
                {
                    "activity_id": f"AC-{short_code(city, day, title)}",
                    "title": f"{title} in {city.title()}",
                    "category": category,
                    "indoor": category in INDOOR_CATEGORIES,
                    "duration_hours": rng.choice([1.5, 2, 3, 4]),
                    "price_usd": rng.choice([0, 15, 25, 40, 60, 95, 150]),
                    "neighborhood": rng.choice(neighborhoods_for(city)),
                }
            )
    return activities


def generate_weather(city: str, day: str) -> dict:
    rng = seeded_rng("weather", city, day)
    high = rng.randint(8, 32)
    condition = rng.choice(WEATHER_CONDITIONS)
    return {
        "city": city.title(),
        "date": day,
        "condition": condition,
        "high_c": high,
        "low_c": high - rng.randint(4, 10),
        "precipitation_chance": {"light rain": 60, "rain": 90}.get(condition, rng.randint(0, 25)),
    }
