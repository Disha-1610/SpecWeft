import sqlite3

import pytest

from specweft import agreements, scanner
from specweft.diffs import analyze_diff, detect_changes, parse_unified_diff
from tests.conftest import git

DIFF_RENAME = """diff --git a/app/settings.py b/app/settings.py
--- a/app/settings.py
+++ b/app/settings.py
@@ -1,3 +1,3 @@
 import os
-PAYMENT_GATEWAY_URL = os.environ["PAYMENT_GATEWAY_URL"]
+PAYMENT_GATEWAY_URL = os.environ["PAYMENTS_API_BASE_URL"]
 ORDER_TOPIC = "orders.created.v1"
"""


def test_scan_stores_locations_and_dedups(indexed: sqlite3.Connection):
    rows = indexed.execute("SELECT r.name, f.path, o.line, o.kind, o.extractor FROM occurrences o JOIN files f ON f.id=o.file_id"
                           " JOIN repos r ON r.id=f.repo_id WHERE o.token_norm='payment_gateway_url'").fetchall()
    places = {(r[0], r[1]) for r in rows}
    assert ("backend", "deploy/k8s.yaml") in places and ("frontend", ".env") in places
    assert all(r[2] >= 1 for r in rows)
    dup = indexed.execute("SELECT file_id, token_norm, line, kind, COUNT(*) c FROM occurrences GROUP BY 1,2,3,4 HAVING c>1").fetchall()
    assert dup == []


def test_index_scores_cross_repo_contract(indexed):
    t = indexed.execute("SELECT * FROM agreement_tokens WHERE token_norm='payment_gateway_url'").fetchone()
    assert t["n_repos"] == 2 and t["n_files"] >= 8 and 0 < t["score"] <= 1
    route = indexed.execute("SELECT * FROM agreement_tokens WHERE token_norm='/api/v2/orders/{}'").fetchone()
    assert route is not None and route["n_repos"] == 2  # python route, openapi path, TS template string agree


def test_rescan_is_idempotent_and_atomic(conn, repos):
    s1 = scanner.scan_repo(conn, repos["backend"], "backend")
    s2 = scanner.scan_repo(conn, repos["backend"], "backend")
    assert s1.occurrences == s2.occurrences == conn.execute("SELECT COUNT(*) FROM occurrences").fetchone()[0]


def test_scan_records_malformed_and_skips_large(conn, repos):
    root = repos["backend"]
    (root / "bad.yaml").write_text("a: [1, 2\nb: : :", encoding="utf-8")
    (root / "huge.py").write_text("x = 1\n" * 200_000, encoding="utf-8")
    git(root, "add", "-A")
    s = scanner.scan_repo(conn, root, "backend")
    assert any(p == "bad.yaml" for p, _ in s.failures)
    assert not conn.execute("SELECT 1 FROM files WHERE path='huge.py'").fetchone()


def test_scan_missing_repo_and_rev(conn, repos, tmp_path):
    with pytest.raises(FileNotFoundError):
        scanner.scan_repo(conn, tmp_path / "nope")
    s = scanner.scan_repo(conn, repos["backend"], "backend", rev="HEAD")
    assert s.occurrences > 0


def test_parse_diff_handles_header_like_content():
    d = "diff --git a/x.sql b/x.sql\n--- a/x.sql\n+++ b/x.sql\n@@ -1,2 +1,2 @@\n--- old comment\n+-- new comment\n select 1;\n"
    fds = parse_unified_diff(d)
    assert len(fds) == 1 and [l[0] for l in fds[0].hunks[0].lines] == ["-", "+", " "]
    assert parse_unified_diff("") == [] and parse_unified_diff("garbage\n@@ nonsense") == []


def test_detect_rename_and_value_change():
    ch = {(c.norm, c.change_type): c for c in detect_changes(parse_unified_diff(DIFF_RENAME)[0])}
    assert ("payment_gateway_url", "renamed") in ch
    assert ch[("payment_gateway_url", "renamed")].renamed_to == "PAYMENTS_API_BASE_URL"
    d = "--- a/.env\n+++ b/.env\n@@ -1,2 +1,2 @@\n-ORDERS_DB_DSN=sqlite:///orders.db\n+ORDERS_DB_DSN=postgres://db/orders\n KEEP=1\n"
    ch = {(c.norm, c.change_type) for c in detect_changes(parse_unified_diff(d)[0])}
    assert ("orders_db_dsn", "value_changed") in ch


def test_detect_removed_and_deleted_file():
    d = "--- a/app/models.py\n+++ b/app/models.py\n@@ -1,3 +1,2 @@\n class CustomerOrder:\n     __tablename__ = \"customer_orders\"\n-    shipping_address_line = None\n"
    ch = {(c.norm, c.change_type) for c in detect_changes(parse_unified_diff(d)[0])}
    assert ("shipping_address_line", "removed") in ch
    d = "diff --git a/a.py b/a.py\ndeleted file mode 100644\n--- a/a.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-X = 'customer_orders_archive'\n"
    fd = parse_unified_diff(d)[0]
    assert fd.new_path is None and any(c.change_type == "removed" for c in detect_changes(fd))


def test_analyze_diff_finds_cross_repo_holders_with_both_locations(indexed):
    cands, changes = analyze_diff(indexed, DIFF_RENAME, "backend")
    by = {(c.repo, c.path): c for c in cands}
    assert ("frontend", ".env") in by and ("backend", "deploy/k8s.yaml") in by
    ev = by[("frontend", ".env")].evidence[0]
    assert ev.changed_site.path == "app/settings.py" and ev.changed_site.line == 2
    assert ev.holder_site.repo == "frontend" and ev.holder_site.line == 1
    assert ("backend", "app/settings.py") not in by  # the changed file itself is never a candidate


def test_analyze_diff_unknown_tokens_yield_nothing(indexed):
    d = "--- a/app/x.py\n+++ b/app/x.py\n@@ -1 +1 @@\n-zz_totally_unique_token_qq = 1\n+zz_other_unique_token_qq = 1\n"
    cands, _ = analyze_diff(indexed, d, "backend")
    assert cands == []
