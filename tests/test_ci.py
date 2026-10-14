from types import SimpleNamespace as NS

from travel_planner.evals.ci import write_ci_report


class Results(list):
    experiment_name = "test-ci"


def example():
    return NS(id="example", outputs={"assertions": [{"key": "details"}, {"key": "codes"}]})


def row(scores=(1, 1), error=None):
    return {"example": example(), "run": NS(id="run", error=error),
            "evaluation_results": {"results": [NS(key=k, score=s, comment="evidence")
                for k, s in zip(("details", "codes"), scores)]}}


def report(tmp_path, rows, repetitions=1):
    return write_ci_report(Results(rows), [example()], repetitions, "https://smith.langchain.com", tmp_path)


def test_all_assertions_pass(tmp_path):
    result = report(tmp_path, [row()])
    assert result["passed"]
    assert (tmp_path / "report.json").exists()
    assert "PASSED" in (tmp_path / "report.md").read_text()


def test_one_failure_is_not_hidden_by_other_scores(tmp_path):
    result = report(tmp_path, [row((1, 0))])
    assert not result["passed"]
    assert result["failed_run_ids"] == ["run"]
    assert "codes" in (tmp_path / "report.md").read_text()


def test_missing_score_fails(tmp_path):
    assert not report(tmp_path, [row((1,))])["passed"]


def test_none_score_fails(tmp_path):
    assert not report(tmp_path, [row((1, None))])["passed"]


def test_target_error_fails_even_with_passing_scores(tmp_path):
    assert not report(tmp_path, [row(error="target failed")])["passed"]


def test_missing_repetition_fails(tmp_path):
    assert not report(tmp_path, [row()], repetitions=2)["passed"]


def test_no_results_fails(tmp_path):
    assert not report(tmp_path, [])["passed"]


def test_duplicate_score_fails(tmp_path):
    result = row()
    result["evaluation_results"]["results"].append(NS(key="codes", score=1, comment="duplicate"))
    assert not report(tmp_path, [result])["passed"]


def test_optional_feedback_does_not_change_gate(tmp_path):
    result = row()
    result["evaluation_results"]["results"].append(NS(key="correctness", score=0, comment="optional"))
    assert report(tmp_path, [result])["passed"]


def test_long_error_is_shortened_in_markdown_but_preserved_in_json(tmp_path):
    import json
    error = "Model error: " + "x" * 70000
    result = report(tmp_path, [row(error=error)])
    assert not result["passed"]
    markdown = (tmp_path / "report.md").read_text()
    assert len(markdown) < 4000
    assert "Open LangSmith experiment" in markdown
    assert "full details in report.json" in markdown
    stored = json.loads((tmp_path / "report.json").read_text())
    assert stored["checks"][0]["comment"] == error


def test_chart_shows_per_assertion_rates(tmp_path):
    result = report(tmp_path, [row(), row((1, 0))], repetitions=2)
    text = (tmp_path / "report.md").read_text()
    assert not result["passed"]
    assert "[####################]  2/2  100%" in text
    assert "[##########..........]  1/2   50%" in text
    assert "Failed assertions: 1 · Affected runs: 1" in text
    assert "Open LangSmith experiment" in text


def test_empty_results_do_not_show_a_successful_chart(tmp_path):
    result = report(tmp_path, [])
    text = (tmp_path / "report.md").read_text()
    assert not result["passed"]
    assert "Assertion pass rates" not in text
    assert "Incomplete evaluation" in text
