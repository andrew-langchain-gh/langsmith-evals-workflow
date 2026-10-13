"""Step 5 - Compare coordinator delegation against a reviewed trace."""

import argparse
from pathlib import Path

from agentevals.trajectory.match import create_trajectory_match_evaluator
from dotenv import load_dotenv
from langchain_core.utils.uuid import uuid7
from langchain_core.messages import AIMessage, convert_to_messages
from langgraph.checkpoint.memory import InMemorySaver
from langsmith import Client

from travel_planner.agent import build_agent, model_name

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


def coordinator_trajectory(messages: list) -> list[AIMessage]:
    """Keep task/write_file batches; omit prose, results, and planning tools."""
    trajectory = []
    for message in convert_to_messages(messages):
        calls = [
            call for call in getattr(message, "tool_calls", [])
            if call["name"] in {"task", "write_file"}
        ]
        if calls:
            trajectory.append(AIMessage(content="", tool_calls=calls))
    return trajectory


def coordinator_matcher(mode: str = "strict"):
    return create_trajectory_match_evaluator(
        trajectory_match_mode=mode,
        tool_args_match_overrides={
            "task": ["subagent_type"],
            "write_file": ["file_path"],
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="24c80282-0e05-4b07-9a7d-e06c4d7250b8")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--num-repetitions", type=int, default=1, help="Runs per dataset example (default: 1)")
    args = parser.parse_args()
    if args.num_repetitions < 1:
        parser.error("--num-repetitions must be at least 1")

    matchers = {mode: coordinator_matcher(mode) for mode in ("strict", "unordered")}

    client = Client()
    examples = list(client.list_examples(dataset_id=args.dataset))
    agent = build_agent(checkpointer=InMemorySaver())

    def travel_planner(inputs: dict) -> dict:
        messages = inputs["messages"]
        result = agent.invoke({"messages": messages}, {"configurable": {"thread_id": str(uuid7())}})
        return {"messages": result["messages"]}

    def grade_trajectory(outputs: dict, reference_outputs: dict):
        actual = coordinator_trajectory(outputs["messages"])
        reference = coordinator_trajectory(reference_outputs["messages"])
        return [
            matcher(outputs=actual, reference_outputs=reference)
            for matcher in matchers.values()
        ]

    results = client.evaluate(
        travel_planner,
        data=examples,
        evaluators=[grade_trajectory],
        experiment_prefix="travel-planner-trajectories",
        metadata={"model": model_name(), "scope": "coordinator", "task_args": "subagent_type", "write_file_args": "file_path"},
        max_concurrency=args.concurrency,
        num_repetitions=args.num_repetitions,
    )
    print(f"\nExperiment: {results.experiment_name}")


if __name__ == "__main__":
    main()
