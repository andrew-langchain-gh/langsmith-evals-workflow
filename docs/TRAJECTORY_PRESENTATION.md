# Coordinator trajectory presentation

Updated October 13, 2026. The implemented demo compares coordinator delegation;
detailed specialist tool execution is deferred.

## Review in the UI, import through the SDK

Review root run `01a117a2-46e8-7861-8705-70b44fead800` in the UI, then run:

```sh
uv run evals/04_import_trajectory_example.py \
  --run-id 01a117a2-46e8-7861-8705-70b44fead800 \
  --dataset 503aa3e3-c21c-4562-bb6c-bccb5f33d3ee
```

The importer copies `run.inputs` and `run.outputs` directly and records
`source_run_id`. The current dataset is `travel-planner-trajectories`.
If importing from the UI, check that replay inputs contain only original user
messages and reference outputs are populated. The SDK importer preserves this shape. Each import creates
a new example; use a reviewed, completed root run.

To import all completed, successful root traces from the project:

```sh
uv run evals/04_import_trajectory_example.py \
  --project-id 01a136da-a562-7b6c-9640-37a603fc6c0c \
  --dataset 503aa3e3-c21c-4562-bb6c-bccb5f33d3ee
```

Project import includes traces with no coordinator calls and creates new examples
each time it runs. It skips failed and unfinished traces. Review the project
before importing all of its traces as references.

## Presentation sequence

1. Show the final answer and coordinator trace. Explain that delegation is
   visible even though specialist tools are absent from root messages.
2. Review the coordinator's delegation and import its root run with script `04`.
3. Show the matcher code and the compared argument fields.
4. Run against the live dataset, then inspect the experiment's actual scores
   and trace.

Tokyo's relevant assistant batches are:

| Batch | Calls | Purpose in this reference |
|---|---|---|
| 1 | flight-booker + hotel-booker | Search |
| 2 | flight-booker + hotel-booker | Book |
| 3 | activity-planner | Plan activities |
| 4 | write_file, `/itinerary.md` | Save itinerary |

Calls inside one batch can run in parallel. Their list position does not prove
execution order.

## Matching policy

`coordinator_trajectory()` keeps assistant batches with `task` and `write_file`
calls. It omits prose, tool results, planning calls, and messages with no relevant
calls. The full original messages remain in the experiment output for inspection.

`create_trajectory_match_evaluator()` compares:

- `task`: exact `subagent_type`.
- `write_file`: exact `file_path`.
- **Strict:** same relevant batches in the same order, with the same calls in
  each batch; calls within a batch can reorder in AgentEvals 0.0.9.
- **Unordered:** same call inventory, regardless of batch order.

This detects missing, extra, or incorrect specialist calls and a changed
itinerary destination. It does not grade delegation descriptions, selected IDs,
itinerary contents, tool results, or specialist execution. Because search and
booking use the same specialists, matching their names does not establish
search-before-booking semantics. A valid alternative delegation strategy may
fail strict matching; inspect the trace before calling that a regression.

## Commands

```sh
# Real agent execution, scored by SDK evaluators
uv run evals/05_run_trajectory_experiment.py --concurrency 1
```

The runner keeps its target and grading wrapper inside `main()` and passes
`evaluators=[grade_trajectory]` to `Client.evaluate()`. No UI evaluator binding
or trajectory API extraction is needed for this stage.

## Verified live experiment

The October 7 experiment
[`travel-planner-trajectories-6a96d373`](https://smith.langchain.com/o/ff74f6b5-f214-4385-bf4f-60fd0d94da58/datasets/33d3aa68-1d4a-4798-a22b-71957257966d/compare?selectedSessions=9de54291-dee7-4ef3-b300-7111e5960d2a)
completed with strict **false** and unordered **true**. The agent called flight
and hotel specialists in two batches, then the activity planner in a separate
third batch, then wrote `/itinerary.md`. The call inventory matched the reference;
the batch structure differed. This illustrates why a strict failure needs trace
review. One example without reference outputs was skipped.

## Later extension

Specialist search/booking trajectories, returned-ID membership, execution timing,
and booking coverage require additional evidence and evaluators. They remain
outside the current coordinator presentation.

Reference: https://docs.langchain.com/oss/python/langchain/test/evals#trajectory-match-evaluator
