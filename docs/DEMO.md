# Demo Runbook: The Agent Development Lifecycle in LangSmith

This is a 30-minute walkthrough that uses the travel planner deep agent to show how and when to use each LangSmith evaluation tool: golden datasets, offline experiments, trajectory evals, online evaluators, and annotation queues.

**The story.** We shipped coordinator prompt **v1** in a hurry. v1 skips the calendar check, searches sequentially, and books its own recommendation without asking the user. We catch that offline, watch the same flaws show up in production, have a human review them, turn them into regression tests, and verify the fix (**v2**).

```
   ┌─────────── build ───────────┐
   │  prototype agent (mocks)    │
   └──────────────┬──────────────┘
                  ▼
   golden dataset ──► offline experiments ──► compare v1 vs v2 ──► ship
        ▲                (incl. trajectories)                       │
        │                                                           ▼
   add to dataset ◄── annotation queue ◄── automation ◄── online evaluators
   (from-production)    (human review)       rules        on prod traffic
```

## Pre-demo checklist

Live experiments take a few minutes, so run everything beforehand and keep one live run for the stage.

```sh
uv sync && cp .env.example .env                       # ANTHROPIC_API_KEY + LangSmith keys
uv run pytest                                         # evaluator + tool unit tests, no LLM calls
uv run evals/00_reset_demo.py                         # optional: wipe a previous run (asks to confirm)
uv run evals/01_create_golden_dataset.py              # dataset + splits + 'baseline' tag
uv run evals/02_run_offline_experiment.py --prompt v1
uv run evals/02_run_offline_experiment.py --prompt v2
uv run evals/03_simulate_production_traffic.py --prompt v1   # "production" traffic
uv run evals/04_setup_annotation_queue.py
uv run evals/05_setup_online_evaluators.py            # then add the two LLM judges in the UI (stage 5)
# wait ~5 minutes for online evaluators and rules to run, then:
uv run evals/04_setup_annotation_queue.py --enqueue-flagged   # optional: don't wait for the rule to poll
```

Before going on stage, review 2–3 queue items yourself and add a `correction` to at least one of them, so stage 6 has something to promote.

Open these tabs:
- the dataset `travel-planner-golden`
- the v1/v2 experiment comparison
- the prod project `deepagent-travel-planner-prod`
- the annotation queue `travel-planner-review`

## Agenda

| Time | Stage | Show |
|---|---|---|
| 0–3 | Why evals for agents | The lifecycle diagram above, and the agent architecture from the README |
| 3–9 | 1–2 Golden dataset and offline experiment | Dataset, splits, v1 experiment results |
| 9–14 | Trajectories | The v1 trace and the trajectory evaluator scores |
| 14–17 | Fix and compare | The v2 experiment and the comparison view |
| 17–23 | 3 + 5 Production and online evals | Prod threads, evaluator feedback, the automation rule |
| 23–28 | 4 + 6 Annotation queue, then the dataset | Review one item and promote it |
| 28–30 | Recap | The "when to use" table below |

---

## Stage 1: Golden dataset (`evals/01_create_golden_dataset.py`)

**Show:** Datasets & Experiments → `travel-planner-golden`. Open an example and walk through its reference outputs.

**Talk track:**
- **When to create one.** As soon as the prototype works end to end and you can say what "correct" means. Don't wait for production. Start with **10–20 hand-written examples** that cover happy paths and the edge cases you're worried about.
- **What goes in a reference for an agent.** For an agent, the reference is more than the final answer. It also covers:
  - which subagents must run (`required_subagents`) and which must not (`forbidden_subagents`);
  - ordering rules (`calendar_first`);
  - efficiency (`parallel_search`);
  - safety (`booking_allowed`, `expected_bookings`);
  - a rubric for the final reply (`criteria`).
- **Splits.** `core` holds must-never-regress behaviors and `edge` holds tricky cases. Later, `from-production` holds cases learned from real traffic. You can run just `--split core` as a fast pre-merge gate.
- **Versions.** The dataset is tagged `baseline`, so you can always re-run against the original examples with `--as-of baseline` even after the dataset grows.
- **Deterministic mocks help here.** The mock tools always return the same data, so references like `HT-606278` or "conference talk on Dec 8–10" are stable, and trajectory matching stays meaningful.

## Stage 2: Offline experiment (`evals/02_run_offline_experiment.py`)

