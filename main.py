import json

from dotenv import load_dotenv
from langchain_core.utils.uuid import uuid7
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

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


def run_until_interrupt(agent, payload, config) -> list:
    for chunk in agent.stream(payload, config=config, stream_mode="updates", subgraphs=True, version="v2"):
        print_progress(chunk)
    return list(agent.get_state(config).interrupts)


def ask_decision(action: dict, allowed: list[str]) -> dict:
    print(f"\n  Approval needed: {action['name']}")
    print("  " + json.dumps(action["args"], indent=2).replace("\n", "\n  "))
    options = "/".join(f"[{d[0]}]{d[1:]}" for d in allowed)
    while True:
        choice = input(f"  {options}? ").strip().lower()[:1]
        if choice == "a" and "approve" in allowed:
            return {"type": "approve"}
        if choice == "r" and "reject" in allowed:
            reason = input("  Reason: ").strip() or "User declined."
            return {"type": "reject", "message": f"Booking not made: {reason}"}
        if choice == "e" and "edit" in allowed:
            try:
                args = json.loads(input("  New args as JSON: "))
            except json.JSONDecodeError as e:
                print(f"  Invalid JSON: {e}")
                continue
            return {"type": "edit", "edited_action": {"name": action["name"], "args": args}}


def resolve_interrupts(interrupts: list) -> dict:
    """Build a resume map keyed by interrupt id, so parallel subagent interrupts resume together."""
    resume = {}
    for pending in interrupts:
        requests = pending.value["action_requests"]
        allowed_by_tool = {cfg["action_name"]: cfg["allowed_decisions"] for cfg in pending.value["review_configs"]}
        decisions = [ask_decision(req, allowed_by_tool[req["name"]]) for req in requests]
        resume[pending.id] = {"decisions": decisions}
    return resume


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
    load_dotenv(override=True)
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

        interrupts = run_until_interrupt(agent, {"messages": [{"role": "user", "content": user_input}]}, config)
        while interrupts:
            interrupts = run_until_interrupt(agent, Command(resume=resolve_interrupts(interrupts)), config)
        print_last_reply(agent, config)


if __name__ == "__main__":
    main()
