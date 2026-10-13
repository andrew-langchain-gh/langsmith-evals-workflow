import os
from datetime import date

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langgraph.types import Checkpointer

from travel_planner.prompts import COORDINATOR_PROMPT
from travel_planner.subagents import SUBAGENTS

DEFAULT_MODEL = "anthropic:claude-haiku-4-5-20251001"


def model_name() -> str:
    return os.environ.get("TRAVEL_PLANNER_MODEL", DEFAULT_MODEL)


def build_agent(checkpointer: Checkpointer = None):
    agent = create_deep_agent(
        model=init_chat_model(model_name()),
        system_prompt=COORDINATOR_PROMPT.format(today=date.today().isoformat()),
        subagents=SUBAGENTS,
        checkpointer=checkpointer,
        name="travel-planner",
    )
    return agent.with_config({"metadata": {"model": model_name()}})


def make_graph(config: RunnableConfig):
    """Graph factory for local and hosted Agent Server; the server manages persistence."""
    return build_agent()
