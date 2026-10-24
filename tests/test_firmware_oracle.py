"""Unit tests for FirmwareOracle loader, normalization, verdict formatting, and status."""

import hashlib
import json

from openwebnet_mcp.firmware_oracle import FirmwareOracle, normalize_frame


def test_normalize_frame():
    assert normalize_frame("*1*1*12##") == "*1*1*12##"
    assert normalize_frame("1*1*12") == "*1*1*12##"
    assert normalize_frame("1*1*12##") == "*1*1*12##"
    assert normalize_frame("*1*1*12") == "*1*1*12##"
    assert normalize_frame("  *1*1*12## \n") == "*1*1*12##"
    assert normalize_frame("") == ""


def test_oracle_init_defaults():
    oracle = FirmwareOracle()
    assert oracle.loaded is False
    assert oracle.load_error is None
    assert oracle.generator is None
    assert oracle.total_unique_inputs == 0
    assert oracle.verdicts == {}
    assert oracle.gateways == []
    assert oracle.source_tier == "none"
    assert oracle.hash_verified is None


def test_oracle_load_default():
    oracle = FirmwareOracle()
    success = oracle.load()
    assert success is True
    assert oracle.loaded is True
    assert oracle.load_error is None
    assert oracle.total_unique_inputs > 0
    assert len(oracle.verdicts) > 0
    assert len(oracle.gateways) >= 2
    assert oracle.generator == "own-firmware-oracle"
    assert oracle.source_tier in ("bundled", "sibling")
    assert oracle.verdicts_sha256 is not None
    assert oracle.hash_verified is True
    assert oracle.computed_sha256 == oracle.verdicts_sha256


def test_oracle_lookup_and_normalization():
    oracle = FirmwareOracle()
    oracle.load()

    # Known frame in index
    v1 = oracle.lookup("*#1*74##")
    assert v1 is not None
    assert len(v1) >= 1
    assert any(p["product"] in ("MH200N", "MyHomeServer1", "F454") for p in v1)

    # Unnormalized / stripped lookup
    v2 = oracle.lookup("  #1*74  ")
    assert v2 == v1

    # Missing frame
    v_missing = oracle.lookup("*999*999*999##")
    assert v_missing is None


def test_format_verdict_markdown_unverified():
    oracle = FirmwareOracle()
    oracle.load()
    md = oracle.format_verdict_markdown("*999*999##", None)
    assert "Empirical Firmware Oracle Verification" in md
    assert "has not yet been replayed" in md
    assert "028206" in md
    assert "010108" in md
    assert "*999*999##" in md

    # Also with empty list
    md_empty = oracle.format_verdict_markdown("*999*999##", [])
    assert "has not yet been replayed" in md_empty


def test_format_verdict_markdown_load_failed(tmp_path):
    missing_file = tmp_path / "nonexistent.json"
    oracle = FirmwareOracle(index_path=missing_file)
    oracle.load()
    md = oracle.format_verdict_markdown("*1*1*1##", None)
    assert "Empirical Firmware Oracle Verification" in md
    assert "Oracle index unavailable:" in md


