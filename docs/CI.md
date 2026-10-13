# Step 6: Gate pull requests with offline assertions

Repository: https://github.com/andrew-langchain-gh/langsmith-evals-workflow

The workflow runs the PR code locally against the existing LangSmith golden dataset.
It reuses `02_run_experiment.py` and its assertion judge, rather than calling the
hosted deployment. Every expected assertion must score 1; missing scores, run
errors, and incomplete example/repetition coverage fail the check. Optional
UI-bound metrics do not change this gate. The report uses the same decision as
CI, never an average that could hide a failing example.

## GitHub setup

1. Under Settings → Secrets and variables → Actions, add repository secrets
   `LANGSMITH_API_KEY` and `ANTHROPIC_API_KEY`. These configure the SDK and models;
   local credentials and LangSmith workspace UI secrets do not configure GitHub.
2. Set `LANGSMITH_WORKSPACE_ID` as an Actions variable if your key needs a workspace.
   Optionally set `EVAL_DATASET_NAME`; default: `travel-planner-golden`.
3. Ensure the golden dataset exists in that workspace. CI does not recreate it.
4. Run **Golden assertion evaluation** manually once to verify access.
5. In Settings → Rules → Rulesets (or branch protection), require **Golden assertions**
   for `main`. A failed check only blocks merging once this rule is enabled.

The workflow uses `pull_request`, not `pull_request_target`. Fork PRs receive no
repository secrets and fail with an explicit configuration message; rehearse with
branches inside this repository. Model calls are live and may vary: review judge
reasoning and repeat experiments before interpreting a single failure as a regression.
The initial gate requires all five assertions on all five examples to pass.
Dataset edits change the benchmark; keep it fixed while comparing PRs.

## Rehearse the presentation

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
they do not post a PR comment. Configure the repository secrets first, as described above.

### Demonstrate a failing gate

1. Establish a passing baseline with a manual run.
2. Open a PR whose coordinator prompt omits confirmation codes from the final answer.
3. Show **Golden assertions** failing and the PR comment identifying
   `must_report_confirmation_codes` with judge evidence and an experiment link.
4. Open the LangSmith experiment, then the failed runs in `travel-planner-review`.
5. Fix the prompt and push another commit. Show the new passing check and the
   required-check merge rule.

Talk track: “The evaluator we used interactively now checks each proposed change
before it ships.” This is a CI gate; it does not automatically deploy the agent.

## Local command

```sh
uv run python evals/02_run_experiment.py --ci
# Also route failed runs for review:
uv run python evals/02_run_experiment.py --ci --annotation-queue travel-planner-review
```

`eval-results/report.json` and `report.md` are written before the quality-gate exit.
The JSON stores individual decisions, failed run IDs, and the actual experiment
name. GitHub publishes the Markdown as a job summary and an updated PR comment.
The report job has write permissions; evaluation has only read permissions.
Experiment metadata records the PR number, head commit SHA, and GitHub run ID.

Based on https://github.com/langchain-samples/ci-evals-failure-aq.
