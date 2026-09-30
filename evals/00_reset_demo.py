"""Reset: delete everything the lifecycle demo created in LangSmith so the runbook can start from a clean slate.

Removes the golden dataset and its experiments, the online evaluators and automation rules on the prod project
(including LLM judges added in the UI), the prod project and its traces, and the annotation queue.
`--include-dev-project` also deletes the dev tracing project used by `main.py` and `langgraph dev`.

Feedback configs (`plan_quality`, `booking_safety`, `correction`) are workspace-wide and are kept; stage 4
reuses them.
"""

import argparse
import asyncio
import os

from dotenv import load_dotenv
from langsmith import Client

from travel_planner.evals.settings import DATASET_NAME, PROD_PROJECT, QUEUE_NAME


def project_rules(client: Client, project_id: str) -> list[dict]:
    return client.request_with_retries("GET", "/runs/rules", params={"session_id": project_id}).json()


def delete_rules(client: Client, rules: list[dict]) -> None:
    async def delete_evaluators(evaluator_ids: set[str]) -> None:
        for evaluator_id in evaluator_ids:
            await client.evaluators.delete(evaluator_id, delete_run_rules=True)

    evaluator_ids = {rule["evaluator_id"] for rule in rules if rule.get("evaluator_id")}
    asyncio.run(delete_evaluators(evaluator_ids))
    for rule in rules:
        if not rule.get("evaluator_id"):
            client.request_with_retries("DELETE", f"/runs/rules/{rule['id']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    parser.add_argument("--include-dev-project", action="store_true", help="Also delete the dev tracing project")
    args = parser.parse_args()

    load_dotenv(override=True)
    client = Client()

    dataset = client.read_dataset(dataset_name=DATASET_NAME) if client.has_dataset(dataset_name=DATASET_NAME) else None
    experiments = list(client.list_projects(reference_dataset_id=dataset.id)) if dataset else []
    prod = next(iter(client.list_projects(name=PROD_PROJECT)), None)
    rules = project_rules(client, str(prod.id)) if prod else []
    queue = next(iter(client.list_annotation_queues(name=QUEUE_NAME)), None)
    dev_name = os.environ.get("LANGSMITH_PROJECT", "deepagent-travel-planner")
    dev = next(iter(client.list_projects(name=dev_name)), None) if args.include_dev_project else None

    plan = [
        *(f"experiment   {e.name}" for e in experiments),
        *([f"dataset      {DATASET_NAME}"] if dataset else []),
        *(f"rule         {r['display_name']}" for r in rules),
        *([f"project      {PROD_PROJECT} (and its traces)"] if prod else []),
        *([f"queue        {QUEUE_NAME}"] if queue else []),
        *([f"project      {dev_name} (and its traces)"] if dev else []),
    ]
    if not plan:
        print("Nothing to reset.")
        return

    print("This permanently deletes from LangSmith:\n  " + "\n  ".join(plan))
    if not args.yes and input("\nProceed? [y/N] ").strip().lower() != "y":
        print("Aborted.")
        return

    for experiment in experiments:
        client.delete_project(project_id=str(experiment.id))
    if dataset:
        client.delete_dataset(dataset_id=dataset.id)
    delete_rules(client, rules)
    if prod:
        client.delete_project(project_id=str(prod.id))
    if queue:
        client.delete_annotation_queue(queue.id)
    if dev:
        client.delete_project(project_id=str(dev.id))
    print(f"Deleted {len(plan)} resources. Start again with evals/01_create_golden_dataset.py.")


if __name__ == "__main__":
    main()
