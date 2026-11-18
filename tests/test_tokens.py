from specweft.tokens import normalize, normalize_template, rarity, specificity, spread


def test_case_and_separator_folding():
    forms = ["userId", "user_id", "USER_ID", "user-id", "UserId"]
    assert {normalize(f).norm for f in forms} == {"user_id"}


def test_version_suffix_identifier_and_path():
    t = normalize("orders_v2")
    assert (t.norm, t.base, t.version) == ("orders_v2", "orders", "v2")
    t = normalize("OrderServiceV3")
    assert (t.base, t.version) == ("order_service", "v3")
    p = normalize("/api/v1/orders")
    assert p.is_path and p.version == "v1" and p.base == "/api/orders"


def test_template_normalization_agrees_across_styles():
    forms = ["/users/{id}", "/users/:id", "/users/${userId}", "/users/<int:id>", "/users/{user_id}"]
    assert {normalize(f).norm for f in forms} == {"/users/{}"}
    assert normalize_template("ord-%s-%(x)d") == "ord-{}-{}"


def test_dotted_topic_keeps_structure():
    assert normalize("orders.created.v1").norm == "orders.created.v1"


def test_stoplist_and_rejections():
    for junk in ["name", "id", "true", "", "   ", "a b c", "x" * 500, "12", "/{}"]:
        t = normalize(junk)
        assert t is None or specificity(t) == 0
    assert specificity(normalize("PAYMENT_GATEWAY_URL")) > specificity(normalize("gateway"))


def test_scores_bounds():
    assert rarity(1, 1000) > rarity(500, 1000) >= 0
    assert spread(1, 1) == 0 and 0 < spread(2, 1) < spread(2, 2) <= 1
