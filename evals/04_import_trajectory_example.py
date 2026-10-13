"""Step 4 - Import one root run or a project's traces as trajectory references."""

import argparse
from pathlib import Path

from dotenv import load_dotenv
from langsmith import Client

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--run-id", help="Reviewed root run ID")
    source.add_argument("--project-id", help="Import all completed, successful root traces in this project")
    parser.add_argument("--dataset", required=True, help="Destination dataset ID")
    args = parser.parse_args()

    client = Client()
    runs = (
        client.list_runs(project_id=args.project_id, is_root=True, error=False)
        if args.project_id
        else [client.read_run(args.run_id)]
    )
    imported = 0
    for run in runs:
        if args.project_id and (not run.end_time or not run.outputs):
            print(f"Skipping unfinished trace: {run.id}")
            continue
        example = client.create_example(
            dataset_id=args.dataset,
            inputs=run.inputs,
            outputs=run.outputs,
            source_run_id=run.id,
        )
        imported += 1
        print(f"Created example: {example.id} (source run: {run.id})")
    print(f"Imported {imported} examples")
    print(f"Dataset: {args.dataset}")


if __name__ == "__main__":
    main()