**Show:** The `prompt-v1-*` experiment. Sort by `booking_consent` and open a failing row.

The evaluators, in `travel_planner/evals/evaluators.py`, run from cheapest to most expensive:

| Key | Type | Checks |
|---|---|---|
| `calendar_checked_first` | code, trajectory | The calendar is checked before any flight/hotel search |
| `parallel_search` | code, trajectory | The flight and hotel searches are issued in the same turn |
| `booking_consent` | code, trajectory | Nothing is booked unless the user asked; the same booking is never repeated |
| `avoided_unneeded_subagents` | code, trajectory | No calls to subagents the task doesn't need |
| `trajectory_superset_match` | agentevals match | All required subagents ran and the **exact booking IDs** were used |
| `trajectory_accuracy` | agentevals LLM judge | Is the path a sensible one, when many paths are valid? |
| `response_quality` | openevals LLM judge | Does the final reply meet the example's rubric? |
| `all_checks_pass_rate` | summary | Share of examples passing every deterministic check (a regression gate) |

**Talk track:**
- Offline experiments are how you **compare versions before shipping**: prompts, models, tools, and architecture changes.
- Put cheap deterministic checks first. Use LLM judges for what code can't check.
- Experiment metadata records `prompt_version` and `model`, so you can filter and group by them.

## Trajectories: when to use them

**Show:** A v1 trace, expanded. Point out the coordinator's `task` calls and the subagents' `search_flights`/`book_flight` calls under them. Then show a failing `trajectory_superset_match` and the harness's flattened `trajectory` output.

**Talk track:**
- **Use trajectory evals when *how* the agent gets the answer matters, not just the answer:**
  - safety and consent: a booking made without the user asking is a failure even if the final message looks fine;
  - required ordering, such as checking availability before searching;
  - efficiency, such as parallel versus sequential delegation and no redundant subagents;
  - correct tool arguments, such as booking the exact ID the user chose.
- **Final-response evals are enough when only the outcome matters,** for example the activities plan.
- **Match evaluators vs trajectory judges.**
  - Use **match** evaluators (strict, unordered, subset, superset) when the correct path is known and deterministic. Here we use superset with `tool_args_match_overrides`, so only `subagent_type` and the booking IDs are compared.
  - Use the **LLM trajectory judge** when many paths are valid. Give it your architecture: the first version of our judge marked correct delegation as "duplicate work" until the prompt explained what a `[subagent]` step is.
- **Multi-agent tip.** A deep agent's subagent calls live in nested runs. The harness (`travel_planner/evals/harness.py`) streams with `subgraphs=True` and flattens the coordinator and subagent calls into one trajectory, so a single evaluator can see the whole system.

**Judge lessons from building this demo** (good talking points):
- **A judge needs your architecture.** The first trajectory judge graded correct delegation as "duplicate work" and read results out of order. The trajectory now nests subagent steps before each `task` result, and the prompt explains `[subagent]` steps.
- **Judge model matters.** With Haiku 4.5 as the judge, `trajectory_accuracy` scored v1 and v2 the same, 0.62. With Sonnet 5 it separates them: 0.46 vs 0.77. The judge defaults to Sonnet 5 (`EVAL_JUDGE_MODEL`), and the agent runs on Haiku.
- **Enforce the judge's output schema.** Claude sometimes omitted the `score` field under tool-calling structured output. `StrictChatAnthropic` forces native `json_schema` output.
- **Re-score without re-running the agent.** `client.evaluate("<experiment-name>", evaluators=[...])` adds new evaluators to an existing experiment. Use it when you change a judge.

## Fix and compare

**Show:** Select the v1 and v2 experiments and click **Compare**. Point to the per-metric deltas, then open one example side by side.

**Talk track:** v2's prompt (`travel_planner/prompts.py`) fixes the specific failures the evaluators found. The comparison view is the ship/no-ship decision.

## Stages 3 and 5: Production traffic and online evaluators

**Show:** `deepagent-travel-planner-prod`, then the **Threads** tab. Open a conversation from `evals/03_simulate_production_traffic.py`: an LLM-simulated user, each turn a root trace grouped by `thread_id`. Then open the **Evaluators** tab.

Scripted by `evals/05_setup_online_evaluators.py` through the run rules API:
- The code evaluators `calendar_checked_first` and `booking_consent` on every root run. These are the **same metric names** as offline.
- An automation, *Unconsented bookings → review queue*, that sends runs with `booking_consent = 0` to the annotation queue.

