"""Check deployed traffic routing without a server, credentials, or model calls."""

import runpy
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def traffic():
    return runpy.run_path(str(Path(__file__).parents[1] / "evals/03_generate_traffic.py"))


def test_deployed_request_uses_graph_and_keeps_thread(traffic):
    client = SimpleNamespace(threads=Mock(), runs=Mock())
    client.threads.create.return_value = {"thread_id": "thread-1"}
    client.runs.create.return_value = {"run_id": "run-1", "status": "success"}

    assert traffic["run_deployed"](client, "Plan a Paris trip") == "Plan a Paris trip"

    client.runs.create.assert_called_once_with(
        "thread-1",
        "travel_planner",
        input={"messages": [{"role": "user", "content": "Plan a Paris trip"}]},
    )


def test_deployed_request_propagates_server_failure(traffic):
    client = SimpleNamespace(threads=Mock(), runs=Mock())
    client.threads.create.return_value = {"thread_id": "thread-1"}
    client.runs.create.return_value = {"run_id": "run-1", "status": "error"}

    with pytest.raises(RuntimeError, match="run-1.*thread-1.*error"):
        traffic["run_deployed"](client, "Plan a Paris trip")


def test_remote_mode_does_not_build_local_agent(traffic, monkeypatch, capsys):
    main = traffic["main"]
    client = SimpleNamespace(threads=Mock(), runs=Mock())
    client.threads.create.return_value = {"thread_id": "thread-1"}
    client.runs.create.return_value = {"run_id": "run-1", "status": "success"}
    get_client = Mock(return_value=client)
    build_agent = Mock(side_effect=AssertionError("Remote mode must not build a local agent"))
    monkeypatch.setitem(main.__globals__, "load_dotenv", Mock())
    monkeypatch.setitem(main.__globals__, "get_sync_client", get_client)
    monkeypatch.setitem(main.__globals__, "build_agent", build_agent)
    for name in ("LANGGRAPH_API_KEY", "LANGCHAIN_API_KEY", "LANGGRAPH_HOST_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-placeholder")
    monkeypatch.setattr(
        sys, "argv", ["traffic", "--url", "https://agent.example", "--n", "2", "--concurrency", "1"]
    )

    main()

    get_client.assert_called_once_with(url="https://agent.example", api_key="test-placeholder", timeout=30)
    build_agent.assert_not_called()
    assert client.runs.create.call_count == 2
    assert "Requests completed on Agent Server" in capsys.readouterr().out


def test_invalid_request_count_fails_before_loading_credentials(traffic, monkeypatch):
    main = traffic["main"]
    load_env = Mock()
    monkeypatch.setitem(main.__globals__, "load_dotenv", load_env)
    monkeypatch.setattr(sys, "argv", ["traffic", "--n", "0"])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2
    load_env.assert_not_called()


def test_polling_waits_for_existing_run_without_resubmitting(traffic, monkeypatch):
    client = SimpleNamespace(threads=Mock(), runs=Mock())
    client.threads.create.return_value = {"thread_id": "thread-1"}
    client.runs.create.return_value = {"run_id": "run-1", "status": "pending"}
    client.runs.get.side_effect = [{"status": "running"}, {"status": "success"}]
    monkeypatch.setattr(traffic["time"], "sleep", Mock())

    traffic["run_deployed"](client, "Plan a Paris trip")

    assert client.runs.create.call_count == 1
    assert client.runs.get.call_count == 2
    client.runs.get.assert_called_with("thread-1", "run-1")


def test_polling_timeout_reports_run_ids_without_resubmitting(traffic, monkeypatch):
    client = SimpleNamespace(threads=Mock(), runs=Mock())
    client.threads.create.return_value = {"thread_id": "thread-1"}
    client.runs.create.return_value = {"run_id": "run-1", "status": "running"}
    monkeypatch.setattr(traffic["time"], "monotonic", Mock(side_effect=[0, 601]))

    with pytest.raises(TimeoutError, match="run-1.*thread-1.*may still be running"):
        traffic["run_deployed"](client, "Plan a Paris trip")

    assert client.runs.create.call_count == 1
    client.runs.get.assert_not_called()


def test_empty_dotenv_key_does_not_override_exported_credential(traffic, monkeypatch, tmp_path):
    main = traffic["main"]
    (tmp_path / ".env").write_text("LANGSMITH_API_KEY=\n")
    monkeypatch.setitem(main.__globals__, "__file__", str(tmp_path / "evals/03_generate_traffic.py"))
    for name in ("LANGGRAPH_API_KEY", "LANGCHAIN_API_KEY", "LANGGRAPH_HOST_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-placeholder")
    client = SimpleNamespace(threads=Mock(), runs=Mock())
    client.threads.create.return_value = {"thread_id": "thread-1"}
    client.runs.create.return_value = {"run_id": "run-1", "status": "success"}
    get_client = Mock(return_value=client)
    monkeypatch.setitem(main.__globals__, "get_sync_client", get_client)
    monkeypatch.setattr(sys, "argv", ["traffic", "--url", "https://agent.example", "--n", "1"])

    main()

    get_client.assert_called_once_with(url="https://agent.example", api_key="test-placeholder", timeout=30)


def test_missing_hosted_credential_fails_before_network(traffic, monkeypatch):
    main = traffic["main"]
    for name in ("LANGGRAPH_API_KEY", "LANGSMITH_API_KEY", "LANGCHAIN_API_KEY", "LANGGRAPH_HOST_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setitem(main.__globals__, "load_dotenv", Mock())
    get_client = Mock()
    monkeypatch.setitem(main.__globals__, "get_sync_client", get_client)
    monkeypatch.setattr(sys, "argv", ["traffic", "--url", "https://agent.example", "--n", "1"])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2
    get_client.assert_not_called()