def test_format_verdict_markdown_various_verdicts():
    oracle = FirmwareOracle()
    oracle.load()
    sample_verdicts = [
        {
            "product": "MH200N",
            "version": "010108",
            "reply": "ack",
            "verdict": "out",
            "bus_frames": ["12 34 56 0d"],
            "emitted_own": ["*#*1##"],
            "suite": "suite_lighting",
            "target_sha256": "abcdef0123456789abcdef0123456789abcdef01",
            "source_tsv": "results/MH200N/010108/oracle/lighting.tsv",
        },
        {
            "product": "MyHomeServer1",
            "version": "028206",
            "reply": "nack",
            "verdict": "silent",
            "bus_frames": [],
            "emitted_own": [],
            "suite": "suite_climate",
            "target_sha256": None,
            "source_tsv": "",
        },
        {
            "product": "MH200N",
            "version": "010108",
            "reply": "-",
            "verdict": "out",
            "bus_frames": ["AA BB CC"],
            "emitted_own": [],
            "suite": "suite_no_reply",
            "target_sha256": "",
            "source_tsv": "",
        },
        {
            "product": "MH200N",
            "version": "010108",
            "reply": "silent",
            "verdict": "silent",
            "bus_frames": [],
            "emitted_own": [],
            "suite": "suite_silent",
            "target_sha256": "",
            "source_tsv": "",
        },
        {
            "product": "MH200N",
            "version": "010108",
            "reply": "custom_response",
            "verdict": "custom",
            "bus_frames": ["AA BB CC", "DD EE FF"],
            "emitted_own": ["*1*1*1##"],
            "suite": "suite_custom",
            "target_sha256": "1234567890abcdef",
            "source_tsv": "results/test.tsv",
        },
    ]

    md = oracle.format_verdict_markdown("1*1*12", sample_verdicts)
    assert "*(Matched normalized frame `*1*1*12##`)*" in md
    assert "| Gateway | Firmware | Reply | Verdict | Bus Frames Emitted | Emitted OWN | Suite | Target SHA |" in md
    assert "**MH200N**" in md
    assert "`010108`" in md
    assert "`028206`" in md
    assert "`ACK (*#*1##)`" in md
    assert "`NACK (*#*0##)`" in md
    assert "*No client reply*" in md
    assert "`SILENT`" in md
    assert "`custom_response`" in md
    assert "`OUT (Bus)`" in md
    assert "`SILENT (Drop)`" in md
    assert "Gateway recorded no client session reply." in md
    assert "Dispatched 1 SCS bus telegram(s)" in md
    assert "Dispatched 2 SCS bus telegram(s)" in md
    assert "Frame consumed or dropped internally" in md
    assert "Gateway acknowledged the command (`*#*1##`)." in md
    assert "Gateway refused the frame (`*#*0##`); nothing reached the bus." in md
    assert "Gateway was silent on the client session." in md
    assert "Gateway returned: `custom_response`." in md
    assert "Provenance: suite `suite_lighting`" in md
    assert "SHA-256: verified" in md



def test_oracle_hash_mismatch(tmp_path, caplog):
    # Create an index with a forged hash
    tampered_index = tmp_path / "tampered_index.json"
    data = {
        "generator": "own-firmware-oracle",
        "format_version": "1.0.0",
        "schema_version": "1.0.0",
        "verdicts_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
        "total_unique_inputs": 1,
        "gateways": [{"product": "MH200N", "version": "010108"}],
        "verdicts": {"*1*1*12##": [{"product": "MH200N", "version": "010108", "reply": "ack"}]},
    }
    tampered_index.write_text(json.dumps(data), encoding="utf-8")

    oracle = FirmwareOracle(index_path=tampered_index)
    assert oracle.load() is True
    assert oracle.loaded is True
    assert oracle.hash_verified is False
    assert "Oracle index hash mismatch" in caplog.text

    md = oracle.format_verdict_markdown("*1*1*12##", oracle.lookup("*1*1*12##"))
    assert "SHA-256: MISMATCH" in md



def test_oracle_format_version_warning(tmp_path, caplog):
    future_index = tmp_path / "future_index.json"
    data = {
        "generator": "own-firmware-oracle",
        "format_version": "2.0.0",
        "schema_version": "2.0.0",
        "total_unique_inputs": 0,
        "gateways": [],
        "verdicts": {},
    }
    future_index.write_text(json.dumps(data), encoding="utf-8")

    oracle = FirmwareOracle(index_path=future_index)
    assert oracle.load() is True
    assert "Unexpected oracle index format_version '2.0.0'" in caplog.text


