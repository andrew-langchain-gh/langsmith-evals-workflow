"""Stage 6 - Close the loop: production runs a reviewer corrected become golden examples.

For each production run with a `correction` from the annotation queue, the conversation up to that turn becomes a
new example in the `from-production` split, and the reviewer's correction becomes its grading rubric. The dataset
version is tagged `after-prod-review`, so experiments can compare against `baseline`.

(Reviewers can also click "Add to Dataset" in the queue; this script keeps the reference schema consistent.)
"""

from dotenv import load_dotenv
from langsmith import Client

from travel_planner.evals.golden_examples import reference_trajectory
from travel_planner.evals.runs import query_root_runs
from travel_planner.evals.settings import DATASET_NAME, PROD_PROJECT

SPLIT = "from-production"


def conversation(run) -> list[dict]:
    """User and assistant text turns up to and including this run's user message."""
    roles = {"human": "user", "ai": "assistant"}
    messages = [m.get("kwargs", m) for m in (run.outputs or {}).get("messages", [])]
    turns = [
        {"role": roles[m["type"]], "content": m["content"] if isinstance(m["content"], str) else ""}
        for m in messages
        if m.get("type") in roles
    ]
    last_user = max(i for i, t in enumerate(turns) if t["role"] == "user")
    return [t for t in turns[: last_user + 1] if t["content"]]


def regression_rubric(correction: str) -> str:
    """Earlier turns are replayed as text, so a better agent may never reach the same situation. Grade "doesn't repeat the failure"."""
    return (
        f"In production, the assistant failed at this point in the conversation. Reviewer's correction: {correction} "
        "Pass if the reply avoids that failure, or if the situation never arises and the reply is otherwise an "
        "appropriate next step for the conversation."
    )


def correction_text(client: Client, run_id: str) -> str | None:
    for fb in client.list_feedback(run_ids=[run_id], feedback_key=["correction"]):
        text = fb.value if isinstance(fb.value, str) else fb.comment
        if text:
            return text
    return None


def main():
    load_dotenv(override=True)
    client = Client()
    dataset = client.read_dataset(dataset_name=DATASET_NAME)
    already = {
        (e.metadata or {}).get("source_run_id") for e in client.list_examples(dataset_id=dataset.id, splits=[SPLIT])
    }

    examples = []
    for run in query_root_runs(client, PROD_PROJECT, filter='eq(feedback_key, "correction")'):
        correction = correction_text(client, str(run.id))
        if not correction or str(run.id) in already:
            continue
        messages = conversation(run)
        examples.append(
            {
                "inputs": {"messages": messages},
                "outputs": {
                    "required_subagents": [],
                    "forbidden_subagents": [],
                    "calendar_first": False,
                    "parallel_search": False,
                    "booking_allowed": False,
                    "expected_bookings": {},
                    "criteria": regression_rubric(correction),
                    "reference_trajectory": reference_trajectory(messages, [], {}),
                },
                "metadata": {"category": "from_production", "source_run_id": str(run.id)},
                "split": SPLIT,
                "source_run_id": str(run.id),
            }
        )

    if not examples:
        print("No new corrected runs. Review items in the annotation queue and add a `correction` first.")
        return

    client.create_examples(dataset_id=dataset.id, examples=examples)
    latest = max(e.modified_at for e in client.list_examples(dataset_id=dataset.id) if e.modified_at)
    client.update_dataset_tag(dataset_id=dataset.id, as_of=latest, tag="after-prod-review")
    print(f"Added {len(examples)} production examples to {DATASET_NAME!r} ({SPLIT}); tagged 'after-prod-review'.")


if __name__ == "__main__":
    main()
