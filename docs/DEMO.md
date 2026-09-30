# Demo Runbook: Evaluating an Agent with LangSmith

A walkthrough in four steps that uses the travel planner deep agent to show a golden dataset, an offline LLM-as-judge evaluator, online evaluators on production traffic, and a trajectory evaluator on a dataset built from real traces. Most of the work happens in the LangSmith UI. The scripts only create data and run the agent.

```
 1. golden dataset ──► 2. offline experiment ──► 3. deploy + online evals ──► 4. trace → queue → dataset
   (hand-curated)       (correctness judge)        (toxicity on live traffic)     (trajectory evaluator)
```

## Pre-demo checklist

```sh
uv sync && cp .env.example .env              # ANTHROPIC_API_KEY + LangSmith keys
uv run pytest                                # tool unit tests, no LLM calls
uv run evals/00_reset_demo.py                # optional: wipe a previous run (asks to confirm)
uv run evals/01_create_golden_dataset.py
```

- **Dates:** the examples in `evals/01_create_golden_dataset.py` and `evals/03_generate_traffic.py` name dates without a year (October–December). If the demo happens after those dates, move them forward.
- **Workspace secret:** the UI evaluators need a model key. Go to Settings → Secrets and add `ANTHROPIC_API_KEY` (or the key for your judge model's provider).
- **Rehearse step 4 in advance:** online evaluators and automation rules take a few minutes to fire. Run `03` well before going on stage so the queue already has items.

---

## Step 1: A hand-curated golden dataset (`evals/01_create_golden_dataset.py`)

**Show:** The `EXAMPLES` list in the script, then Datasets & Experiments → `travel-planner-golden`.

**Talk track:**
- "There are many ways to get started evaluating an agent by building a golden dataset: collecting agent traces, building a human-curated dataset by hand, or synthetically generating data with the help of an LLM. For this demonstration we will curate a dataset by hand."
- Each example is a `question` and the `answer` a travel expert expects, in the same shape as the [chatbot tutorial](https://docs.langchain.com/langsmith/evaluate-chatbot-tutorial).
- The answers are **key facts**, not a word-for-word reply: what was booked, for whom, when, and where. A good agent can write a different itinerary and still be correct.
- One example says "don't book anything yet". Sometimes the correct answer is to **not act**.

## Step 2: A correctness evaluator, then an experiment (`evals/02_run_experiment.py`)

**Build the evaluator in the UI:** open `travel-planner-golden` → **Evaluators** → **+ Evaluator** → **Create from a template** → **Correctness**.
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

**Show:** The script contains no evaluator code at all. The experiment's `correctness` column is filled in by the evaluator you just bound to the dataset. Open a row and compare the agent's answer with the reference and the judge's reasoning.

**Talk track:**
- An evaluator bound to a dataset runs automatically on **every** experiment against that dataset. Subject-matter experts can own the rubric in the UI while engineers own the code.
- Correctness is **reference-based**: it needs the expected answer. Keep that in mind for step 3.

## Step 3: Deploy and watch (`evals/03_generate_traffic.py`)

**Talk track:** "Once you have a baseline of dataset examples and evaluators, it is time to deploy the agent and watch its behavior."

```sh
uv run evals/03_generate_traffic.py
```

**Show:** The `deepagent-travel-planner-prod` project. About 18 traces of one-shot requests: ordinary bookings, a few rude users, and a few requests the agent can't fully satisfy, such as a Paris hotel under $50 or a return date before the departure date. Point out that the project has **no online evaluators yet**.

**Add online evaluators:** project → **Evaluators** → **+ Evaluator** → **Create from a template** → **Safety** → **Toxicity**.
- Filter: root runs. Sampling: 100% for the demo; say 10–20% in production.
- Map the text variable to the run **input** (the user's message). Here we're flagging abusive users; the agent's replies stay polite.

**Talk track:**
- Production traffic has **no reference answers**, so correctness can't run here. Online evaluators must be **reference-free**: toxicity, safety, format, and policy checks.
- Online metrics tell you **that** something is happening in production. Step 4 turns those traces into something you can test against.

## Step 4: From a trace to a trajectory evaluator

**1. Create an annotation queue:** Annotation queues → **+ New queue** → `travel-planner-review`.

**2. Create an automation rule:** prod project → **Automations** → **+ Rule**.
- Filter: feedback `toxicity` = true. You can also use a sample rate, since any filter works.
- Action: **Add to annotation queue** → `travel-planner-review`.
- Talk track: rules run on new traces, and you can apply them to past traces when you create the rule.

**3. Review one item in the queue.** Open the trace and point out the **trajectory**: the coordinator's `task` tool calls to `flight-booker`, `hotel-booker`, and `activity-planner`, and the results each one returned (flight IDs, hotel IDs, confirmation codes). Click **Add to dataset** → **+ New dataset** → `travel-planner-trajectories`. The example's reference output is the run's `messages`, which is the trajectory a reviewer just approved.

**4. Bind a trajectory evaluator:** `travel-planner-trajectories` → **Evaluators** → **+ Evaluator** → **Create from a template** → **Trajectory**.
- Map the output messages to `outputs.messages` and the reference to `reference_outputs.messages`.

**5. Run the experiment against the new dataset:**

```sh
uv run evals/02_run_experiment.py --dataset travel-planner-trajectories
```

**Talk track:**
- Final-answer evaluators check **what** the agent said. Trajectory evaluators check **how** it got there: which subagents it delegated to, in what order, and with which IDs. A reply can look correct even when the agent booked the wrong thing or skipped a step.
- The reference trajectory came from production and a human approved it. The loop is closed: **traffic → review → dataset → experiment**.

## Recap

| Tool | Use it when | In this demo |
|---|---|---|
| **Golden dataset** | You can say what "correct" looks like | 5 hand-written questions and answers |
| **Offline evaluator** | Comparing versions before shipping, with a reference | Correctness judge bound to the dataset |
| **Online evaluator** | After shipping, on real traffic without references | Toxicity on the prod project |
| **Automation rule** | An online signal should trigger an action | Flagged runs → annotation queue |
| **Annotation queue** | A human needs to judge or curate | Review a trace and add it to a dataset |
| **Trajectory evaluator** | *How* the agent acts matters, not just the answer | Compare the path against a reviewed trace |

---

## Appendix: Resetting between rehearsals

`uv run evals/00_reset_demo.py` deletes everything the demo created in LangSmith: both datasets, their experiments and bound evaluators, the prod project with its online evaluators and rules, and the queue. Then start again from step 1.
