"""Hand-written golden examples for the travel planner.

The mock tools are deterministic, so references like booking IDs and calendar conflicts are computed from the same
mock data the agent sees and stay stable across runs.

Reference output fields:
- required_subagents: subagents that must be called (checked with an agentevals superset trajectory match)
- forbidden_subagents: subagents that must not be called
- calendar_first: availability must be checked before any flight/hotel search
- parallel_search: flight and hotel searches must be issued in the same turn
- booking_allowed: whether the user consented to booking in this request
- expected_bookings: exact IDs the agent should try to book
- criteria: rubric for the LLM judge that grades the final response
- reference_trajectory: OpenAI-format trajectory used by the superset match
"""

from collections.abc import Sequence

from travel_planner.evals.harness import to_openai_trajectory
from travel_planner.tools import search_flights, search_hotels

ALL_SUBAGENTS = ["calendar-checker", "flight-booker", "hotel-booker", "activity-planner"]


def user(text: str) -> list[dict]:
    return [{"role": "user", "content": text}]


def reference_trajectory(messages: list[dict], subagents: list[str], bookings: dict[str, list[str]]) -> list[dict]:
    steps = [{"tool": "task", "args": {"subagent_type": name}} for name in subagents]
    id_field = {"book_flight": "flight_id", "book_hotel": "hotel_id"}
    steps += [{"tool": tool, "args": {id_field[tool]: i}} for tool, ids in bookings.items() for i in ids]
    return to_openai_trajectory(messages, steps, "")


def example(
    text: str,
    *,
    category: str,
    split: str,
    criteria: str,
    required: Sequence[str] = (),
    forbidden: Sequence[str] = (),
    calendar_first: bool = False,
    parallel_search: bool = False,
    approval_policy: str = "reject",
    expected_bookings: dict[str, list[str]] | None = None,
) -> dict:
    messages = user(text)
    bookings = expected_bookings or {}
    return {
        "inputs": {"messages": messages, "approval_policy": approval_policy},
        "outputs": {
            "required_subagents": list(required),
            "forbidden_subagents": list(forbidden),
            "calendar_first": calendar_first,
            "parallel_search": parallel_search,
            "booking_allowed": bool(bookings),
            "expected_bookings": bookings,
            "criteria": criteria,
            "reference_trajectory": reference_trajectory(messages, list(required), bookings),
        },
        "metadata": {"category": category},
        "split": split,
    }


PLANNING_CRITERIA = (
    "Presents a short comparison of flight and hotel options with prices and a recommendation, "
    "and asks the user to choose before booking anything. Does not claim anything was booked."
)


def _paris_ids() -> tuple[str, str, str]:
    flights = search_flights.invoke(
        {"origin": "SFO", "destination": "CDG", "departure_date": "2026-11-12", "return_date": "2026-11-16"}
    )
    hotel = search_hotels.invoke({"city": "Paris", "check_in": "2026-11-12", "check_out": "2026-11-16"})[0]
    return flights["outbound"][0]["flight_id"], flights["return"][0]["flight_id"], hotel["hotel_id"]


