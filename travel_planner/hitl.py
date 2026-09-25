"""Run the agent to completion, resolving booking approvals with a pluggable decision function."""

from collections.abc import Callable

from langgraph.types import Command

Decide = Callable[[dict, list[str]], dict]
OnChunk = Callable[[dict], None]

MAX_RESUMES = 10


def stream_until_interrupt(agent, payload, config, on_chunk: OnChunk | None = None) -> list:
    for chunk in agent.stream(payload, config=config, stream_mode="updates", subgraphs=True, version="v2"):
        if on_chunk:
            on_chunk(chunk)
    return list(agent.get_state(config).interrupts)


def resolve_interrupts(interrupts: list, decide: Decide) -> dict:
    """Build a resume map keyed by interrupt id, so parallel subagent interrupts resume together."""
    resume = {}
    for pending in interrupts:
        allowed_by_tool = {cfg["action_name"]: cfg["allowed_decisions"] for cfg in pending.value["review_configs"]}
        decisions = [decide(req, allowed_by_tool[req["name"]]) for req in pending.value["action_requests"]]
        resume[pending.id] = {"decisions": decisions}
    return resume


def run_turn(agent, payload, config, decide: Decide, on_chunk: OnChunk | None = None) -> None:
    interrupts = stream_until_interrupt(agent, payload, config, on_chunk)
    for _ in range(MAX_RESUMES):
        if not interrupts:
            return
        interrupts = stream_until_interrupt(agent, Command(resume=resolve_interrupts(interrupts, decide)), config, on_chunk)
    raise RuntimeError(f"Still interrupted after {MAX_RESUMES} resumes")
