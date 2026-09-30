"""Offline-eval target: run the agent on one dataset example and capture its full multi-agent trajectory."""

import json

from langchain_core.runnables import RunnableConfig
from langchain_core.utils.uuid import uuid7
from langgraph.checkpoint.memory import InMemorySaver

from travel_planner.agent import build_agent


class TrajectoryRecorder:
    """Collects every tool call made by the coordinator and its subagents, in stream order.

    Each step keeps the id of the AI message that issued it, so calls issued together (in parallel) share a
    `message_id`. `call_seq`/`result_seq` record when the call and its result appeared in the stream, so a `task`
    call's result lands after the subagent steps it spawned.
    """

    def __init__(self) -> None:
        self._steps: dict[str, dict] = {}
        self._seq = 0

    def _next(self) -> int:
        self._seq += 1
        return self._seq

    def on_chunk(self, chunk: dict) -> None:
        if chunk["type"] != "updates":
            return
        agent = "subagent" if chunk["ns"] else "coordinator"
        for update in chunk["data"].values():
            if not isinstance(update, dict):
                continue
            for message in update.get("messages", []):
                if message.type == "tool" and message.tool_call_id in self._steps:
                    step = self._steps[message.tool_call_id]
                    step.update(result=message.text, result_seq=self._next())
                for call in getattr(message, "tool_calls", None) or []:
                    if call["id"] not in self._steps:
                        self._steps[call["id"]] = {
                            "agent": agent,
                            "tool": call["name"],
                            "args": call["args"],
                            "message_id": message.id,
                            "call_seq": self._next(),
                        }

    @property
    def steps(self) -> list[dict]:
        return list(self._steps.values())


RESULT_PREVIEW_CHARS = 600


def to_openai_trajectory(user_messages: list[dict], steps: list[dict], final_response: str) -> list[dict]:
    """Flatten coordinator + subagent tool calls into one OpenAI-format message list for agentevals.

    Messages follow stream order: a `task` call, the labeled [subagent] calls it spawned, then the `task` result.
    Calls issued together in parallel share one assistant message.
    """
    events: list[tuple[int, dict]] = []
    open_message: dict | None = None
    for i, step in enumerate(steps):
        call_seq, result_seq = step.get("call_seq", 2 * i), step.get("result_seq", 2 * i + 1)
        tool_call = {
            "id": f"call_{i}",
            "type": "function",
            "function": {"name": step["tool"], "arguments": json.dumps(step["args"])},
        }
        message_id = step.get("message_id")
        if open_message is not None and message_id is not None and open_message["_id"] == message_id:
            open_message["tool_calls"].append(tool_call)
        else:
            label = f"[{step.get('agent', 'coordinator')}]"
            open_message = {"role": "assistant", "content": label, "tool_calls": [tool_call], "_id": message_id}
            events.append((call_seq, open_message))
        result = step.get("result", "")[:RESULT_PREVIEW_CHARS]
        events.append((result_seq, {"role": "tool", "tool_call_id": f"call_{i}", "content": result}))

    ordered = [message for _, message in sorted(events, key=lambda e: e[0])]
    for message in ordered:
        message.pop("_id", None)
    return [*user_messages, *ordered, {"role": "assistant", "content": final_response}]


def run_agent(inputs: dict, prompt_version: str | None = None) -> dict:
    agent = build_agent(checkpointer=InMemorySaver(), version=prompt_version)
    config: RunnableConfig = {"configurable": {"thread_id": str(uuid7())}}
    recorder = TrajectoryRecorder()

    payload = {"messages": [dict(m) for m in inputs["messages"]]}  # the graph converts messages in place
    for chunk in agent.stream(payload, config=config, stream_mode="updates", subgraphs=True, version="v2"):
        recorder.on_chunk(chunk)

    final_response = agent.get_state(config).values["messages"][-1].text
    return {
        "final_response": final_response,
        "steps": recorder.steps,
        "trajectory": to_openai_trajectory(inputs["messages"], recorder.steps, final_response),
    }