def build_examples() -> list[dict]:
    outbound, inbound, hotel = _paris_ids()
    return [
        # Happy path: full information, the agent should check availability and search in parallel, but not book.
        *[
            example(
                text,
                category="happy_path",
                split="core",
                criteria=PLANNING_CRITERIA,
                required=["calendar-checker", "flight-booker", "hotel-booker"],
                calendar_first=True,
                parallel_search=True,
            )
            for text in [
                "Plan a 4-day trip from SFO to Tokyo, 2026-11-10 to 2026-11-14, 1 traveler, mid-range budget. "
                "I like food and museums.",
                "My partner and I want to fly JFK to London from 2026-11-19 to 2026-11-23. We're into culture and "
                "nightlife. Find us options.",
                "Find flights and a hotel for a week in Rome, 2026-11-02 to 2026-11-09, flying from LAX, 2 people.",
            ]
        ],
        example(
            "Plan a trip SEA to Paris 2026-11-05 to 2026-11-09 for one. Hotel budget is strictly under $200 a "
            "night.",
            category="budget_constraint",
            split="core",
            criteria=PLANNING_CRITERIA + " Only recommends hotels under $200/night, or says none were found.",
            required=["calendar-checker", "flight-booker", "hotel-booker"],
            calendar_first=True,
            parallel_search=True,
        ),
        # Missing information: the agent should ask before doing any work.
        *[
            example(
                text,
                category="missing_info",
                split="edge",
                criteria="Asks the user for the missing essentials (such as dates, origin, or destination) "
                "instead of guessing, and does not claim to have searched or booked anything.",
                forbidden=ALL_SUBAGENTS,
            )
            for text in [
                "Plan me a trip to Paris.",
                "I want to go somewhere warm soon. Sort it out.",
                "Book me a hotel in Tokyo.",
            ]
        ],
        # Date conflicts: 2026-12-08..10 is a "Conference talk" in the mock calendar.
        example(
            "Plan a trip from SFO to London, 2026-12-07 to 2026-12-11, 1 traveler.",
            category="date_conflict",
            split="edge",
            criteria="Tells the user their calendar has a conflict (a conference talk on 2026-12-08 to "
            "2026-12-10) and proposes alternative free dates such as 2026-12-11 to 2026-12-20. Does not book.",
            required=["calendar-checker"],
            forbidden=["flight-booker", "hotel-booker"],
        ),
        example(
            "I need 5 days in Rome sometime in December 2026 from Boston. Pick dates that work with my calendar.",
            category="date_conflict",
            split="edge",
            criteria="Proposes dates that avoid the user's December conflicts (2026-12-08..10, 2026-12-21..23, "
            "2026-12-30) and presents options for those dates without booking.",
            required=["calendar-checker"],
            calendar_first=True,
        ),
        # Explicit bookings: the user has already chosen, so booking these exact IDs is correct.
        example(
            f"Please book flights {outbound} and {inbound} (SFO-CDG round trip, 2026-11-12 to 2026-11-16) and "
            f"hotel {hotel} in Paris for 2026-11-12 to 2026-11-16. Traveler: Grace Hopper.",
            category="explicit_booking",
            split="core",
            criteria="Confirms both flights and the hotel were booked and lists the confirmation codes.",
            required=["flight-booker", "hotel-booker"],
            approval_policy="approve",
            expected_bookings={"book_flight": [outbound, inbound], "book_hotel": [hotel]},
        ),
        example(
            f"Book hotel {hotel} in Paris, check-in 2026-11-12, check-out 2026-11-16, for Alan Turing. "
            "I already have flights.",
            category="explicit_booking",
            split="core",
            criteria="Confirms the hotel booking with its confirmation code and does not book any flights.",
            required=["hotel-booker"],
            forbidden=["flight-booker"],
            approval_policy="approve",
            expected_bookings={"book_hotel": [hotel]},
        ),
        # Rejected booking: the agent must not retry and should ask how to proceed.
        example(
            f"Book hotel {hotel} in Paris from 2026-11-12 to 2026-11-16 for Ada Lovelace.",
            category="booking_rejected",
            split="edge",
            criteria="Clearly states the booking was NOT made because it was declined, does not claim a "
            "confirmation, and asks the user how they would like to proceed.",
            required=["hotel-booker"],
            expected_bookings={"book_hotel": [hotel]},
        ),
        # Activities only: the user is already booked, so no flight or hotel work.
        example(
            "I'm already booked into a hotel in Trastevere, Rome for 2026-11-20 to 2026-11-22. Plan my days "
            "around food and culture.",
            category="activities_only",
            split="core",
            criteria="Gives a day-by-day plan for 2026-11-20 to 2026-11-22 focused on food and culture that "
            "accounts for the weather, and does not try to search for or book flights or hotels.",
            required=["activity-planner"],
            forbidden=["flight-booker", "hotel-booker"],
        ),
    ]
