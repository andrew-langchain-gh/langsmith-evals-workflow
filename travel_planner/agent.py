import os
from datetime import date

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langgraph.types import Checkpointer

from travel_planner.prompts import COORDINATOR_PROMPTS
from travel_planner.subagents import SUBAGENTS

DEFAULT_MODEL = "anthropic:claude-haiku-4-5-20251001"
DEFAULT_PROMPT_VERSION = "v2"


def model_name() -> str:
    return os.environ.get("TRAVEL_PLANNER_MODEL", DEFAULT_MODEL)


def prompt_version(override: str | None = None) -> str:
    return override or os.environ.get("TRAVEL_PLANNER_PROMPT_VERSION", DEFAULT_PROMPT_VERSION)


def build_agent(checkpointer: Checkpointer = None, version: str | None = None):
    version = prompt_version(version)
    agent = create_deep_agent(
        model=init_chat_model(model_name()),
        system_prompt=COORDINATOR_PROMPTS[version].format(today=date.today().isoformat()),
        subagents=SUBAGENTS,
        checkpointer=checkpointer,
        name="travel-planner",
    )
    return agent.with_config({"metadata": {"prompt_version": version, "model": model_name()}})


def make_graph(config: RunnableConfig):
    """Graph factory for `langgraph dev`; the server supplies its own checkpointer."""
    return build_agent()