**Add live in the UI** (project → Evaluators → **+ Evaluator** → LLM-as-judge). The script prints both prompts:
1. **`booking_safety_judge`** (run level)
   - Filter: root runs. Sampling: 100% for the demo; say 10–20% in production.
   - Model: Claude Haiku 4.5.
   - Map `input` to the run inputs and `output` to the run outputs. Output is a boolean.
2. **`task_completion`** (Source: **Threads**)
   - It uses `{{trajectory}}`, so the judge sees tool calls too. Output is a score from 1 to 5.
   - It runs after the thread has been idle (configurable, minimum 2 minutes).

**Talk track:**
- **When to use online evaluators:** after you ship, on real traffic where there are **no reference outputs**. That means reference-free checks: safety, policy, format, task completion, and user frustration.
- Code evaluators are free and deterministic, so run them on 100% of traffic. LLM judges cost money, so sample them.
- Thread-level evaluators score the whole conversation. A single turn can look fine while the conversation fails.
- Online metrics tell you **that** something is wrong in production. Automations route those runs to the right place: a queue, a dataset, or a webhook.

## Stages 4 and 6: Annotation queue, then the dataset

**Show:** The `travel-planner-review` queue. Open a flagged run and fill in the rubric:
- `booking_safety` (safe/unsafe);
- `plan_quality` (1–5);
- `correction` (what it should have done).

Then either click **Add to Dataset** (the golden dataset is the queue's default) or run:

```sh
uv run evals/06_promote_reviewed_to_dataset.py
uv run evals/02_run_offline_experiment.py --prompt v2 --split from-production
```

`06` frames the correction as a regression rubric ("don't repeat this failure"). The failing turn is often a resumed approval rather than a user message, so a better agent may never reach that situation when the conversation is replayed.

**Talk track:**
- **When to use annotation queues:**
  - automated scores are low, uncertain, or disagree with each other;
  - a judgement needs domain expertise;
  - you're **calibrating an LLM judge** against human labels;
  - you want to turn production cases into corrected reference examples.
- Reviewers get a rubric (feedback configs) so labels are consistent and can be aggregated.
- The loop closes when the reviewer's correction becomes the rubric for a new `from-production` example. The next experiment tests v2 against the exact failure found in production, and the `after-prod-review` tag marks the new dataset version.

## Reference results (Haiku 4.5 agent, Sonnet 5 judge)

| Metric | v1 | v2 |
|---|---|---|
| `booking_consent` | 0.62 | **1.00** |
| `calendar_checked_first` | 0.60 | **0.80** |
| `parallel_search` | 0.50 | **0.75** |
| `trajectory_superset_match` | 0.90 | 0.90 |
| `trajectory_accuracy` (judge) | 0.46 | **0.77** |
| `response_quality` (judge) | 0.58 | **0.85** |

The agent isn't deterministic, so expect some movement between runs. v2 isn't perfect either (calendar ordering, parallelism), which is a natural "what would you iterate on next?" moment. 

On the `from-production` example (v1 retried a booking the user declined), v1 fails `booking_consent` and `response_quality` and v2 passes both.

## When to use what (recap slide)

| Tool | Use it when | Signal |
|---|---|---|
| **Golden dataset** | The prototype works and you can define "correct". Grow it from production failures. | Curated inputs with references, versioned and split |
| **Offline experiments** | Before every change: prompts, models, tools, architecture | Side-by-side comparison of versions |
| **Trajectory evals** | *How* the agent acts matters: safety, ordering, efficiency, tool args | Match evaluators for known paths, LLM judge for open-ended ones |
| **Online evaluators** | After shipping, on sampled real traffic with no references | Reference-free quality and safety trends, per run and per thread |
| **Automation rules** | Online signals should trigger an action | Route to a queue or dataset, or call a webhook |
| **Annotation queues** | A human needs to judge, correct, or calibrate | Rubric labels plus corrected examples |

---

## Appendix: Resetting between rehearsals

- `uv run evals/00_reset_demo.py` deletes everything the demo created in LangSmith: experiments, the dataset, the prod project with its rules and online evaluators, and the queue.
- `uv run evals/01_create_golden_dataset.py --recreate` rebuilds only the dataset. This removes `from-production` examples.
- Pass `--no-llm-judges` to `02` for a fast, cheap run while rehearsing.
