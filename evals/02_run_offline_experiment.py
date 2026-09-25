"""Stage 2 - Offline experiment: run a prompt version against the golden dataset with every evaluator.

Run v1 and v2, then open the Datasets & Experiments page and compare the two experiments side by side.
"""

import argparse

from dotenv import load_dotenv
from langsmith import Client

from travel_planner.agent import model_name
from travel_planner.evals.evaluators import DETERMINISTIC_EVALUATORS, LLM_EVALUATORS, all_checks_pass_rate
from travel_planner.evals.harness import run_agent
from travel_planner.evals.settings import DATASET_NAME
from travel_planner.prompts import COORDINATOR_PROMPTS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", choices=COORDINATOR_PROMPTS, default="v2")
    parser.add_argument("--split", action="append", help="Only run these splits (repeatable), e.g. core")
    parser.add_argument("--as-of", help="Dataset version tag to pin, e.g. baseline")
    parser.add_argument("--no-llm-judges", action="store_true", help="Deterministic evaluators only (cheaper)")
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()

    load_dotenv(override=True)
    client = Client()

    def travel_planner(inputs: dict) -> dict:
        return run_agent(inputs, prompt_version=args.prompt)

    data = (
        client.list_examples(dataset_name=DATASET_NAME, splits=args.split, as_of=args.as_of)
        if args.split or args.as_of
        else DATASET_NAME
    )
    evaluators = DETERMINISTIC_EVALUATORS + ([] if args.no_llm_judges else LLM_EVALUATORS)

    # langsmith's SUMMARY_EVALUATOR_T only types the (runs, examples) form; (outputs, reference_outputs) is supported.
    results = client.evaluate(  # pyright: ignore[reportCallIssue]
        travel_planner,
        data=data,
        evaluators=evaluators,
        summary_evaluators=[all_checks_pass_rate],  # pyright: ignore[reportArgumentType]
        experiment_prefix=f"prompt-{args.prompt}",
        description=f"Coordinator prompt {args.prompt}",
        metadata={"prompt_version": args.prompt, "model": model_name(), "dataset_version": args.as_of or "latest"},
        max_concurrency=args.concurrency,
    )
    print(f"\nExperiment: {results.experiment_name}")


if __name__ == "__main__":
    main()
