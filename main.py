from pathlib import Path
from dotenv import load_dotenv
from langchain_core.utils.uuid import uuid7
from langgraph.checkpoint.memory import InMemorySaver

from travel_planner.agent import build_agent

ITINERARY_PATH = "/itinerary.md"


def print_progress(chunk: dict) -> None:
    if chunk["type"] != "updates":
        return
    in_subagent = bool(chunk["ns"])
    for update in chunk["data"].values():
        if not isinstance(update, dict):
            continue
        for message in update.get("messages", []):
            for call in getattr(message, "tool_calls", None) or []:
                if call["name"] == "task":
                    description = call["args"].get("description", "").splitlines()[0][:100]
                    print(f"  → {call['args'].get('subagent_type')}: {description}")
                elif in_subagent:
                    print(f"      · {call['name']}")


def print_last_reply(agent, config) -> None:
    messages = agent.get_state(config).values.get("messages", [])
    if messages:
        print(f"\nPlanner: {messages[-1].text}\n")


def print_itinerary(agent, config) -> None:
    files = agent.get_state(config).values.get("files", {})
    itinerary = files.get(ITINERARY_PATH)
    if not itinerary:
        print("No itinerary yet.\n")
        return
    print(itinerary["content"])


def main():
    load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
    agent = build_agent(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": str(uuid7())}}

    print("Travel planner (mock data). Commands: /itinerary, /quit\n")
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input:
            continue
        if user_input == "/quit":
            break
        if user_input == "/itinerary":
            print_itinerary(agent, config)
            continue

        payload = {"messages": [{"role": "user", "content": user_input}]}
        for chunk in agent.stream(payload, config=config, stream_mode="updates", subgraphs=True, version="v2"):
            print_progress(chunk)
        print_last_reply(agent, config)


if __name__ == "__main__":
    main()
