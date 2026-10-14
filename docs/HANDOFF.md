# Session handoff

Saved October 6, 2026. This records the preceding session's reported state for resuming work; implementation details have not been reverified during this handoff.

## Goal and current stopping point

Build a presentation demonstrating: golden dataset → offline assertion evaluations → deployed agent and online evaluations → human-reviewed trajectories → trajectory regression tests.

The trajectory presentation proposal is in `docs/TRAJECTORY_PRESENTATION.md`. The user requested the proposal be saved, then requested this handoff before restarting. **Do not assume authorization to implement the trajectory workflow yet.**

## User preferences

- Keep demonstration code clean, simple, and readable.
- Separate golden and trajectory experiment runners.
- Golden inputs use `inputs["question"]`; trajectory inputs use `inputs["messages"]`.
- Keep target and assertion evaluator together in the golden runner.
- User explicitly preferred nested function definitions inside `main()` over top-level functions wired with `partial`.
- `--num-repetitions` defaults to `1`.
- Avoid unnecessary permission questions. No commits or pushes requested.

## Completed work

### Golden dataset and offline evaluations

- `evals/01_create_golden_dataset.py` defines five booking examples with reference `answer` and `assertions`, each shaped `{"key": ..., "comment": ...}`.
- There are 25 assertions: five per example. London's extra budget assertion was removed.
- The former “Nothing is booked” example was replaced by Jamie Chen's solo SEA–Paris trip, November 12–16, four nights at Loft Montmartre Hotel, Eiffel Tower and Louvre.
- LangSmith dataset was recreated, then Jamie's example updated in place. Remote examples were verified against local definitions.
- Dataset: `travel-planner-golden`; ID: `f7013669-b43c-4e01-b61a-2536ed54d250`.
- Workspace: `ff74f6b5-f214-4385-bf4f-60fd0d94da58`.
- `evals/02_run_experiment.py` contains target and `grade_assertions()` nested in `main()`. A structured judge returns `Verdict(reason, passed)`, with one call per assertion and feedback containing key, numeric score, and explanation.
- `Client.evaluate()` explicitly receives `evaluators=[grade_assertions]`.
- Arguments include `--judge-model`, `--concurrency`, and `--num-repetitions`; default judge is `anthropic:claude-sonnet-4-5-20250929`.
- The SDK assertion demo lives in `evals/02_run_experiment.py`; the redundant `04` forwarding script and shared evaluator module were removed.
- `evals/05_run_trajectory_experiment.py` is separate and uses messages. It uses SDK strict/unordered evaluators and captures **only coordinator messages**, not full specialist trajectories.

### Deployment

Deep Agents can deploy with LangGraph CLI because they produce LangGraph graphs. The existing `make_graph` factory leaves checkpointer/store management to Agent Server.

- `langgraph.json` includes `"python_version": "3.13"`.
- `.dockerignore` excludes secrets, virtualenv, and caches.
- Successful command: `uv run langgraph deploy --remote --name deepagent-travel-planner-prod-20261007`.
- Installed CLI was `0.4.32`, accepting legacy `dev`/`prod` with default `dev`; current docs describe `serverless`/`dedicated`. Deployment succeeded with defaults.
- Redeployed October 7, 2026 under a fresh name after the deleted deployment's old name returned an environment conflict.
- Deployment ID: `cde3390e-2733-4ac0-a0c0-543f223c2eff`.
- Tracing project ID: `01a11772-c38a-77ef-8759-cce245ca9077`.
- API URL: `https://deepagent-travel-planner-pr-76c99bb254005eb2a4706a3d2dc1f40e.us.langgraph.app`.
- Dashboard: https://smith.langchain.com/o/ff74f6b5-f214-4385-bf4f-60fd0d94da58/host/deployments/cde3390e-2733-4ac0-a0c0-543f223c2eff
- Logs confirmed model requests through LangSmith LLM Gateway at `gateway.smith.langchain.com/anthropic/v1/messages`.

### Traffic client and verified fixes

`evals/03_generate_traffic.py --url ...` calls Agent Server; without `--url`, it runs a local rehearsal.

- Replaced `runs.wait()` after a 504 with persistent thread creation, `runs.create()`, and `runs.get()` polling every two seconds.
- Prints thread/run IDs, waits up to ten minutes, raises on failure/timeout, and does not automatically resubmit. HTTP timeout is 30 seconds.
- Authentication failure was caused by `load_dotenv(override=True)` replacing a valid exported key with an empty `.env` value.
- Fixed traffic script to load project-root `.env` with `override=False`.
- Resolves credentials from `LANGGRAPH_API_KEY`, `LANGSMITH_API_KEY`, `LANGCHAIN_API_KEY`, or `LANGGRAPH_HOST_API_KEY`, then explicitly passes the key to SDK. Hosted URLs without credentials fail before network access; localhost may run without credentials.
- Live smoke test succeeded with request: “Book a trip from SFO to Tokyo, November 10 - 14, for one. Mid-range budget, I love food. I'm Priya Shah.”
- Thread: `01a11776-6c34-7bd0-83a1-270e64e8d13c`; run: `01a11776-6da6-7443-8a27-b08d7c4ab86c`.
- This is a candidate reference trajectory only: successful execution does not prove booking correctness.
- `tests/test_deployment.py` covers routing, polling, failure/timeout, and authentication regression; last reported run had 16 passing tests.
- No online evaluators were created by us; user understands that workflow.

