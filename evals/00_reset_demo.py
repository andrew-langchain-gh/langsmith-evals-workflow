"""Reset: delete everything the demo created in LangSmith so the runbook can start from a clean slate.

Removes the golden and trajectory datasets with their experiments and bound evaluators, the online evaluators and
automation rules on the prod project (including those added in the UI), the prod project and its traces, and the
annotation queue. `--include-dev-project` also deletes the dev tracing project used by `main.py` and `langgraph dev`.
"""

import argparse
from pathlib import Path
import asyncio
import os

from dotenv import load_dotenv
from langsmith import Client

from travel_planner.evals.settings import DATASET_NAME, PROD_PROJECT, QUEUE_NAME, TRAJECTORY_DATASET_NAME


def rules_for(client: Client, **params: str) -> list[dict]:
    return client.request_with_retries("GET", "/runs/rules", params=params).json()


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
    parser.add_argument("--project-id", help="Tracing project to reset instead of the legacy project name")
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    client = Client()

    datasets = [
        client.read_dataset(dataset_name=name)
        for name in (DATASET_NAME, TRAJECTORY_DATASET_NAME)
        if client.has_dataset(dataset_name=name)
    ]
    experiments = [e for d in datasets for e in client.list_projects(reference_dataset_id=d.id)]
    prod = (client.read_project(project_id=args.project_id) if args.project_id
            else next(iter(client.list_projects(name=PROD_PROJECT)), None))
    rules = [r for d in datasets for r in rules_for(client, dataset_id=str(d.id))]
    rules += rules_for(client, session_id=str(prod.id)) if prod else []
    queue = next(iter(client.list_annotation_queues(name=QUEUE_NAME)), None)
    dev_name = os.environ.get("LANGSMITH_PROJECT", "deepagent-travel-planner")
    dev = next(iter(client.list_projects(name=dev_name)), None) if args.include_dev_project else None

    if prod and dev and prod.id == dev.id:
        dev = None  # Never delete the same project twice.

    plan = [
        *(f"experiment   {e.name}" for e in experiments),
        *(f"dataset      {d.name}" for d in datasets),
        *(f"rule         {r['display_name']}" for r in rules),
        *([f"project      {prod.name} (and its traces)"] if prod else []),
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
    delete_rules(client, rules)
    for dataset in datasets:
        client.delete_dataset(dataset_id=dataset.id)
    if prod:
        client.delete_project(project_id=str(prod.id))
    if queue:
        client.delete_annotation_queue(queue.id)
    if dev:
        client.delete_project(project_id=str(dev.id))
    print(f"Deleted {len(plan)} resources. Start again with evals/01_create_golden_dataset.py.")


if __name__ == "__main__":
    main()
