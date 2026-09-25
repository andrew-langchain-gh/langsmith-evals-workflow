"""Query production root runs with the v2 runs API (`list_runs` is deprecated)."""

import asyncio
from datetime import datetime, timedelta, timezone

from langsmith import Client

DEFAULT_FIELDS = ["ID", "PROJECT_ID", "START_TIME", "INPUTS", "OUTPUTS", "THREAD_ID", "TRACE_ID", "METADATA", "FEEDBACK_STATS"]


def query_root_runs(
    client: Client, project_name: str, *, filter: str = "eq(is_root, true)", days: int = 7, limit: int = 100
) -> list:
    project = client.read_project(project_name=project_name)

    async def collect() -> list:
        runs = []
        async for run in client.runs.query_v2(
            project_ids=[str(project.id)],
            is_root=True,
            min_start_time=datetime.now(timezone.utc) - timedelta(days=days),
            selects=DEFAULT_FIELDS,  # type: ignore[arg-type]
            page_size=min(limit, 100),
            filter=filter,
        ):
            runs.append(run)
            if len(runs) >= limit:
                break
        return runs

    return asyncio.run(collect())
