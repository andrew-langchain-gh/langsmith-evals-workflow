"""Verify reset targeting without deleting any remote resources."""
import runpy
from pathlib import Path
from types import SimpleNamespace as NS


def reset_script(monkeypatch, answer="y"):
    module = runpy.run_path(str(Path(__file__).resolve().parents[1] / "evals/00_reset_demo.py"))
    project = NS(id="project-id", name="local-project")
    deleted = []
    selected = []
    client = NS(
        has_dataset=lambda **kwargs: False,
        read_project=lambda **kwargs: (selected.append(kwargs) or project),
        list_projects=lambda **kwargs: [project],
        list_annotation_queues=lambda **kwargs: [],
        delete_project=lambda **kwargs: deleted.append(kwargs["project_id"]),
    )
    g = module["main"].__globals__
    monkeypatch.setitem(g, "Client", lambda: client)
    monkeypatch.setitem(g, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setitem(g, "rules_for", lambda *args, **kwargs: [])
    monkeypatch.setitem(g, "delete_rules", lambda *args: None)
    monkeypatch.setenv("LANGSMITH_PROJECT", "local-project")
    monkeypatch.setattr("builtins.input", lambda prompt: answer)
    monkeypatch.setattr("sys.argv", ["reset", "--project-id", "project-id", "--include-dev-project"])
    return module["main"], deleted, selected


def test_explicit_project_is_deleted_once_even_when_also_dev(monkeypatch):
    main, deleted, selected = reset_script(monkeypatch)
    main()
    assert selected == [{"project_id": "project-id"}]
    assert deleted == ["project-id"]


def test_declining_reset_deletes_nothing(monkeypatch):
    main, deleted, _ = reset_script(monkeypatch, answer="n")
    main()
    assert deleted == []