## Documentation

- `docs/DEMO.md`: runbook, model comparison commands, deployment, endpoint workflow.
- `README.md`: deployment and deployed smoke/full traffic commands.
- `docs/DEPLOYMENT.md`: research, CLI limitations, credentials, deployment details, smoke run.
- `docs/langsmith-dataset-assertions.md`: assertion research and guidance.
- `docs/agent-evals-slides.html`: standalone 11-slide deck including `evaluate()` and `grade_assertions()` examples; snippets syntax-checked. Browser visual preview was blocked by unavailable CUA authentication.
- `docs/TRAJECTORY_PRESENTATION.md`: latest trajectory presentation proposal.

## Proposed trajectory workflow — not yet implemented

Presentation sequence:

1. Show final answer beside expanded trace: the answer can conceal wrong actions.
2. Human-review a trace and promote it to a golden example.
3. Evaluate meaningful dependencies and arguments.
4. Compare a new experiment against those requirements.

Initial deterministic assertions:

- `must_search_before_booking`: corresponding successful search finishes before booking starts.
- `must_book_returned_ids`: booked IDs appear in relevant search results.
- `must_not_duplicate_bookings`: each selected booking occurs once.

Design constraints:

- Flight and hotel searches can run in parallel; enforce dependencies rather than one exact global order.
- Require booking coverage so empty/search-only trajectories cannot pass vacuously.
- Coordinator `outputs.messages` omits specialist tool calls. Both reference extraction and new experiment capture need child/subagent runs.
- Preserve arguments, results, call IDs, and execution context sufficient to establish ordering.
- Replay original input only; never put the approved trajectory into new agent inputs.
- Run the coordinator trajectory evaluator against live dataset examples and show the recorded scores and traces.
- Review the Tokyo smoke trace before using it as golden evidence.
- Proposed dataset: `travel-planner-trajectories`; review queue: `travel-planner-review`.
- Full-trajectory extraction, dataset population, and SDK trajectory evaluators remain unimplemented.
- Existing DEMO trajectory section overstates root-message capture; revise when implementing.

## References and cautions

- https://docs.langchain.com/langsmith/assertions
- https://docs.langchain.com/oss/python/langchain/test/evals#trajectory-match-evaluator
- https://docs.langchain.com/langsmith/evaluate-complex-agent
- https://docs.langchain.com/oss/python/deepagents/going-to-production
- https://docs.langchain.com/langsmith/cli#deploy

Other runners still use `load_dotenv(override=True)`; the verified authentication fix applies only to the traffic script. Do not print credentials or secret-file contents.

The working tree has many uncommitted changes from this session and an unrelated untracked `.DS_Store`. Preserve all user changes. No git commits were performed.

To resume, read this handoff and `docs/TRAJECTORY_PRESENTATION.md`, inspect the relevant files, and follow the user's next instruction.

## Trajectory import workflow update

- `04_import_trajectory_example.py --run-id <root-run-id> --dataset <dataset-id>` copies raw root inputs/outputs and records source_run_id. Each invocation creates an example.
- The experiment runner is now `05_run_trajectory_experiment.py`, defaulting to dataset `24c80282-0e05-4b07-9a7d-e06c4d7250b8`.
- Remove the malformed UI-imported example from that dataset before evaluation; it contains conversation history in inputs and no reference outputs.

## Repository migration and CI update (October 13, 2026)

- Local directory is now `/Users/andrew/src/langchain-demos/langsmith-evals-workflow`.
- Origin is `https://github.com/andrew-langchain-gh/langsmith-evals-workflow.git`.
- Distribution name is `langsmith-evals-workflow`; the application remains `travel_planner`.
- `.github/workflows/evaluate.yml` runs the golden assertion gate and reports PR results.
- `02_run_experiment.py --ci` requires all expected assertions to pass, with optional failed-run queue routing.
- GitHub secret and required-status-check setup is documented in `docs/CI.md`.

## Current hosted deployment (October 13)

- Name: `langsmith-evals-workflow`
- ID: `c8f61711-15de-4f08-b45d-205d43e7baa0`
- URL: https://langsmith-evals-workflow-1adb7e671f445cc1867199bd250fad01.us.langgraph.app
- Hosted trace project: `langsmith-evals-workflow-production` (`01a136da-a562-7b6c-9640-37a603fc6c0c`).
- Exact-name project rename was rejected with a conflict; existing projects are unchanged.
- Local `.env` uses `langsmith-evals-workflow`, and local traffic respects it.

## Final consistency review

- Current trajectory dataset: `503aa3e3-c21c-4562-bb6c-bccb5f33d3ee` in runbook, notebook, presentation notes, and runner default.
- README covers CI gate, PR reports, and failed-run queue with an ASCII flow chart.
- Model configuration in exported environment takes precedence over `.env` across runners.
- Reset supports explicit `--project-id`; no reset was executed during this review.
- Earlier status/dataset IDs in this handoff are historical.
