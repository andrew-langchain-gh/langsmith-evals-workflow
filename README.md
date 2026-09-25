# Deep Agent Travel Planner

A travel planning agent built on [Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview). A coordinator agent plans the trip and delegates every search and booking to specialist subagents. All tools currently return **deterministic mock data**, so we can iterate on prompts and orchestration without paying for travel APIs.

```
                    ┌──────────────────────────┐
   user ◄──────────►│  coordinator (main agent)│  write_todos, virtual FS (/itinerary.md), task
                    └────────────┬─────────────┘
          ┌──────────────┬───────┴───────┬──────────────────┐
          ▼              ▼               ▼                  ▼
  calendar-checker  flight-booker   hotel-booker     activity-planner
  get_calendar_     search_flights  search_hotels    search_activities
  events            book_flight*    book_hotel*      get_weather_forecast
  find_free_windows
                                          * requires human approval
```

| Subagent | Tools | Module |
|---|---|---|
| `calendar-checker` | `get_calendar_events`, `find_free_windows` | `travel_planner/tools/calendar.py` |
| `flight-booker` | `search_flights`, `book_flight` (HITL) | `travel_planner/tools/flights.py` |
| `hotel-booker` | `search_hotels`, `book_hotel` (HITL) | `travel_planner/tools/hotels.py` |
| `activity-planner` | `search_activities`, `get_weather_forecast` | `travel_planner/tools/activities.py` |

## Setup

```sh
uv sync
cp .env.example .env   # set ANTHROPIC_API_KEY (and LangSmith keys for tracing)
```

`TRAVEL_PLANNER_MODEL` picks the model (default `anthropic:claude-haiku-4-5-20251001`). `ANTHROPIC_BASE_URL` and `ANTHROPIC_CUSTOM_HEADERS` are read by the Anthropic SDK, so you can route calls through the LangSmith gateway.

## Run

Interactive CLI:

```sh
uv run main.py
```

```
You: Plan a 4-day trip from SFO to Tokyo, Oct 20-24, mid-range budget, I like food and museums.
  → calendar-checker: Check availability ...
  → flight-booker: Search for flights ...
  → hotel-booker: Search for hotels ...
```

When a booking is proposed, the CLI pauses and asks you to `[a]pprove`, `[e]dit` (new args as JSON), or `[r]eject` (with a reason). Type `/itinerary` to print the generated itinerary and `/quit` to exit.

LangGraph Studio:

```sh
uv run langgraph dev
```

## Tests

```sh
uv run pytest
```

These tests cover the mock tools only and make no LLM calls.

## Mock data → real APIs

`travel_planner/mock_data.py` seeds its generators from the tool arguments, so the same query always returns the same results for any city or date. To go live, replace a tool's body in `travel_planner/tools/` with a real API call and keep the tool's name, signature, and ID prefixes (`FL-`, `HT-`). The subagent prompts and the approval config in `travel_planner/subagents.py` can stay as they are.
