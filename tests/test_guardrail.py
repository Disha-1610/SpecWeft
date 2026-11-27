"""The finish-line guardrail: same verdict for a coding agent's Stop hook and for `specweft check` on a working tree."""
from specweft import agent_demo, cli, guardrail


def test_fails_thresholds():
    assert guardrail.fails("high", "high") and guardrail.fails("high", "medium") and guardrail.fails("medium", "medium")
    assert not guardrail.fails("medium", "high") and not guardrail.fails("high", "never") and not guardrail.fails("low", "medium")


def test_agent_demo_hook_sends_agent_back_for_other_repos(tmp_path):
    rep = agent_demo.run(tmp_path / "ws", tmp_path / "a.db")
    first, second = rep["stop_hook"]["first_stop"], rep["stop_hook"]["second_stop"]
    assert first["decision"] == "block" and "platform-infra:k8s/orders-deployment.yaml" in first["reason"]
    assert "decision" not in second and "systemMessage" in second  # never blocks twice
    stale = set(rep["check"]["stale_files"])
    assert rep["check"]["verdict"] == "fail"
    assert {"checkout-web:src/api/orders.ts", "platform-infra:terraform/orders.tf"} <= stale
    assert not any(f.split(":", 1)[1] in rep["agent_edited"] for f in stale if f.startswith("orders-service:"))


def test_check_cli_exit_codes(tmp_path, capsys):
    agent_demo.run(tmp_path / "ws", tmp_path / "a.db")
    o = str(tmp_path / "ws" / "orders-service")
    assert cli.main(["--db", str(tmp_path / "a.db"), "check", "--path", o, "--fail-on", "medium"]) == 1
    assert "verdict: FAIL" in capsys.readouterr().out
    assert cli.main(["--db", str(tmp_path / "a.db"), "check", "--path", o, "--fail-on", "never"]) == 0
    # a clean tree passes
    assert cli.main(["--db", str(tmp_path / "a.db"), "check", "--path", str(tmp_path / "ws" / "checkout-web")]) == 0
