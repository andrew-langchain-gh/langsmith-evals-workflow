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
  events            book_flight     book_hotel       get_weather_forecast
  find_free_windows
```

| Subagent | Tools | Module |
|---|---|---|
| `calendar-checker` | `get_calendar_events`, `find_free_windows` | `travel_planner/tools/calendar.py` |
| `flight-booker` | `search_flights`, `book_flight` | `travel_planner/tools/flights.py` |
| `hotel-booker` | `search_hotels`, `book_hotel` | `travel_planner/tools/hotels.py` |
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
  → flight-booker: Search for flights ...
  → hotel-booker: Search for hotels ...
```

Bookings are mock and go through as soon as you pick an option, with no approval step. Type `/itinerary` to print the generated itinerary and `/quit` to exit.

LangGraph Studio:

```sh
uv run langgraph dev
```

## Tests

```sh
uv run pytest
```

These tests cover the mock tools and make no LLM calls.

## Evaluation demo

`evals/` holds four numbered scripts for a LangSmith evaluation walkthrough. They cover a hand-curated golden dataset, an experiment scored by a correctness judge built in the UI, simulated production traffic for online evaluators, and a trajectory evaluator on a dataset built from a reviewed trace. The evaluators, rules, and queue are created live in the LangSmith UI.

See **[docs/DEMO.md](docs/DEMO.md)** for the presenter runbook.

| Script | Step |
|---|---|
| `evals/00_reset_demo.py` | Delete everything the demo created in LangSmith, to start over |
| `evals/01_create_golden_dataset.py` | 1. Five hand-written `question` → `answer` examples |
| `evals/02_run_experiment.py [--dataset NAME]` | 2 and 4. Run the agent over a dataset; UI-bound evaluators score it |
| `evals/03_generate_traffic.py` | 3. One-shot requests sent to the "deployed" agent's prod project |
