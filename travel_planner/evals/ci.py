"""Require every dataset assertion to pass and preserve an inspectable CI report."""

import json
import time
from collections import Counter
from pathlib import Path


def write_ci_report(results, examples, repetitions, experiment_url, output_dir="eval-results"):
    expected = {str(e.id): [a["key"] for a in e.outputs["assertions"]] for e in examples}
    seen = Counter()
    checks = []
    failed_run_ids = set()
    for row in results:
        example_id = str(row["example"].id)
        seen[example_id] += 1
        run = row["run"]
        scores = row["evaluation_results"]["results"]
        for key in expected[example_id]:
            matches = [score for score in scores if score.key == key]
            passed = not run.error and len(matches) == 1 and matches[0].score == 1
            comment = matches[0].comment if len(matches) == 1 else "Missing or duplicate assertion score"
            checks.append({"example_id": example_id, "run_id": str(run.id), "key": key,
                           "passed": bool(passed), "comment": run.error or comment})
            if not passed:
                failed_run_ids.add(str(run.id))
    coverage = bool(expected) and all(keys and seen[eid] == repetitions for eid, keys in expected.items())
    report = {
        "experiment_name": results.experiment_name, "experiment_url": experiment_url,
        "passed": coverage and bool(checks) and all(c["passed"] for c in checks),
        "coverage_complete": coverage, "checks": checks,
        "failed_run_ids": sorted(failed_run_ids),
    }
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / "report.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    lines = ["## Golden assertion evaluation", "",
             f"**{'PASSED' if report['passed'] else 'FAILED'}** — {sum(c['passed'] for c in checks)}/{len(checks)} assertions passed.",
             "", f"[Open LangSmith experiment]({experiment_url})", ""]
    if not coverage:
        lines.append("Incomplete evaluation: expected a result and nonempty assertion list for every example/repetition.")
    for check in checks:
        if not check["passed"]:
            reason = str(check["comment"] or "Assertion failed").replace("\n", " ")
            lines.append(f"- `{check['key']}` — example `{check['example_id']}`: {reason}")
    (path / "report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return report


def queue_failures(client, name, run_ids):
    client.flush()
    # Queue insertion needs runs to have finished asynchronous ingestion.
    deadline = time.monotonic() + 30
    while True:
        try:
            for run_id in run_ids:
                client.read_run(run_id)
            break
        except Exception:
            if time.monotonic() >= deadline:
                raise
            time.sleep(2)
    queues = list(client.list_annotation_queues(name=name, limit=1))
    queue = queues[0] if queues else client.create_annotation_queue(name=name)
    client.add_runs_to_annotation_queue(queue_id=queue.id, run_ids=run_ids)
