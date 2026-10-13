from copy import deepcopy
import json
import runpy
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, ToolMessage

trajectory_script = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "evals/05_run_trajectory_experiment.py")
)
coordinator_matcher = trajectory_script["coordinator_matcher"]
coordinator_trajectory = trajectory_script["coordinator_trajectory"]


@pytest.fixture
def reference():
    fixture = Path(__file__).parent / "fixtures/coordinator_tokyo.json"
    return coordinator_trajectory(json.loads(fixture.read_text())["messages"])


def score(actual, reference, mode="strict"):
    return coordinator_matcher(mode)(outputs=actual, reference_outputs=reference)["score"]


def test_parallel_calls_and_prose_can_change(reference):
    actual = deepcopy(reference)
    actual[0].tool_calls.reverse()
    actual[0].tool_calls[0]["args"]["description"] = "Different delegation wording"
    actual[2].tool_calls[0]["args"]["content"] = "Different itinerary"
    actual[0].content = "Different assistant wording"
    assert score(actual, reference)


def test_batches_preserve_order(reference):
    actual = [reference[1], reference[0], reference[2]]
    assert not score(actual, reference)
    assert score(actual, reference, "unordered")


@pytest.mark.parametrize("change", ["wrong_specialist", "wrong_path", "missing", "duplicate", "empty"])
def test_regressions_fail(reference, change):
    actual = deepcopy(reference)
    if change == "wrong_specialist":
        actual[0].tool_calls[0]["args"]["subagent_type"] = "calendar-checker"
    elif change == "wrong_path":
        actual[2].tool_calls[0]["args"]["file_path"] = "/other.md"
    elif change == "missing":
        actual[1].tool_calls.pop()
    elif change == "duplicate":
        actual[1].tool_calls.append(deepcopy(actual[1].tool_calls[0]))
    else:
        actual = []
    assert not score(actual, reference)
    assert not score(actual, reference, "unordered")


def test_projection_omits_planning_and_tool_results(reference):
    history = [
        AIMessage(content="Planning", tool_calls=[{"id": "todo", "name": "write_todos", "args": {}}]),
        ToolMessage(content="Done", tool_call_id="todo"),
        *reference,
        AIMessage(content="Final answer"),
    ]
    assert score(coordinator_trajectory(history), reference)
