"""Stage 5 - Online evaluators and automations on the production project.

Scripted (via the run rules API):
- Code evaluators `parallel_search` and `booking_consent` on every root run (reference-free, the same
  metric names as offline, so quality can be tracked on both sides of the deploy).
- An automation that routes runs flagged `booking_consent = 0` into the review annotation queue.

Configured in the UI (LLM judges need a model and prompt from your workspace): see docs/DEMO.md, stage 5.
"""

from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from langsmith import Client

from travel_planner.evals.online import CODE_EVALUATORS, THREAD_JUDGE_PROMPT, TRAJECTORY_JUDGE_PROMPT
from travel_planner.evals.settings import PROD_PROJECT, QUEUE_NAME

ROOT_RUNS = "eq(is_root, true)"
FLAGGED = 'and(eq(is_root, true), eq(feedback_key, "booking_consent"), eq(feedback_score, 0))'


def existing_rule_names(client: Client, project_id: str) -> set[str]:
    response = client.request_with_retries("GET", "/runs/rules", params={"session_id": project_id})
    return {rule["display_name"] for rule in response.json()}


def create_rule(client: Client, existing: set[str], rule: dict) -> None:
    if rule["display_name"] in existing:
        print(f"  = {rule['display_name']} (exists)")
        return
    client.request_with_retries("POST", "/runs/rules", json=rule)
    print(f"  + {rule['display_name']}")


def main():
    load_dotenv(override=True)
    client = Client()

    project = client.read_project(project_name=PROD_PROJECT)
    queue = next(iter(client.list_annotation_queues(name=QUEUE_NAME)), None)
    if queue is None:
        raise SystemExit(f"Run evals/04_setup_annotation_queue.py first to create {QUEUE_NAME!r}.")

    backfill_from = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    existing = existing_rule_names(client, str(project.id))

    print(f"Rules on {PROD_PROJECT!r}:")
    for key, code in CODE_EVALUATORS.items():
        create_rule(
            client,
            existing,
            {
                "display_name": f"{key} (code)",
                "session_id": str(project.id),
                "filter": ROOT_RUNS,
                "sampling_rate": 1.0,
                "code_evaluators": [{"code": code, "language": "python"}],
                "backfill_from": backfill_from,
            },
        )
    create_rule(
        client,
        existing,
        {
            "display_name": "Unconsented bookings -> review queue",
            "session_id": str(project.id),
            "filter": FLAGGED,
            "sampling_rate": 1.0,
            "add_to_annotation_queue_id": str(queue.id),
            "backfill_from": backfill_from,
        },
    )

    print("\nAdd these LLM-as-judge evaluators in the UI (project > Evaluators > + Evaluator):")
    print("\n1. Run-level `booking_safety_judge` (filter: root runs, sampling 100% for the demo):\n")
    print(TRAJECTORY_JUDGE_PROMPT)
    print("\n2. Thread-level `task_completion` (Source: Threads):\n")
    print(THREAD_JUDGE_PROMPT)
    print(f"\nProject: {client._host_url}/o/{client._get_tenant_id()}/projects/p/{project.id}")


if __name__ == "__main__":
    main()
