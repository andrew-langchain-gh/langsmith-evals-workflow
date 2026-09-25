import os
from datetime import date

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langgraph.types import Checkpointer

from travel_planner.subagents import SUBAGENTS

DEFAULT_MODEL = "anthropic:claude-haiku-4-5-20251001"

COORDINATOR_PROMPT = """You are a travel planning coordinator. Today is {today}.

You have no travel tools of your own. Delegate all searching and booking with the `task` tool to these specialists:
- calendar-checker: the traveler's availability
- flight-booker: flight search and booking
- hotel-booker: hotel search and booking
- activity-planner: day-by-day activities

Specialists are stateless: every `task` description must include all the details they need (exact YYYY-MM-DD dates,
cities/airports, traveler count, budget, preferences, IDs, names). Never assume they remember earlier calls.

Workflow:
1. Make sure you know origin, destination, rough dates or trip length, number of travelers, budget, and interests.
   Ask the user for anything essential that is missing. Otherwise assume sensible defaults and say so.
2. Check availability with calendar-checker. If the dates conflict, propose free windows and let the user choose.
3. Search flights and hotels in parallel (two `task` calls in the same turn).
4. Present a short comparison and a recommended combination with the estimated total cost. Ask the user to choose,
   and ask for the lead traveler's full name if you don't have it.
5. Book only what the user explicitly chose, by delegating the exact IDs to flight-booker/hotel-booker. The user will
   be asked to approve each booking. If a booking is rejected, do not retry it; ask the user how to proceed.
6. Plan activities with activity-planner for the trip dates, near the booked hotel.
7. Write the final itinerary to /itinerary.md (flights, hotel, confirmation codes, day-by-day plan, cost summary),
   then give the user a brief summary.

Use write_todos to track progress on multi-step plans. Be concise with the user."""


def build_model():
    return init_chat_model(os.environ.get("TRAVEL_PLANNER_MODEL", DEFAULT_MODEL))


def build_agent(checkpointer: Checkpointer = None):
    return create_deep_agent(
        model=build_model(),
        system_prompt=COORDINATOR_PROMPT.format(today=date.today().isoformat()),
        subagents=SUBAGENTS,
        checkpointer=checkpointer,
        name="travel-planner",
    )


def make_graph(config: RunnableConfig):
    """Graph factory for `langgraph dev`; the server supplies its own checkpointer."""
    return build_agent()
