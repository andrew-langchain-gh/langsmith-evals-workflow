# Deploying the travel planner

## Supported deployment route

This Deep Agent can run on LangSmith Deployments through the LangGraph CLI. `create_deep_agent()` produces a LangGraph graph, and `langgraph.json` already exports the `travel_planner` graph through `travel_planner.agent.make_graph`.

The factory does not supply an in-memory checkpointer or store: Agent Server supplies persistence. The default Deep Agents filesystem is thread-scoped agent state, so `/itinerary.md` does not need a shared host filesystem. All travel tools remain deterministic mocks.

Managed Deep Agents is the current recommended managed Deep Agents product, but it uses a different project declaration and deployment workflow. Migrating to it is unnecessary for this evaluation demo. Direct LangSmith Deployment preserves the existing coordinator, subagents, tools, and API input format.

Sources, researched October 6, 2026:

- [Deep Agents: going to production](https://docs.langchain.com/oss/python/deepagents/going-to-production)
- [LangGraph CLI deployment reference](https://docs.langchain.com/langsmith/cli#deploy)
- [Deploy to LangSmith Cloud](https://docs.langchain.com/langsmith/deploy-to-cloud)
- [Online LLM-as-judge evaluators](https://docs.langchain.com/langsmith/online-evaluations-llm-as-judge)

## Configuration and credentials

`langgraph.json` installs this package with `dependencies: ["."]`, specifies Python 3.13 to match `pyproject.toml`, and serves `./travel_planner/agent.py:make_graph` as `travel_planner`. The `.dockerignore` excludes local secrets, the virtual environment, and generated files from Docker build contexts.

The config's `env` field points to `.env`. Provide credentials through your existing local environment setup; do not put values into tracked configuration or shell commands. The deploy CLI uses local LangSmith credentials to authenticate and uploads non-reserved variables from the configured env file as hosted secrets. Review which variable names you intend to deploy before running it.

For the default Anthropic agent:

- Local deployment authentication: `LANGSMITH_API_KEY`, with permission to deploy in the intended workspace. The installed deploy CLI accepts `LANGSMITH_TENANT_ID` (the workspace ID) when needed to disambiguate the workspace.
- Hosted model access: `ANTHROPIC_API_KEY`.
- Optional hosted model selection: `TRAVEL_PLANNER_MODEL`, defaulting to `anthropic:claude-haiku-4-5-20251001`.
- Optional Anthropic gateway configuration: `ANTHROPIC_BASE_URL` and `ANTHROPIC_CUSTOM_HEADERS`, if your existing model setup uses them.

Cloud manages its tracing credentials and tracing destination. Do not try to force the hosted tracing destination with `LANGSMITH_PROJECT`; it is reserved by the deploy CLI. The current deployment is named `langsmith-evals-workflow`; its managed tracing project is `langsmith-evals-workflow-production`.

Model-provider secrets used by online evaluators must also be configured in LangSmith **Settings → Secrets**. Those workspace secrets are separate from the deployed agent's runtime credentials.

## Validate and deploy

Optional local API rehearsal:

```sh
uv run langgraph dev --no-browser
```

In another terminal, send one request through the same API used in deployment:

```sh
uv run evals/03_generate_traffic.py --url http://127.0.0.1:2024 --n 1 --concurrency 1
```

Check the installed CLI before cloud deployment:

```sh
uv run langgraph --version
uv run langgraph deploy --help
```

The locally installed CLI is **0.4.32**. It supports remote builds, but its deployment-type choices are `dev` and `prod`, with `dev` as the default. Current docs describe `serverless` and `dedicated` for usage-based billing. Do not pass `--deployment-type serverless` to this installed version: it rejects that option. A cloud workspace using current deployment types may require a compatible newer CLI or the UI route below.

For a workspace accepting this CLI's default deployment type, the command is:

```sh
uv run langgraph deploy --remote --name langsmith-evals-workflow
```

`--remote` uploads the application for a remote build; local Docker is not required for this route. If you choose a local build instead, Docker must be running, and Apple Silicon builds need support for the target `linux/amd64` platform.

The CLI command is beta. Current docs state that it is not supported on LangSmith Cloud hosted in AWS. For an AWS workspace, or a workspace requiring the newer deployment-type options, use **Deployments → New Deployment → Import from GitHub**, select this repository and its branch, set the config path to `langgraph.json`, choose **Serverless** for the demo, and configure runtime secrets in the UI. This route needs the prepared changes available on the selected GitHub branch; local edits are not included automatically.

Wait for the deployment to report ready, then copy its **Deployment URL**. Use that URL rather than the LangSmith dashboard URL or the control-plane URL.

## Online evaluators and deployed traffic

1. Open the deployment's linked tracing project or agent environment.
2. Add an online **Toxicity** evaluator. Filter to root runs and use 100% sampling for the demo. Map its text to the user's message in `inputs.messages`; this example flags abusive inputs.
3. Optionally add a reference-free evaluator for the assistant response. Map it to the final assistant message in `outputs.messages`. Hosted graph outputs contain message state, not the `outputs.answer` wrapper used by the offline runner.
4. Preview the variable mappings on a trace before enabling each evaluator. If no trace exists yet, send the one-request smoke test below, then create the evaluator and generate the remaining traffic.

Smoke test, replacing the example URL with your deployment URL:

```sh
uv run evals/03_generate_traffic.py \
  --url https://YOUR-DEPLOYMENT-URL \
  --n 1 --concurrency 1
```

Generate all 18 demo requests after configuring the evaluator:

```sh
uv run evals/03_generate_traffic.py \
  --url https://YOUR-DEPLOYMENT-URL \
  --n 18 --concurrency 5
```

The client reads local LangSmith credentials. Each request creates a persistent thread and submits `runs.create(thread_id, "travel_planner", ...)`, then polls `runs.get()` until completion. This avoids holding one HTTP request open for the entire agent execution, which can produce a gateway 504 even when the Python client's timeout is longer. Thread and run IDs are printed for debugging. The script stops waiting after ten minutes without cancelling or resubmitting the run; it may still be executing. Server-side failures are reported instead of being treated as successful requests. The server chooses the hosted agent model; changing a local model environment variable does not change a deployed revision.

The traffic client requires a local `LANGSMITH_API_KEY` (or `LANGGRAPH_API_KEY`, legacy `LANGCHAIN_API_KEY`, or the deployment CLI's `LANGGRAPH_HOST_API_KEY`) in the invoking environment or the project's `.env`. The script explicitly loads the project's file without overriding exported variables, so an empty `.env` placeholder cannot erase a valid shell credential. It passes the resolved credential to the SDK and fails before network calls if none is available for a hosted URL. A credential saved only in a CLI profile does not automatically authenticate the Python SDK. “Missing authentication headers” means the SDK did not send a credential; it is separate from a gateway timeout.

Without `--url`, this script still supports local rehearsal: it invokes the agent in-process and respects `LANGSMITH_PROJECT` from `.env` (currently `langsmith-evals-workflow`). That mode does not exercise a deployment.

Online scoring and automation rules can take time to appear. Verify root runs and subagent/tool spans in the linked tracing destination, then inspect evaluator feedback before rehearsing the annotation-queue workflow in `DEMO.md`.

## Deployment status

Redeployed October 13, 2026 after the repository rename.

- Deployment: `langsmith-evals-workflow`
- Deployment ID: `c8f61711-15de-4f08-b45d-205d43e7baa0`
- API URL: https://langsmith-evals-workflow-1adb7e671f445cc1867199bd250fad01.us.langgraph.app
- Hosted tracing project: `langsmith-evals-workflow-production`
- Tracing project ID: `01a136da-a562-7b6c-9640-37a603fc6c0c`
- [Deployment dashboard](https://smith.langchain.com/o/ff74f6b5-f214-4385-bf4f-60fd0d94da58/host/deployments/c8f61711-15de-4f08-b45d-205d43e7baa0)

Local `.env` uses `LANGSMITH_PROJECT=langsmith-evals-workflow`. Hosted tracing is
managed by LangSmith and uses the production project above. The CLI skips the
reserved `LANGSMITH_PROJECT` variable. Renaming the hosted project to the exact
local name was rejected with a name conflict; no existing project was renamed.
Existing trajectory dataset examples still reference previously reviewed runs.
The earlier deployment has not been deleted.