def test_oracle_status():
    oracle = FirmwareOracle()
    st = oracle.status()
    assert st["loaded"] is True
    assert st["generator"] == "own-firmware-oracle"
    assert st["source_tier"] in ("bundled", "sibling")
    assert st["total_unique_inputs"] > 0
    assert st["total_verdicts"] > 0
    assert st["verdicts_sha256"] is not None
    assert st["hash_verified"] is True
    assert len(st["gateways"]) >= 2
    assert "suites_count" in st["gateways"][0]
    assert st["load_error"] is None


def test_oracle_reload():
    oracle = FirmwareOracle()
    assert oracle.load() is True
    assert oracle.reload() is True
    assert oracle.loaded is True


def test_oracle_missing_file(tmp_path):
    missing_file = tmp_path / "nonexistent_index.json"
    oracle = FirmwareOracle(index_path=missing_file)
    assert oracle.load() is False
    assert oracle.loaded is False
    assert "not found" in oracle.load_error
    assert oracle.lookup("*1*1*12##") is None


def test_oracle_corrupt_file(tmp_path):
    corrupt_file = tmp_path / "corrupt_index.json"
    corrupt_file.write_text("{invalid json", encoding="utf-8")
    oracle = FirmwareOracle(index_path=corrupt_file)
    assert oracle.load() is False
    assert oracle.loaded is False
    assert "Failed to parse oracle index" in oracle.load_error
    assert oracle.lookup("*1*1*12##") is None


def test_lookup_with_fallback_and_preflight():
    oracle = FirmwareOracle()
    oracle.load()

    # Exact hit returns matched_template=None
    v_exact, tpl_exact = oracle.lookup_with_fallback("*#1*74##")
    assert v_exact is not None
    assert tpl_exact is None

    # Fallback hit via canonical WHERE template (e.g. *1*1*99## -> *1*1*21## or *1*1*31##)
    v_fb, tpl_fb = oracle.lookup_with_fallback("*1*1*99##")
    assert v_fb is not None
    assert tpl_fb is not None
    assert tpl_fb.startswith("*1*1*")

    md = oracle.format_verdict_markdown("*1*1*99##", v_fb, matched_template=tpl_fb)
    assert f"*(Matched via equivalent address template `{tpl_fb}`)*" in md

    # Status request fallback (*#1*99## -> *#1*74## or *#1*21##)
    v_req, tpl_req = oracle.lookup_with_fallback("*#1*99##")
    assert v_req is not None
    assert tpl_req is not None

    # Pre-flight check on accepted frame
    pf_ok = oracle.preflight_check("*1*1*12##", gateway="MH200N")
    assert pf_ok["checked"] is True
    assert len(pf_ok["accepted_by"]) > 0

    # Pre-flight check on rejected frame (*#1*99*1## is rejected by all gateways)
    pf_rej = oracle.preflight_check("*#1*74*99##", gateway="MH200N")
    if pf_rej["checked"]:
        assert len(pf_rej["rejected_by"]) > 0
        assert len(pf_rej["warnings"]) > 0

    # Pre-flight check on split frame (*22*1*1## in sound-who22)
    pf_split = oracle.preflight_check("*22*1*1##")
    if pf_split["checked"] and pf_split["accepted_by"] and pf_split["rejected_by"]:
        assert any("Split gateway support" in w for w in pf_split["warnings"])

    # Pre-flight check on unknown frame
    pf_unk = oracle.preflight_check("*999*999*999##")
    assert pf_unk["checked"] is False

    # Group (#99), general (0 on unindexed WHO/WHAT), and compound (99#4#01) WHERE addresses
    # must NOT falsely fallback to point-to-point WHERE templates like 21
    assert oracle.lookup_with_fallback("*1*1*#99##") == (None, None)
    assert oracle.lookup_with_fallback("*1*1*99#4#01##") == (None, None)
    assert oracle.lookup_with_fallback("*#1*0*99##") == (None, None)


