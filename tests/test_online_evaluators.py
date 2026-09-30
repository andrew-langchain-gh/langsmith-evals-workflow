from travel_planner.evals.online import BOOKING_CONSENT, PARALLEL_SEARCH, load

parallel_search = load(PARALLEL_SEARCH)
booking_consent = load(BOOKING_CONSENT)


def human(text: str) -> dict:
    return {"type": "human", "content": text}


def delegate(*calls: tuple[str, str]) -> dict:
    return {
        "type": "ai",
        "content": "",
        "tool_calls": [
            {"name": "task", "args": {"subagent_type": s, "description": d}, "id": f"c{i}"}
            for i, (s, d) in enumerate(calls)
        ],
    }


def run(*messages: dict) -> dict:
    return {"outputs": {"messages": list(messages)}}


def test_parallel_search():
    good = run(human("plan"), delegate(("flight-booker", "Search flights"), ("hotel-booker", "Search hotels")))
    bad = run(
        human("plan"),
        delegate(("flight-booker", "Search flights")),
        delegate(("hotel-booker", "Search hotels")),
    )
    assert parallel_search(good) == {"parallel_search": True}
    assert parallel_search(bad) == {"parallel_search": False}
    assert parallel_search(run(human("plan"), delegate(("hotel-booker", "Search hotels")))) == {}


def test_booking_in_same_turn_as_search_violates_consent():
    v1_turn = run(
        human("plan"),
        delegate(("flight-booker", "Search flights SFO-HND")),
        delegate(("flight-booker", "Book flight FL-1 for Traveler")),
    )
    assert booking_consent(v1_turn) == {"booking_consent": False}


def test_booking_after_user_choice_is_consented():
    v2_conversation = run(
        human("plan"),
        delegate(("flight-booker", "Search flights SFO-HND")),
        human("book FL-1, I'm Ada"),
        delegate(("flight-booker", "Book flight FL-1 for Ada")),
    )
    assert booking_consent(v2_conversation) == {"booking_consent": True}
    assert booking_consent(run(human("plan"), delegate(("hotel-booker", "Search hotels")))) == {}


def test_lc_serialized_messages_are_supported():
    serialized = {"outputs": {"messages": [{"lc": 1, "kwargs": m} for m in run(
        human("plan"), delegate(("flight-booker", "Search flights")), delegate(("hotel-booker", "Search hotels"))
    )["outputs"]["messages"]]}}
    assert parallel_search(serialized) == {"parallel_search": False}
