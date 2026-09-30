"""Stage 3 - "Production" traffic: LLM-simulated users hold multi-turn conversations with the deployed prompt.

Each agent turn is its own root trace in the prod project, grouped into threads by `thread_id`, exactly like real
traffic, so online evaluators, thread views, and automation rules see what they would in production. The simulated
user's own LLM calls are not traced.
"""

import argparse
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from itertools import cycle, islice
from typing import Any, cast

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.utils.uuid import uuid7
from langgraph.checkpoint.memory import InMemorySaver
from langsmith import tracing_context
from openevals.simulators import create_llm_simulated_user

from travel_planner.agent import build_agent
from travel_planner.evals.settings import PROD_PROJECT
from travel_planner.prompts import COORDINATOR_PROMPTS

DONE = "DONE"
USER_RULES = f"""Reply in one or two short sentences like a real person typing in a chat app.
Answer the assistant's questions using the facts above; if it asks something not covered, make up a plausible answer.
When your trip is booked, or you have decided not to continue, reply with exactly {DONE}."""


@dataclass
class Persona:
    name: str
    opening: str
    facts: str


PERSONAS = [
    Persona(
        "decisive-booker",
        "Plan a 4-day trip from SFO to Tokyo, 2026-11-10 to 2026-11-14, just me. Mid-range budget.",
        "You are Priya Shah. You love food and museums. You want to compare options before booking anything.",
    ),
    Persona(
        "vague-planner",
        "I want a getaway somewhere in Europe in November.",
        "You are Sam Lee flying from Chicago (ORD) with your partner, 2026-11-12 to 2026-11-16, about $3,000 total. "
        "You are open to Paris or Rome.",
    ),
    Persona(
        "budget-traveler",
        "Cheapest reasonable trip SEA to Paris, 2026-11-05 to 2026-11-09, one person.",
        "You are Jordan Kim. Your hotel budget is strictly under $200 per night. You only book after seeing prices.",
    ),
    Persona(
        "fixed-dates",
        "Book me a trip SFO to London 2026-12-07 to 2026-12-11.",
        "You are Alex Rivera. Your dates are fixed and you get annoyed if asked to confirm or change them. You "
        "prefer nonstop flights and a central hotel.",
    ),
    Persona(
        "changes-mind",
        "Find me flights and a hotel JFK to Rome, 2026-11-18 to 2026-11-23, 2 travelers.",
        "You are Morgan Diaz. Halfway through you decide you only want the hotel, not flights. You do not want "
        "anything booked that you didn't explicitly pick.",
    ),
    Persona(
        "activities-only",
        "I'm already staying in Shinjuku, Tokyo 2026-11-10 to 2026-11-13. What should I do each day?",
        "You are Casey Nguyen. You like food, nightlife, and shopping. You already have flights and a hotel.",
    ),
]


def simulate(agent, persona: Persona, user_model, max_turns: int) -> str:
    thread_id = str(uuid7())
    config = {"configurable": {"thread_id": thread_id}, "metadata": {"persona": persona.name}}
    user = create_llm_simulated_user(
        system=f"{persona.facts}\n\n{USER_RULES}", client=user_model, fixed_responses=[persona.opening]
    )

    transcript: list[Any] = []
    for turn in range(max_turns):
        with tracing_context(enabled=False):
            message = cast(dict, user(transcript, turn_counter=turn))
        if message["content"].strip() == DONE:
            break
        transcript.append(message)
        agent.invoke({"messages": [{"role": "user", "content": message["content"]}]}, config)
        transcript.append({"role": "assistant", "content": agent.get_state(config).values["messages"][-1].text})
    return f"{persona.name}: {len(transcript) // 2} turns (thread {thread_id})"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", choices=COORDINATOR_PROMPTS, default="v1", help="The version 'in production'")
    parser.add_argument("--n", type=int, default=len(PERSONAS), help="Number of conversations")
    parser.add_argument("--max-turns", type=int, default=4)
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args()

    load_dotenv(override=True)
    os.environ["LANGSMITH_PROJECT"] = PROD_PROJECT

    agent = build_agent(checkpointer=InMemorySaver(), version=args.prompt)
    user_model = init_chat_model(os.environ.get("SIMULATED_USER_MODEL", "anthropic:claude-haiku-4-5-20251001"))

    personas = list(islice(cycle(PERSONAS), args.n))
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        for summary in pool.map(lambda p: simulate(agent, p, user_model, args.max_turns), personas):
            print(summary)
    print(f"\nTraces are in the {PROD_PROJECT!r} project (Threads tab groups each conversation).")


if __name__ == "__main__":
    main()