def test_compare_gateways(tmp_path):
    oracle = FirmwareOracle()
    oracle.load()

    # 1. Fleet summary (no arguments)
    summary = oracle.compare_gateways()
    assert "# Empirical Firmware Oracle Fleet Summary" in summary
    assert "MH200N" in summary

    # 2. Single frame comparison (with template fallback)
    comp_frame = oracle.compare_gateways(frame="*1*1*99##")
    assert "# Cross-Gateway Comparison: `*1*1*99##`" in comp_frame
    assert "Outcome Equivalence Classes" in comp_frame

    # 3. Unknown frame comparison
    comp_unk = oracle.compare_gateways(frame="*999*999##")
    assert "has not yet been replayed" in comp_unk

    # 4. Suite comparison with divergences
    comp_suite = oracle.compare_gateways(suite="sound-who22")
    assert "# Cross-Gateway Divergences in Suite `sound-who22`" in comp_suite

    # 5. Unknown suite comparison
    comp_no_suite = oracle.compare_gateways(suite="nonexistent_suite_xyz")
    assert "No indexed frames found" in comp_no_suite

    # 6. Unloaded oracle error
    bad_oracle = FirmwareOracle(index_path=tmp_path / "missing.json")
    assert "**Error**" in bad_oracle.compare_gateways()



def _index_with_reply_semantics(tmp_path):
    """A schema-1.2.0 index: F461 follows the empty-bus rule, MH200N does not."""
    verdicts = {
        "*#1*06##": [
            {"product": "F461", "version": "020011", "reply": "nack", "verdict": "out",
             "bus_frames": ["24 30 30 33 30 36 30 30 31 35 30 30 0d"], "emitted_own": [],
             "suite": "lights-area0", "source_tsv": "results/F461/020011/oracle/full/lights-area0.tsv"},
            {"product": "MH200N", "version": "010108", "reply": "ack", "verdict": "out",
             "bus_frames": ["24 30 30 33 30 36 30 30 31 35 30 30 0d"], "emitted_own": [],
             "suite": "lights-area0", "source_tsv": "results/MH200N/010108/oracle/full/lights-area0.tsv"},
        ],
        "*#4*0##": [
            {"product": "F461", "version": "020011", "reply": "nack", "verdict": "silent",
             "bus_frames": [], "emitted_own": [], "suite": "thermo-ts10", "source_tsv": ""},
            {"product": "MH200N", "version": "010108", "reply": "nack", "verdict": "out",
             "bus_frames": ["24 30 34 42 30 30 30 30 39 30 30 0d"], "emitted_own": [], "suite": "thermo-ts10", "source_tsv": ""},
        ],
    }
    canonical = json.dumps(verdicts, sort_keys=True, separators=(",", ":"))
    data = {
        "generator": "own-firmware-oracle",
        "format_version": "1.0.0",
        "schema_version": "1.2.0",
        "verdicts_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "total_unique_inputs": 2,
        "gateways": [
            {"product": "F461", "version": "020011", "status": "emulated", "suites": ["lights-area0"],
             "reply_semantics": "empty_bus_txack"},
            {"product": "MH200N", "version": "010108", "status": "emulated", "suites": ["lights-area0"],
             "reply_semantics": "pic_ack"},
            {"product": "F455", "version": "010102", "status": "catalogued", "suites": [], "reply_semantics": ""},
        ],
        "verdicts": verdicts,
    }
    path = tmp_path / "index_1_2_0.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_reply_semantics_loaded_and_exposed(tmp_path):
    oracle = FirmwareOracle(index_path=_index_with_reply_semantics(tmp_path))
    assert oracle.load() is True
    assert oracle.reply_semantics == {"F461": "empty_bus_txack", "MH200N": "pic_ack", "F455": ""}
    assert oracle.status()["reply_semantics"]["F461"] == "empty_bus_txack"


