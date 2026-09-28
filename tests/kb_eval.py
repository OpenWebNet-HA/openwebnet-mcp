"""Retrieval-quality harness for the Machine KB (golden set in tests/golden/kb_golden.json).

Run as a report:  python tests/kb_eval.py [--boost-off]
Gated by tests/test_kb_golden.py (needs a KB via OPENWEBNET_KB_PATH, the kb_fetch cache or a sibling checkout).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from openwebnet_mcp import kb as kbmod
from openwebnet_mcp.kb import NON_ESTABLISHED, MachineKB
from openwebnet_mcp.kb_format import format_record

GOLDEN = Path(__file__).parent / "golden" / "kb_golden.json"
DEPTH = 10


def load_golden() -> dict[str, Any]:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def record_path(rec: dict[str, Any]) -> str:
    if rec.get("source_path"):
        return rec["source_path"]
    prov = rec.get("provenance") or [{}]
    return (prov[0] if isinstance(prov, list) else prov).get("location", {}).get("path", "")


def record_text(rec: dict[str, Any]) -> str:
    return rec.get("text") or rec.get("statement") or ""


def is_correct(rec: dict[str, Any], case: dict[str, Any]) -> bool:
    return record_path(rec).endswith(case["path"]) and bool(re.search(case["text"], record_text(rec), re.I))


def first_correct_rank(kb: MachineKB, case: dict[str, Any]) -> int | None:
    for rank, hit in enumerate(kb.search(case["query"], limit=DEPTH), 1):
        rec = kb.get(hit["id"])
        if rec and is_correct(rec, case):
            return rank
    return None


def fidelity_failures(kb: MachineKB, query: str, k: int = 5) -> list[str]:
    """Qualifiers the search output must keep for each of the top-k hits."""
    bad = []
    for hit in kb.search(query, limit=k):
        rec = kb.get(hit["id"])
        out = format_record(rec, kb, detail=False)
        if rec["kind"] == "claim":
            status = rec.get("epistemic_status", "?")
            if f"`{status}`" not in out or "Applicability" not in out or "Provenance" not in out:
                bad.append(f"{rec['id']}: status/applicability/provenance missing")
            if status in NON_ESTABLISHED and NON_ESTABLISHED[status] not in out:
                bad.append(f"{rec['id']}: non-established status {status} lacks its explanation")
            if kbmod.clean_statement(rec.get("statement", ""))[1] and "truncated" not in out:
                bad.append(f"{rec['id']}: degraded statement without the truncation note")
            for cid in rec.get("cautions", []):
                if cid not in out:
                    bad.append(f"{rec['id']}: caution {cid} not shown")
        else:
            cues = rec.get("qualification_cues", {})
            for name in ("uncertainty_cues", "caution_cues", "applicability_cues"):
                for cue in cues.get(name, []):
                    if cue not in out:
                        bad.append(f"{rec['id']}: {name} '{cue}' not shown")
    return bad


def abstention_failures(kb: MachineKB, case: dict[str, Any], k: int = 5) -> list[str]:
    """Hits that appear to answer a question the corpus cannot answer."""
    bad = []
    for hit in kb.search(case["query"], limit=k):
        rec = kb.get(hit["id"])
        if re.search(case["must_not"], record_text(rec) + " " + record_path(rec), re.I):
            bad.append(rec["id"])
    return bad


def evaluate(kb: MachineKB) -> dict[str, Any]:
    gold = load_golden()
    ranks = [(c, first_correct_rank(kb, c)) for c in gold["cases"]]
    rows = [(c, r) for c, r in ranks if not c.get("known_miss")]
    known = [(c, r) for c, r in ranks if c.get("known_miss")]
    n = len(rows)
    fid = [(c["id"], fidelity_failures(kb, c["query"])) for c, _ in rows]
    absent = [(c["id"], abstention_failures(kb, c)) for c in gold["absent"]]
    return {
        "rows": rows,
        "known": known,
        "fixed": [c["id"] for c, r in known if r is not None and r <= 5],
        "recall_at_1": sum(1 for _, r in rows if r == 1) / n,
        "recall_at_5": sum(1 for _, r in rows if r is not None and r <= 5) / n,
        "fidelity": sum(1 for _, f in fid if not f) / n,
        "fidelity_failures": [x for _, f in fid for x in f],
        "abstain": sum(1 for _, b in absent if not b) / len(absent),
        "absent": absent,
        "thresholds": gold["thresholds"],
    }


def report(res: dict[str, Any]) -> str:
    lines = ["| case | first correct rank |", "|---|---|"]
    lines += [f"| {c['id']} | {r if r else 'MISS (>' + str(DEPTH) + ')'} |" for c, r in res["rows"]]
    lines += [f"| {c['id']} (known miss) | {r if r else 'MISS (>' + str(DEPTH) + ')'} |" for c, r in res["known"]]
    lines += [f"FIXED, drop known_miss from the golden set: {name}" for name in res["fixed"]]
    t = res["thresholds"]
    for key in ("recall_at_1", "recall_at_5", "fidelity", "abstain"):
        mark = "ok" if res[key] >= t[key] else "FAIL"
        lines.append(f"{key}: {res[key]:.2f} (min {t[key]}) {mark}")
    for name, hits in res["absent"]:
        if hits:
            lines.append(f"abstention failure {name}: {', '.join(hits)}")
    lines += res["fidelity_failures"][:10]
    return "\n".join(lines)


def main() -> int:
    kb = MachineKB()
    if not kb.load():
        print(kb.load_error)
        return 2
    if "--boost-off" in sys.argv:
        kbmod._REF_BOOST = 0.0
    res = evaluate(kb)
    print(report(res))
    t = res["thresholds"]
    return 0 if all(res[k] >= t[k] for k in t) and not res["fixed"] else 1


if __name__ == "__main__":
    sys.exit(main())
