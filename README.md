# LangSmith Evals Workflow

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

For hosted deployment, see **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**. This Deep
Agent can deploy through the LangGraph CLI using the existing graph factory.
The guide covers CLI version differences, runtime credentials, online evaluators,
and traffic sent to the actual deployed endpoint.

Deploy from the project root with the LangGraph CLI:

```sh
uv run langgraph deploy --remote --name deepagent-travel-planner-prod-20261007
```

`--remote` builds in the cloud, so local Docker is not required. The command uses
`langgraph.json` and deployment credentials from `.env`; non-reserved environment
variables in that file are configured as hosted secrets.

The installed CLI (`0.4.32`) defaults to the legacy `dev` deployment type. If your
workspace rejects that type, use the LangSmith UI's **Serverless** deployment
option or update to a CLI version supporting the current deployment types.

Send a smoke-test request to the deployed agent:

```sh
uv run evals/03_generate_traffic.py \
  --url https://deepagent-travel-planner-pr-76c99bb254005eb2a4706a3d2dc1f40e.us.langgraph.app \
  --n 1 --concurrency 1
```

Use `--n 18 --concurrency 5` to generate all demo requests. These commands invoke
the hosted model and create traces in the deployment's linked tracing project.
The Python client needs `LANGSMITH_API_KEY` in your shell or `.env`; CLI-profile
authentication alone does not configure it. Requests run in the background and
the script polls their status, avoiding a long HTTP wait through the gateway.
The traffic script preserves exported shell variables when loading `.env`, so an
empty credential placeholder in that file does not override a configured key.

## Tests

```sh
uv run pytest
```

These tests cover the mock tools and make no LLM calls.

## Evaluation demo

`evals/` holds numbered scripts for a LangSmith evaluation walkthrough. They cover a hand-curated golden dataset, SDK assertion evaluators, simulated production traffic for online evaluators, and SDK trajectory evaluators on a dataset built from a reviewed trace. Online evaluators, rules, and the annotation queue are configured in the LangSmith UI.

See **[docs/DEMO.md](docs/DEMO.md)** for the presenter runbook.

For the same five-step workflow with runnable SDK cells and explanatory markdown,
open **[notebooks/agent_evaluations.ipynb](notebooks/agent_evaluations.ipynb)**.
Select the project's `.venv` interpreter and run each section in order; the
notebook's configuration cell holds the dataset IDs, trace ID, and deployment URL.

| Script | Step |
|---|---|
| `evals/00_reset_demo.py` | Delete everything the demo created in LangSmith, to start over |
| `evals/01_create_golden_dataset.py` | 1. Five hand-written `question` → `answer` examples |
| `evals/02_run_experiment.py` | 2. Run the golden questions; an SDK evaluator scores each assertion |
| `evals/03_generate_traffic.py [--url DEPLOYMENT_URL]` | 3. Send requests to Agent Server, or rehearse locally without `--url` |
| `evals/04_import_trajectory_example.py` | 4. Import a root run (`--run-id`) or project (`--project-id`) with original inputs and reference outputs |
| `evals/05_run_trajectory_experiment.py` | 5. Compare coordinator delegation with SDK strict/unordered matchers |

Run the SDK assertion demo with `uv run evals/02_run_experiment.py`. It passes an
evaluator directly to `Client.evaluate`, returning one score per assertion. An LLM
judge grades every answer criterion with the same logic. `--judge-model` and `--concurrency` configure the
judge and parallelism. This runs the agent and judge models and logs an experiment
to LangSmith; UI-bound evaluators, if present, also run.

## GitHub CI evaluation gate

[`.github/workflows/evaluate.yml`](.github/workflows/evaluate.yml) runs the golden
assertion evaluator on PRs to `main` and manual dispatches. Any failed or missing
assertion fails **Golden assertions**. Reports are uploaded even on failure and
posted as a PR comment. Failed runs enter `travel-planner-review` in LangSmith.

See [CI setup and presentation walkthrough](docs/CI.md).
