"""The cross-repo headline: a PR in one repo flags holders in other repos, which co-change and CODEOWNERS can't."""
from specweft import crossrepo_demo


def test_pr_in_one_repo_flags_files_in_other_repos(tmp_path):
    rep = crossrepo_demo.run(tmp_path / "ws", tmp_path / "x.db")
    cross = set(rep["specweft"]["cross_repo_files"])
    assert {"checkout-web:src/api/orders.ts", "checkout-web:src/components/OrderSummary.tsx",
            "platform-infra:k8s/orders-deployment.yaml", "platform-infra:terraform/orders.tf"} <= cross
    # baselines are structurally blind across repos
    assert all(":" not in f for f in rep["git_cochange"]["files"])
    assert rep["codeowners"]["reviewers_requested"] == ["@acme/api-guild", "@acme/orders-team"]
    assert rep["codeowners"]["owners_of_broken_files_not_requested"] == ["@acme/checkout-team", "@acme/platform-team"]
    ev = next(f for f in rep["specweft"]["flagged"] if f["path"] == "src/api/orders.ts")["evidence"][0]
    assert ev["renamed_to"] == "shipping_address" and ev["changed_at"].startswith("orders-service:api/openapi.yaml")
