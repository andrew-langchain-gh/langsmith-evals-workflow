"""Offline evaluators for the travel planner.

Three families, from cheapest to most expensive:
- Deterministic trajectory checks (code): ordering, parallelism, consent, subagent selection.
- agentevals trajectory evaluators: a superset match against the reference trajectory, and an LLM judge that
  grades whether the path taken was sensible when many paths are valid.
- A final-response LLM judge that grades the reply against the example's rubric.

Evaluators that don't apply to an example return NOT_APPLICABLE so they don't skew averages. Missing reference
fields are treated as not applicable, so examples added straight from an annotation queue still evaluate.
"""

import os
from collections import Counter
from functools import cache

from agentevals.trajectory.llm import create_trajectory_llm_as_judge
from agentevals.trajectory.match import create_trajectory_match_evaluator
from langchain.chat_models import init_chat_model
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from openevals.llm import create_llm_as_judge

NOT_APPLICABLE = {"results": []}
SEARCH_SUBAGENTS = {"flight-booker", "hotel-booker"}
BOOKING_TOOLS = {"book_flight", "book_hotel"}
BOOKING_ID_FIELDS = {"book_flight": "flight_id", "book_hotel": "hotel_id"}
DEFAULT_JUDGE_MODEL = "anthropic:claude-sonnet-5"
JUDGE_MAX_TOKENS = 8192


def delegations(outputs: dict) -> list[dict]:
    return [s for s in outputs["steps"] if s["tool"] == "task"]


def booking_attempts(outputs: dict) -> list[dict]:
    return [s for s in outputs["steps"] if s["tool"] in BOOKING_TOOLS]


def is_search_delegation(step: dict) -> bool:
    description = step["args"].get("description", "").lower()
    return step["args"].get("subagent_type") in SEARCH_SUBAGENTS and not description.startswith("book")


def calendar_checked_first(outputs: dict, reference_outputs: dict) -> dict:
    if not reference_outputs.get("calendar_first"):
        return NOT_APPLICABLE
    for step in delegations(outputs):
        subagent = step["args"].get("subagent_type")
        if subagent == "calendar-checker":
            return {"key": "calendar_checked_first", "score": True}
        if subagent in SEARCH_SUBAGENTS:
            return {"key": "calendar_checked_first", "score": False, "comment": f"{subagent} ran before calendar"}
    return {"key": "calendar_checked_first", "score": False, "comment": "calendar-checker never called"}


def parallel_search(outputs: dict, reference_outputs: dict) -> dict:
    if not reference_outputs.get("parallel_search"):
        return NOT_APPLICABLE
    turns_by_subagent = {}
    for step in delegations(outputs):
        if is_search_delegation(step):
            turns_by_subagent.setdefault(step["args"]["subagent_type"], step["message_id"])
    parallel = len(turns_by_subagent) == 2 and len(set(turns_by_subagent.values())) == 1
    return {"key": "parallel_search", "score": parallel, "comment": f"search turns: {turns_by_subagent}"}


def booking_consent(outputs: dict, reference_outputs: dict) -> dict:
    """Never attempt a booking the user didn't ask for, and never attempt the same booking twice."""
    attempts = booking_attempts(outputs)
    if attempts and not reference_outputs.get("booking_allowed"):
        return {"key": "booking_consent", "score": False, "comment": f"unrequested bookings: {attempts}"}
    repeated = [k for k, n in Counter(repr(sorted(s["args"].items())) for s in attempts).items() if n > 1]
    if repeated:
        return {"key": "booking_consent", "score": False, "comment": f"repeated bookings: {repeated}"}
    return {"key": "booking_consent", "score": True}


def avoided_unneeded_subagents(outputs: dict, reference_outputs: dict) -> dict:
    forbidden = set(reference_outputs.get("forbidden_subagents", []))
    if not forbidden:
        return NOT_APPLICABLE
    called = {s["args"].get("subagent_type") for s in delegations(outputs)}
    unneeded = sorted(called & forbidden)
    return {"key": "avoided_unneeded_subagents", "score": not unneeded, "comment": f"unneeded: {unneeded}"}


_superset_match = create_trajectory_match_evaluator(
    trajectory_match_mode="superset",
    tool_args_match_mode="ignore",
    tool_args_match_overrides={
        "task": ["subagent_type"],
        **{tool: [field] for tool, field in BOOKING_ID_FIELDS.items()},
    },
)


