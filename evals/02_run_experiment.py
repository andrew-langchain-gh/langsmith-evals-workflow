"""Step 2 - Offline experiment: run the agent over a dataset and let the evaluators bound to it in the UI score it.

There are no SDK evaluators here on purpose: the correctness judge (and, in step 4, the trajectory evaluator) is
created in the LangSmith UI on the dataset, and LangSmith runs it automatically on every new experiment.
"""

import argparse

from dotenv import load_dotenv
from langchain_core.utils.uuid import uuid7
from langgraph.checkpoint.memory import InMemorySaver
from langsmith import Client

from travel_planner.agent import build_agent, model_name
from travel_planner.evals.settings import DATASET_NAME


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=DATASET_NAME, help="e.g. travel-planner-trajectories in step 4")
    parser.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args()

    load_dotenv(override=True)
    agent = build_agent(checkpointer=InMemorySaver())

    def travel_planner(inputs: dict) -> dict:
        messages = inputs.get("messages") or [{"role": "user", "content": inputs["question"]}]
        result = agent.invoke({"messages": messages}, {"configurable": {"thread_id": str(uuid7())}})
        return {"answer": result["messages"][-1].text, "messages": result["messages"]}

    results = Client().evaluate(
        travel_planner,
        data=args.dataset,
        experiment_prefix="travel-planner",
        metadata={"model": model_name()},
        max_concurrency=args.concurrency,
    )
    print(f"\nExperiment: {results.experiment_name}")


if __name__ == "__main__":
    main()