def test_reply_meaning_follows_the_empty_bus_rule(tmp_path):
    oracle = FirmwareOracle(index_path=_index_with_reply_semantics(tmp_path))
    oracle.load()
    # F461: a NACK after a bus frame is the empty-bus TX-ACK rule, not a refusal.
    assert "empty-bus rule" in oracle.reply_meaning("F461", "nack", "out")
    assert "not a refusal" in oracle.reply_meaning("F461", "nack", "out")
    # A NACK with nothing on the bus is a refusal on every gateway.
    assert oracle.reply_meaning("F461", "nack", "silent").startswith("Gateway refused the frame")
    # A pic_ack gateway's NACK + OUT is just a NACK.
    assert oracle.reply_meaning("MH200N", "nack", "out") == "Gateway answered NACK (`*#*0##`)."
    assert oracle.reply_meaning("MH200N", "ack", "out").startswith("Gateway acknowledged")
    assert oracle.reply_meaning("MH200N", "-", "out") == "Gateway recorded no client session reply."
    assert oracle.reply_meaning("MH200N", "silent", "silent") == "Gateway was silent on the client session."
    assert oracle.reply_meaning("MH200N", "weird", "out") == "Gateway returned: `weird`."


def test_format_verdict_markdown_explains_empty_bus_nack(tmp_path):
    oracle = FirmwareOracle(index_path=_index_with_reply_semantics(tmp_path))
    oracle.load()
    md = oracle.format_verdict_markdown("*#1*06##", oracle.lookup("*#1*06##"))
    assert "- **F461 (020011)**: Frame went out on the bus; the NACK is this firmware's empty-bus rule" in md
    assert "Gateway refused" not in md
    md_refused = oracle.format_verdict_markdown("*#4*0##", oracle.lookup("*#4*0##"))
    assert "- **F461 (020011)**: Gateway refused the frame (`*#*0##`); nothing reached the bus." in md_refused
    assert "- **MH200N (010108)**: Gateway answered NACK (`*#*0##`)." in md_refused


def test_compare_gateways_notes_the_empty_bus_rule(tmp_path):
    oracle = FirmwareOracle(index_path=_index_with_reply_semantics(tmp_path))
    oracle.load()
    md = oracle.compare_gateways(frame="*#1*06##")
    assert "**NACK + OUT** (1): F461" in md
    assert "`NACK + OUT` on F461 is the empty-bus rule of that firmware" in md
    assert "not a divergence" in md
    # A frame without such rows gets no note.
    md_refused = oracle.compare_gateways(frame="*#4*0##")
    assert "empty-bus rule" not in md_refused
    # The fleet summary shows each gateway's semantics.
    fleet = oracle.compare_gateways()
    assert "| Gateway | Firmware | Status | Suites Executed | Reply Semantics |" in fleet
    assert "| **F461** | `020011` | `emulated` | `1` | `empty_bus_txack` |" in fleet
    assert "| **F455** | `010102` | `catalogued` | `0` | `-` |" in fleet


def test_index_without_reply_semantics_keeps_the_plain_reading(tmp_path):
    plain = tmp_path / "index_1_1_0.json"
    plain.write_text(json.dumps({
        "generator": "own-firmware-oracle", "format_version": "1.0.0", "schema_version": "1.1.0",
        "total_unique_inputs": 1,
        "gateways": [{"product": "F461", "version": "020011", "status": "emulated", "suites": ["x"]}],
        "verdicts": {"*#1*06##": [{"product": "F461", "version": "020011", "reply": "nack", "verdict": "out",
                                   "bus_frames": ["aa"], "emitted_own": [], "suite": "x", "source_tsv": ""}]},
    }), encoding="utf-8")
    oracle = FirmwareOracle(index_path=plain)
    oracle.load()
    assert oracle.reply_semantics == {"F461": ""}
    assert oracle.reply_meaning("F461", "nack", "out") == "Gateway answered NACK (`*#*0##`)."
    assert "empty-bus rule" not in oracle.compare_gateways(frame="*#1*06##")
