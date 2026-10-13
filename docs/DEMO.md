# Demo Runbook: Evaluating an Agent with LangSmith

A walkthrough in five steps using the travel planner deep agent: create a golden dataset, score offline assertions, deploy and evaluate live traffic, import reviewed traces, and compare coordinator trajectories. The UI supports inspection, online evaluator configuration, and human review. The scripts create datasets/examples and run offline SDK evaluators.

The [Jupyter notebook](../notebooks/agent_evaluations.ipynb) presents the same five
steps with direct SDK code and explanatory markdown. It includes all five golden
examples and 18 traffic requests, with resource IDs configured in one cell. Run it
section by section; skip trace import when reusing the existing reference dataset.

```
 1. golden dataset → 2. offline assertions → 3. deploy + online evals
                                                    ↓
 5. trajectory experiment ← 4. review + SDK trace import
```

## Pre-demo checklist

```sh
uv sync
# First-time setup only: copy .env.example to .env and configure credentials.
uv run pytest                                # tools, deployment client, trajectory matching
uv run evals/00_reset_demo.py                # optional: reset configured resources (see appendix)
uv run evals/01_create_golden_dataset.py
```

- **Dates:** the examples in `evals/01_create_golden_dataset.py` and `evals/03_generate_traffic.py` name dates without a year (October–December). If the demo happens after those dates, move them forward.
- **Workspace secret:** the UI evaluators need a model key. Go to Settings → Secrets and add `ANTHROPIC_API_KEY` (or the key for your judge model's provider).
- **Rehearse steps 4–5 in advance:** configure the online evaluator and queue automation before running `03`, then allow feedback and queue items to appear. Create an empty trajectory dataset in the UI and copy its ID for `04` and `05`. The current trajectory dataset is `503aa3e3-c21c-4562-bb6c-bccb5f33d3ee`. Use this ID for both `04` and `05`; avoid importing the same traces repeatedly.

---

## Step 1: A hand-curated golden dataset (`evals/01_create_golden_dataset.py`)

**Show:** The `EXAMPLES` list in the script, then Datasets & Experiments → `travel-planner-golden`.

**Talk track:**
- "There are many ways to get started evaluating an agent by building a golden dataset: collecting agent traces, building a human-curated dataset by hand, or synthetically generating data with the help of an LLM. For this demonstration we will curate a dataset by hand."
- Each example is a `question` and the `answer` a travel expert expects, in the same shape as the [chatbot tutorial](https://docs.langchain.com/langsmith/evaluate-chatbot-tutorial).
- The answers are **key facts**, not a word-for-word reply: what was booked, for whom, when, and where. A good agent can write a different itinerary and still be correct.
- All five examples are booking requests with named assertions for the expected trip details, hotel, activities, confirmation codes, and total cost.

## Step 2: SDK assertion evaluation and an experiment (`evals/02_run_experiment.py`)

**Primary evaluator:** `02` defines `grade_assertions()` and passes it directly to `Client.evaluate()`. It produces one LLM-as-judge score per named assertion; no UI evaluator setup is required.

**Optional additional evaluator in the UI:** open `travel-planner-golden` → **Evaluators** → **+ Evaluator** → **Create from a template** → **Correctness**.
- Map the variables:
  - input → `inputs.question`
  - output → `outputs.answer`
  - reference output → `reference_outputs.answer`
- Model: Claude Sonnet (a stronger judge than the Haiku agent). Output: boolean. Feedback key: `correctness`.
- Optionally, add a **Conciseness** template the same way.

**Run the experiment:**

```sh
uv run evals/02_run_experiment.py
```

**Compare agent models:** run these commands from the project root. Both use the same Anthropic judge and run each example three times within one experiment. Each command creates a separate experiment to compare in LangSmith.

Anthropic agent:

```sh
TRAVEL_PLANNER_MODEL=anthropic:claude-haiku-4-5-20251001 \
uv run evals/02_run_experiment.py \
  --judge-model anthropic:claude-sonnet-4-5-20250929 \
  --num-repetitions 3
```

OpenAI agent:

```sh
TRAVEL_PLANNER_MODEL=openai:gpt-4.1 \
uv run --with langchain-openai evals/02_run_experiment.py \
  --judge-model anthropic:claude-sonnet-4-5-20250929 \
  --num-repetitions 3
```

`--with langchain-openai` supplies the OpenAI integration for that run; it is not currently a project dependency. Both commands need LangSmith and Anthropic credentials available locally, and the OpenAI command also needs `OPENAI_API_KEY`. Workspace secrets used by UI evaluators do not configure the local SDK judge.

If `.env` defines `TRAVEL_PLANNER_MODEL`, remove that entry before running these commands: the script loads `.env` with `override=True`, which would override the model selected on the command line.

**Show:** The script passes `evaluators=[grade_assertions]` to `Client.evaluate()`. Show the evaluator in the same file: each assertion becomes a feedback score. The optional UI-bound correctness judge also adds a `correctness` column. Open a row and compare the scores and judge reasoning.

**Talk track:**
- The SDK evaluator is supplied explicitly on each experiment. Optional evaluators bound to the dataset also run automatically, so subject-matter experts can manage an additional rubric in the UI.
- Correctness is **reference-based**: it needs the expected answer. Keep that in mind for step 3.

## Step 3: Deploy and watch (`evals/03_generate_traffic.py`)

**Talk track:** "Once you have a baseline of dataset examples and evaluators, it is time to deploy the agent and watch its behavior."

**Deploy first:** follow [DEPLOYMENT.md](DEPLOYMENT.md), using deployment name `langsmith-evals-workflow`. Copy the deployment's API URL once it is ready. Open its linked tracing project or agent environment; Cloud controls the hosted tracing destination.

Run the LangGraph CLI from the project root:

```sh
uv run langgraph deploy --remote --name langsmith-evals-workflow
```

`--remote` builds in the cloud without requiring local Docker. The command uses `langgraph.json` and deployment credentials from `.env`; non-reserved variables in that file become hosted secrets. The installed CLI (`0.4.32`) defaults to legacy deployment type `dev`. If your workspace rejects that type, use the LangSmith UI's **Serverless** option or update to a CLI version supporting the current deployment types.

After the deployment is ready, send a smoke-test request using its API URL:

```sh
uv run evals/03_generate_traffic.py --url https://langsmith-evals-workflow-1adb7e671f445cc1867199bd250fad01.us.langgraph.app --n 1 --concurrency 1
```

**Show:** The deployment's tracing destination and the smoke-test request. For a fresh deployment, show the smoke trace before adding the online evaluator. Without `--url`, the script runs the agent locally and only simulates production tracing.

**Add online evaluators:** project → **Evaluators** → **+ Evaluator** → **Create from a template** → **Safety** → **Toxicity**.
- Filter: root runs. Sampling: 100% for the demo; say 10–20% in production.
- Map the text variable to the user's message in `inputs.messages`. Here we're flagging abusive users; the agent's replies stay polite. Preview the mapping on the smoke-test trace.

**Generate traffic after saving the evaluator:**

```sh
uv run evals/03_generate_traffic.py --url https://langsmith-evals-workflow-1adb7e671f445cc1867199bd250fad01.us.langgraph.app --n 18 --concurrency 5
```

Show ordinary bookings, rude users, and requests the agent cannot fully satisfy, such as a Paris hotel under $50 or a return date before departure. Hosted outputs use `outputs.messages`; the `outputs.answer` wrapper belongs to the offline runner.

**Talk track:**
- Production traffic has **no reference answers**, so correctness can't run here. Online evaluators must be **reference-free**: toxicity, safety, format, and policy checks.
- Online metrics tell you **that** something is happening in production. Step 4 turns those traces into something you can test against.

## Step 4: Import a reviewed trace

**1. Create an annotation queue:** Annotation queues → **+ New queue** → `travel-planner-review`.

**2. Create an automation rule:** prod project → **Automations** → **+ Rule**.
- Filter: feedback `toxicity` = true. You can also use a sample rate, since any filter works.
- Action: **Add to annotation queue** → `travel-planner-review`.
- Talk track: rules run on new traces, and you can apply them to past traces when you create the rule.

**3. Review one item in the queue.** Open the root coordinator trace and inspect the `task` calls and specialist summaries. Copy the root run ID, then import it through the SDK:

```sh
uv run evals/04_import_trajectory_example.py \
  --run-id 01a117a2-46e8-7861-8705-70b44fead800 \
  --dataset 503aa3e3-c21c-4562-bb6c-bccb5f33d3ee
```

The importer saves `run.inputs` as replay inputs and `run.outputs` as reference outputs, with `source_run_id` linking the example to its reviewed run. Each invocation creates an example. Review in the UI, then import through `04`; the UI conversation import previously placed the full history in inputs and left outputs empty. The current dataset has been corrected.

The single-run example above is the previously reviewed Tokyo booking trace. For a new trace, replace `--run-id` after reviewing it. Use the new trajectory dataset specified below for both import and evaluation.

To import all completed, successful root traces from the new `langsmith-evals-workflow-production` project:

```sh
uv run evals/04_import_trajectory_example.py \
  --project-id 01a136da-a562-7b6c-9640-37a603fc6c0c \
  --dataset 503aa3e3-c21c-4562-bb6c-bccb5f33d3ee
```

Project import includes traces with no coordinator calls and creates new examples
each time it runs. It skips failed and unfinished traces. Review the project
before importing all of its traces as references.

## Step 5: Evaluate coordinator trajectories

**1. Explain the coordinator matching policy:**

The SDK evaluator projects assistant messages containing `task` or `write_file` calls. It omits planning tools, prose, and tool results. `task` matches on `subagent_type`; `write_file` matches on `file_path`. Strict matching preserves batch order and membership while allowing calls inside a batch to reorder. Unordered matching checks the same call inventory across all batches.

The new Tokyo reference's batches: flight + hotel delegation → flight + hotel delegation → activities → write `/itinerary.md`. The first batch requests searches and the second requests bookings, but the matcher does not grade task descriptions or prove search-before-booking. Detailed specialist tools and booking correctness are outside this stage.

**2. Run the experiment against the reference dataset:**

```sh
uv run evals/05_run_trajectory_experiment.py \
  --dataset 503aa3e3-c21c-4562-bb6c-bccb5f33d3ee
```

The runner passes its evaluators explicitly to `Client.evaluate()`; no UI evaluator binding is required. It uses dataset examples directly, expecting original user messages in inputs and reference messages in outputs. Use `--dataset <dataset-id>` for another reviewed dataset. `--num-repetitions` defaults to 1.

**3. Inspect the recorded results:** Show `trajectory_strict_match` and `trajectory_unordered_match`, then open a row and compare actual delegation batches with the reference. The target runs the agent locally; it does not call the deployed endpoint. Both scores use coordinator messages, so specialist search/booking execution remains outside this evaluation.

Four current references contain no tool calls: matching checks that a new run also has no relevant calls, not whether its clarification text is correct. Dana's Paris reference omits `write_file`; retain it only if that is an accepted reference behavior.

**Talk track:**
- Final-answer evaluators check **what** the agent said. This coordinator evaluator checks which specialists it delegated to, the delegation batches, and the itinerary path. It does not grade IDs, instructions, or specialist execution.
- A reviewed reference trajectory comes from production; project-wide imports are candidates until reviewed. The loop is closed: **traffic → review → dataset → experiment**.

## Step 6: Gate a GitHub PR

Follow [CI.md](CI.md) to run the same golden assertions on proposed changes.
Show a failing confirmation-code assertion, inspect the experiment and review queue,
then fix the prompt and show the passing required check. Reports are published even
when evaluation fails.

### Run CI without changing application code

Create a branch with an empty commit, push it, and open a PR against `main`:

```sh
git switch -c demo/ci-evaluation
git commit --allow-empty -m "Trigger CI evaluation demo"
git push -u origin demo/ci-evaluation
```

[Open the PR on GitHub](https://github.com/andrew-langchain-gh/langsmith-evals-workflow/compare/main...demo/ci-evaluation).
The `pull_request` trigger runs the golden assertion experiment even though no
application files changed. Show the **Golden assertions** job, the PR report,
and its **Open LangSmith experiment** link. The outcome reflects the current
agent's scores; an empty PR does not guarantee a passing check. Use a fresh branch
name if `demo/ci-evaluation` already exists.

Alternatively, use **Actions → Golden assertion evaluation → Run workflow** to
run without a PR. Manual runs publish a job summary and downloadable report;
they do not post a PR comment. Configure the repository secrets first, as described
in [CI.md](CI.md).

## Recap

| Tool | Use it when | In this demo |
|---|---|---|
| **Golden dataset** | You can say what "correct" looks like | 5 hand-written questions and answers |
| **Offline evaluator** | Comparing versions before shipping, with a reference | SDK judge scores each named assertion; optional UI correctness judge |
| **Online evaluator** | After shipping, on real traffic without references | Toxicity on the prod project |
| **Automation rule** | An online signal should trigger an action | Flagged runs → annotation queue |
| **Annotation queue** | A human needs to judge or curate | Review a trace, then import raw root inputs/outputs with `04` |
| **Trajectory evaluator** | *How* the agent acts matters, not just the answer | Compare the path against a reviewed trace |

---

## Appendix: Resetting between rehearsals

`uv run evals/00_reset_demo.py` deletes the two datasets named in `travel_planner/evals/settings.py`, their experiments/evaluator rules, the queue, and the project named `deepagent-travel-planner-prod` if it exists. It does not delete deployments or automatically find the replacement deployment's linked tracing project or the project passed to `04 --project-id`.

The reset script still needs configurable project IDs to fully reset this hosted workflow. After recreating the trajectory dataset, pass its new ID to both `04` and `05`; `05`'s current default points to the existing dataset.