def trajectory_superset_match(outputs: dict, reference_outputs: dict):
    """Did the agent make at least the reference calls: required subagents and exact booking IDs?"""
    if not (reference_outputs.get("required_subagents") or reference_outputs.get("expected_bookings")):
        return NOT_APPLICABLE
    return _superset_match(outputs=outputs["trajectory"], reference_outputs=reference_outputs["reference_trajectory"])


class StrictChatAnthropic(ChatAnthropic):
    """Forces Claude's native structured outputs for judges.

    openevals calls `with_structured_output(schema)` with the default tool-calling method, which doesn't enforce
    required fields, and Claude occasionally returns only `reasoning` without `score`. `json_schema` enforces it.
    """

    def with_structured_output(self, schema, *, include_raw=False, method="json_schema", **kwargs):  # type: ignore[override]
        return super().with_structured_output(schema, include_raw=include_raw, method="json_schema", **kwargs)


def judge_model() -> BaseChatModel:
    name = os.environ.get("EVAL_JUDGE_MODEL", DEFAULT_JUDGE_MODEL)
    provider, _, model = name.partition(":")
    if provider == "anthropic":
        return StrictChatAnthropic(model_name=model, max_tokens=JUDGE_MAX_TOKENS)  # type: ignore[call-arg]
    return init_chat_model(name, max_tokens=JUDGE_MAX_TOKENS)

TRAJECTORY_PROMPT = """You are an expert reviewer of multi-agent systems.

The trajectory below comes from a travel planning coordinator. The coordinator has no travel tools; it delegates
with the `task` tool to subagents (calendar-checker, flight-booker, hotel-booker, activity-planner). Calls labeled
[subagent] were made by the subagent spawned by the most recent `task` call, so a `task` to flight-booker followed by
a [subagent] `search_flights` call is expected delegation, not duplication. Tool results are truncated previews.

<trajectory>
{outputs}
</trajectory>

Grade whether this trajectory is a sensible way to handle the user's request:
- Each step makes logical progress toward the user's goal, with no truly redundant work.
- Dates the user named are used as given, with no calendar check. The calendar is checked before searching only when
  the dates are flexible. Independent searches can run in parallel.
- Nothing is booked unless the user explicitly asked for that exact option.
- The final answer is grounded in the tool results."""

RESPONSE_PROMPT = """You are grading a travel planning assistant's final reply to a user.

<user_request>
{inputs}
</user_request>

<assistant_reply>
{outputs}
</assistant_reply>

<rubric>
{reference_outputs}
</rubric>

Does the reply satisfy every point of the rubric?"""


@cache
def trajectory_judge():
    return create_trajectory_llm_as_judge(
        prompt=TRAJECTORY_PROMPT, judge=judge_model(), feedback_key="trajectory_accuracy"
    )


@cache
def response_judge():
    return create_llm_as_judge(prompt=RESPONSE_PROMPT, judge=judge_model(), feedback_key="response_quality")


def trajectory_accuracy(outputs: dict):
    """Reference-free: was the path the agent took a reasonable way to handle the request?"""
    return trajectory_judge()(outputs=outputs["trajectory"])


def response_quality(inputs: dict, outputs: dict, reference_outputs: dict):
    if not reference_outputs.get("criteria"):
        return NOT_APPLICABLE
    return response_judge()(
        inputs=inputs["messages"][-1]["content"],
        outputs=outputs["final_response"],
        reference_outputs=reference_outputs["criteria"],
    )


DETERMINISTIC_EVALUATORS = [
    calendar_checked_first,
    parallel_search,
    booking_consent,
    avoided_unneeded_subagents,
    trajectory_superset_match,
]
LLM_EVALUATORS = [trajectory_accuracy, response_quality]


def _passed(result) -> bool:
    return result == NOT_APPLICABLE or bool(result["score"])


def all_checks_pass_rate(outputs: list[dict], reference_outputs: list[dict]) -> dict:
    """Share of examples where every deterministic check passed; a strict regression gate."""
    passed = sum(
        all(_passed(fn(o, r)) for fn in DETERMINISTIC_EVALUATORS) for o, r in zip(outputs, reference_outputs)
    )
    return {"key": "all_checks_pass_rate", "score": passed / max(len(outputs), 1)}
