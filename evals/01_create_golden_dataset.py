"""Stage 1 - Golden dataset: hand-written examples with reference outputs, created once the prototype works.

Splits: `core` (the behaviors that must never regress) and `edge` (tricky cases). The version is tagged
`baseline` so later experiments can pin to it even after production cases are added.
"""

import argparse

from dotenv import load_dotenv
from langsmith import Client

from travel_planner.evals.golden_examples import build_examples
from travel_planner.evals.settings import DATASET_NAME


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recreate", action="store_true", help="Delete and recreate the dataset")
    args = parser.parse_args()

    load_dotenv(override=True)
    client = Client()

    if client.has_dataset(dataset_name=DATASET_NAME):
        if not args.recreate:
            print(f"Dataset {DATASET_NAME!r} already exists; pass --recreate to rebuild it.")
            return
        client.delete_dataset(dataset_name=DATASET_NAME)

    dataset = client.create_dataset(
        DATASET_NAME,
        description="Golden examples for the deep agent travel planner: expected subagent trajectories, "
        "booking consent, and response rubrics.",
    )
    examples = build_examples()
    client.create_examples(dataset_id=dataset.id, examples=examples)

    latest = max(e.modified_at for e in client.list_examples(dataset_id=dataset.id) if e.modified_at)
    client.update_dataset_tag(dataset_id=dataset.id, as_of=latest, tag="baseline")

    print(f"Created {len(examples)} examples in {DATASET_NAME!r}, tagged 'baseline': {dataset.url}")


if __name__ == "__main__":
    main()
