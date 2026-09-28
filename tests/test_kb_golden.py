"""Quality gate: the golden set (ground truth from Encyclopedia#32) must keep meeting its thresholds.

Needs a real Machine KB (OPENWEBNET_KB_PATH, the kb_fetch cache or a sibling checkout); skipped otherwise.
"""

import pytest

import kb_eval
from openwebnet_mcp import kb as kbmod
from openwebnet_mcp.kb import MachineKB


@pytest.fixture(scope="module")
def real_kb():
    kb = MachineKB()
    if not kb.load():
        pytest.skip(f"no Machine KB available: {kb.load_error}")
    return kb


def test_golden_thresholds(real_kb):
    res = kb_eval.evaluate(real_kb)
    print("\n" + kb_eval.report(res))
    for key, minimum in res["thresholds"].items():
        assert res[key] >= minimum, f"{key} {res[key]:.2f} < {minimum}\n{kb_eval.report(res)}"
    assert not res["fixed"], f"known misses now pass; drop known_miss for {res['fixed']}"


def test_exact_reference_boost_never_lowers_recall(real_kb, monkeypatch):
    with_boost = kb_eval.evaluate(real_kb)
    monkeypatch.setattr(kbmod, "_REF_BOOST", 0.0)
    without = kb_eval.evaluate(real_kb)
    assert with_boost["recall_at_5"] >= without["recall_at_5"]
    assert with_boost["recall_at_1"] >= without["recall_at_1"]


def test_golden_answers_exist_in_the_corpus(real_kb):
    """Every golden case must be answerable: a matching record exists, so a MISS is a ranking miss, not bad data."""
    records = list(real_kb.chunks.values()) + list(real_kb.claims.values())
    for case in kb_eval.load_golden()["cases"]:
        assert any(kb_eval.is_correct(r, case) for r in records), f"{case['id']}: no matching record in the KB"
