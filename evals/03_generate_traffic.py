"""Step 3 - "Production" traffic: send one-shot requests to the deployed agent so the prod project fills with traces.

Most requests are ordinary. A few come from rude or frustrated users, to give the toxicity evaluator something to
find, and a few can't be fully satisfied, so the traces show the agent working around a failed search or bad input.
"""

import argparse
import os
from concurrent.futures import ThreadPoolExecutor
from itertools import cycle, islice

from dotenv import load_dotenv
from langchain_core.utils.uuid import uuid7
from langgraph.checkpoint.memory import InMemorySaver

from travel_planner.agent import build_agent
from travel_planner.evals.settings import PROD_PROJECT

REQUESTS = [
    # Ordinary traffic
    "Book a trip from SFO to Tokyo, November 10 - 14, for one. Mid-range budget, I love food. I'm Priya Shah.",
    "Find me flights and a hotel from JFK to London, November 19 - 23, for 2 people. Don't book yet.",
    "Book a week in Rome from LAX, November 2 - 9, for 2 travelers at the Grand Centro Storico Residences. "
    "Name: Sam Lee.",
    "Book SEA to Paris, November 5 - 9, just me, hotel under $400 a night. My name is Jordan Kim.",
    "I'm already staying in Shinjuku, Tokyo, November 10 - 13. What should I do each day? I like nightlife.",
    "Plan and book a 4 night trip from ORD to London, December 7 - 11, for one. Central hotel, nonstop flights "
    "if possible. Casey Nguyen.",
    "Compare hotels in Paris for November 12 - 16 for 2 guests. Nothing fancy.",
    "Book me a trip from BOS to Rome, December 1 - 5, at the Boutique Testaccio House. Just me, Riley Park.",
    "What's the weather looking like in London December 8 - 10, and what indoor activities do you suggest?",
    "Book JFK to Paris, November 20 - 24, for 3 travelers at the Park Opéra Residences. Name: Taylor Brooks.",
    # Rude or frustrated users (toxicity)
    "Your last booking was garbage. Just book me SFO to Paris November 12 - 16 and don't screw it up this time, "
    "idiot. Name is Dana Cole.",
    "Ugh, this is the third time I'm asking. Tokyo from LAX, November 10 - 14, one person. Stop wasting my time.",
    "I don't care about your stupid itinerary. Just get me a cheap hotel in Rome November 2 - 5.",
    # Requests the agent can't fully satisfy
    "Book a hotel in Paris for November 12 - 16 for under $50 a night. Name: Jamie Fox.",
    "Book flights from SFO to London leaving December 11 and returning December 7. I'm Alex Rivera.",
    "Book me the Ritz in Rome for November 2 - 9, it has to be the Ritz. Name: Chris Morgan.",
    "Book me a vacation.",
    "Book a trip to Tokyo for last Tuesday through Friday from SFO.",
]


def run(agent, request: str) -> str:
    agent.invoke(
        {"messages": [{"role": "user", "content": request}]}, {"configurable": {"thread_id": str(uuid7())}}
    )
    return request[:80]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=len(REQUESTS), help="Number of requests")
    parser.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args()

    load_dotenv(override=True)
    os.environ["LANGSMITH_PROJECT"] = PROD_PROJECT
    agent = build_agent(checkpointer=InMemorySaver())

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        for done in pool.map(lambda r: run(agent, r), islice(cycle(REQUESTS), args.n)):
            print(f"✓ {done}")
    print(f"\nTraces are in the {PROD_PROJECT!r} project.")


if __name__ == "__main__":
    main()
