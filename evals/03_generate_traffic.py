"""Step 3 - Send one-shot requests to Agent Server with --url, or rehearse locally without it.

Most requests are ordinary. A few come from rude or frustrated users, to give the toxicity evaluator something to
find, and a few can't be fully satisfied, so the traces show the agent working around a failed search or bad input.
"""

import argparse
import os
import time
from concurrent.futures import ThreadPoolExecutor
from itertools import cycle, islice
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from langchain_core.utils.uuid import uuid7
from langgraph.checkpoint.memory import InMemorySaver
from langgraph_sdk import get_sync_client

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


def run_deployed(client, request: str) -> str:
    thread = client.threads.create()  # A fresh, persistent conversation per request.
    thread_id = thread["thread_id"]
    print(f"Thread: {thread_id}", flush=True)
    background_run = client.runs.create(
        thread_id,
        "travel_planner",  # Graph ID in langgraph.json.
        input={"messages": [{"role": "user", "content": request}]},
    )
    run_id = background_run["run_id"]
    print(f"Run: {run_id}", flush=True)

    # Short status requests avoid holding /runs/wait open through a gateway.
    deadline = time.monotonic() + 600
    while background_run["status"] in {"pending", "running"}:
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Stopped waiting for run {run_id} on thread {thread_id}; it may still be running.")
        time.sleep(2)
        background_run = client.runs.get(thread_id, run_id)

    if background_run["status"] != "success":
        raise RuntimeError(f"Run {run_id} on thread {thread_id} ended with status {background_run['status']}.")
    return request[:80]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", help="Agent Server deployment URL (omit for local rehearsal)")
    parser.add_argument("--n", type=int, default=len(REQUESTS), help="Number of requests")
    parser.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args()
    if args.n < 1 or args.concurrency < 1:
        parser.error("--n and --concurrency must be at least 1")

    # Preserve exported credentials when .env contains empty placeholders.
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    if args.url:
        api_key = next(
            (os.environ[name] for name in (
                "LANGGRAPH_API_KEY", "LANGSMITH_API_KEY", "LANGCHAIN_API_KEY", "LANGGRAPH_HOST_API_KEY"
            ) if os.environ.get(name)),
            None,
        )
        if not api_key and urlparse(args.url).hostname not in {"localhost", "127.0.0.1", "::1"}:
            parser.error("Set LANGSMITH_API_KEY in your shell or the project's .env before calling a hosted agent.")
        client = get_sync_client(url=args.url, api_key=api_key, timeout=30)

        def send_request(request):
            return run_deployed(client, request)

    else:
        project_name = os.environ.setdefault("LANGSMITH_PROJECT", PROD_PROJECT)
        os.environ["LANGSMITH_TRACING"] = "true"
        agent = build_agent(checkpointer=InMemorySaver())

        def send_request(request):
            return run(agent, request)

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        for done in pool.map(send_request, islice(cycle(REQUESTS), args.n)):
            print(f"✓ {done}")
    if args.url:
        print("\nRequests completed on Agent Server. Open the deployment's tracing project to review them.")
    else:
        print(f"\nLocal rehearsal traces are in the {project_name!r} project.")


if __name__ == "__main__":
    main()
