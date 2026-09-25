from travel_planner.evals.evaluators import (
    NOT_APPLICABLE,
    all_checks_pass_rate,
    avoided_unneeded_subagents,
    booking_consent,
    calendar_checked_first,
    parallel_search,
    trajectory_superset_match,
)
from travel_planner.evals.golden_examples import build_examples, example
from travel_planner.evals.harness import to_openai_trajectory

REQUEST = [{"role": "user", "content": "Plan a trip"}]


def task(subagent: str, message_id: str, description: str = "Search") -> dict:
    return {
        "agent": "coordinator",
        "tool": "task",
        "args": {"subagent_type": subagent, "description": description},
        "message_id": message_id,
    }


def book(tool: str, id_field: str, value: str) -> dict:
    return {"agent": "subagent", "tool": tool, "args": {id_field: value, "passenger_name": "A"}, "message_id": "s"}


def outputs(*steps: dict) -> dict:
    return {"steps": list(steps), "trajectory": to_openai_trajectory(REQUEST, list(steps), "done"), "final_response": "done"}


HAPPY = example(
    "Plan a trip",
    category="happy_path",
    split="core",
    criteria="",
    required=["calendar-checker", "flight-booker", "hotel-booker"],
    calendar_first=True,
    parallel_search=True,
)["outputs"]

V2_LIKE = outputs(
    task("calendar-checker", "m1"), task("flight-booker", "m2"), task("hotel-booker", "m2")
)
V1_LIKE = outputs(
    task("flight-booker", "m1"),
    task("hotel-booker", "m2"),
    task("flight-booker", "m3", "Book flight FL-1"),
    book("book_flight", "flight_id", "FL-1"),
)


def score(result) -> bool:
    return result["score"]


def test_good_trajectory_passes_every_check():
    assert score(calendar_checked_first(V2_LIKE, HAPPY))
    assert score(parallel_search(V2_LIKE, HAPPY))
    assert score(booking_consent(V2_LIKE, HAPPY))
    assert score(trajectory_superset_match(V2_LIKE, HAPPY))


def test_v1_style_trajectory_fails_ordering_parallelism_and_consent():
    assert not score(calendar_checked_first(V1_LIKE, HAPPY))
    assert not score(parallel_search(V1_LIKE, HAPPY))
    assert not score(booking_consent(V1_LIKE, HAPPY))
    assert not score(trajectory_superset_match(V1_LIKE, HAPPY))


def test_booking_delegation_does_not_count_as_parallel_search():
    searched_then_booked = outputs(
        task("calendar-checker", "m1"),
        task("flight-booker", "m2"),
        task("hotel-booker", "m3", "Book hotel HT-1"),
    )
    assert not score(parallel_search(searched_then_booked, HAPPY))


def test_repeated_booking_fails_consent():
    reference = {**HAPPY, "booking_allowed": True}
    twice = outputs(book("book_hotel", "hotel_id", "HT-1"), book("book_hotel", "hotel_id", "HT-1"))
    assert not score(booking_consent(twice, reference))


def test_superset_match_checks_exact_booking_ids():
    ex = next(e for e in build_examples() if e["metadata"]["category"] == "explicit_booking")
    reference = ex["outputs"]
    ids = reference["expected_bookings"]
    correct = outputs(
        task("flight-booker", "m1", "Book"),
        task("hotel-booker", "m1", "Book"),
        *[book("book_flight", "flight_id", i) for i in ids["book_flight"]],
        book("book_hotel", "hotel_id", ids["book_hotel"][0]),
    )
    wrong_hotel = outputs(*correct["steps"][:-1], book("book_hotel", "hotel_id", "HT-WRONG"))
    assert score(trajectory_superset_match(correct, reference))
    assert not score(trajectory_superset_match(wrong_hotel, reference))


def test_not_applicable_checks_are_skipped():
    missing_info = next(e for e in build_examples() if e["metadata"]["category"] == "missing_info")["outputs"]
    assert calendar_checked_first(outputs(), missing_info) == NOT_APPLICABLE
    assert trajectory_superset_match(outputs(), missing_info) == NOT_APPLICABLE
    assert score(avoided_unneeded_subagents(outputs(), missing_info))
    assert not score(avoided_unneeded_subagents(outputs(task("flight-booker", "m1")), missing_info))


def test_pass_rate_summary():
    assert all_checks_pass_rate([V2_LIKE, V1_LIKE], [HAPPY, HAPPY])["score"] == 0.5


def test_trajectory_nests_subagent_steps_and_groups_parallel_calls():
    steps = [
        {**task("flight-booker", "m1"), "call_seq": 1, "result_seq": 6, "result": "flight report"},
        {**task("hotel-booker", "m1"), "call_seq": 2, "result_seq": 7, "result": "hotel report"},
        {"agent": "subagent", "tool": "search_flights", "args": {}, "message_id": "s1", "call_seq": 3, "result_seq": 4},
        {"agent": "subagent", "tool": "search_hotels", "args": {}, "message_id": "s2", "call_seq": 5, "result_seq": 8},
    ]
    trajectory = to_openai_trajectory(REQUEST, steps, "done")
    kinds = [
        m["role"] if m["role"] != "assistant" or "tool_calls" not in m else [c["function"]["name"] for c in m["tool_calls"]]
        for m in trajectory
    ]
    assert kinds == ["user", ["task", "task"], ["search_flights"], "tool", ["search_hotels"], "tool", "tool", "tool", "assistant"]
    assert trajectory[1]["content"] == "[coordinator]" and trajectory[2]["content"] == "[subagent]"
