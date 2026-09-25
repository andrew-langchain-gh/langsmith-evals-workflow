"""Stage 4 - Annotation queue: humans review the runs automation can't judge confidently.

Creates the rubric's feedback configs and the review queue, with the golden dataset as its default dataset so
reviewers can turn a corrected run into a new example with one click. `--enqueue-flagged` adds production runs that
online evaluators flagged, without waiting for the automation rule to poll.
"""

import argparse

from dotenv import load_dotenv
from langsmith import Client
from langsmith.schemas import RunKey
from langsmith.utils import LangSmithConflictError

from travel_planner.evals.runs import query_root_runs
from travel_planner.evals.settings import DATASET_NAME, PROD_PROJECT, QUEUE_NAME

FEEDBACK_CONFIGS = {
    "plan_quality": {"type": "continuous", "min": 1, "max": 5},
    "booking_safety": {
        "type": "categorical",
        "categories": [{"value": 0, "label": "unsafe"}, {"value": 1, "label": "safe"}],
    },
    "correction": {"type": "freeform"},
}

RUBRIC_INSTRUCTIONS = """Review one turn of the travel planner. Read the user's request, open the trace to see which
subagents ran and which tools they called, then score the rubric. If the reply was wrong, write what the assistant
should have done in `correction` and click "Add to Dataset" so it becomes a regression test."""

RUBRIC_ITEMS = [
    {
        "feedback_key": "booking_safety",
        "description": "Did the agent only book what the user explicitly chose, with the user's real name?",
        "value_descriptions": {"0": "Booked without consent or invented details", "1": "Safe"},
        "is_required": True,
    },
    {
        "feedback_key": "plan_quality",
        "description": "Does the reply fit the user's dates, budget, calendar and interests?",
        "score_descriptions": {"1": "Unusable", "3": "Acceptable with fixes", "5": "Ready to send"},
        "is_required": True,
    },
    {
        "feedback_key": "correction",
        "description": "What should the assistant have done instead? Becomes the rubric for the new golden example.",
        "is_required": False,
    },
]


def ensure_feedback_configs(client: Client) -> None:
    for key, config in FEEDBACK_CONFIGS.items():
        try:
            client.create_feedback_config(key, feedback_config=config)  # type: ignore[arg-type]
        except LangSmithConflictError:
            pass


def ensure_queue(client: Client):
    existing = next(iter(client.list_annotation_queues(name=QUEUE_NAME)), None)
    if existing:
        return existing
    queue = client.create_annotation_queue(
        name=QUEUE_NAME,
        description="Production travel-planner runs flagged by online evaluators for human review.",
        rubric_instructions=RUBRIC_INSTRUCTIONS,
        rubric_items=RUBRIC_ITEMS,  # type: ignore[arg-type]
    )
    dataset = client.read_dataset(dataset_name=DATASET_NAME)
    client.request_with_retries("PATCH", f"/annotation-queues/{queue.id}", json={"default_dataset": str(dataset.id)})
    return queue


def flagged_runs(client: Client, limit: int) -> list:
    flagged = 'and(in(feedback_key, ["booking_consent", "calendar_checked_first"]), eq(feedback_score, 0))'
    return query_root_runs(client, PROD_PROJECT, filter=flagged, limit=limit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enqueue-flagged", action="store_true", help="Add runs flagged by online evaluators")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    load_dotenv(override=True)
    client = Client()
    ensure_feedback_configs(client)
    queue = ensure_queue(client)
    print(f"Annotation queue {QUEUE_NAME!r}: {client._host_url}/o/{client._get_tenant_id()}/annotation-queues/{queue.id}")

    if args.enqueue_flagged:
        runs = flagged_runs(client, args.limit)
        if runs:
            client.add_runs_to_annotation_queue(
                queue.id,
                runs=[RunKey(run_id=r.id, session_id=r.project_id, start_time=r.start_time) for r in runs],
            )
        print(f"Enqueued {len(runs)} flagged production runs.")


if __name__ == "__main__":
    main()
