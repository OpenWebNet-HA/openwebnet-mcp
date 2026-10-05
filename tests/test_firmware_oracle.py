"""Unit tests for FirmwareOracle loader, normalization, verdict formatting, and status."""

import json
from pathlib import Path
import pytest

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


def test_oracle_lookup_and_normalization():
    oracle = FirmwareOracle()
    oracle.load()

    # Known frame in index
    v1 = oracle.lookup("*#1*74##")
    assert v1 is not None
    assert len(v1) >= 1
    assert v1[0]["product"] in ("MH200N", "MyHomeServer1")

    # Unnormalized / stripped lookup
    v2 = oracle.lookup("  #1*74  ")
    assert v2 == v1

    # Missing frame
    v_missing = oracle.lookup("*999*999*999##")
    assert v_missing is None


def test_format_verdict_markdown_unverified():
    oracle = FirmwareOracle()
    md = oracle.format_verdict_markdown("*999*999##", None)
    assert "Empirical Firmware Oracle Verification" in md
    assert "has not yet been replayed" in md
    assert "*999*999##" in md

    # Also with empty list
    md_empty = oracle.format_verdict_markdown("*999*999##", [])
    assert "has not yet been replayed" in md_empty


def test_format_verdict_markdown_various_verdicts():
    oracle = FirmwareOracle()
    sample_verdicts = [
        {
            "product": "MH200N",
            "version": "010108",
            "reply": "ack",
            "verdict": "pass",
            "bus_frames": ["12 34 56 0d"],
            "emitted_own": ["*#*1##"],
            "suite": "suite_lighting",
            "target_sha256": "abcdef0123456789abcdef0123456789abcdef01",
            "source_tsv": "results/MH200N/010108/oracle/lighting.tsv",
        },
        {
            "product": "MyHomeServer1",
            "version": "2.60.26",
            "reply": "nack",
            "verdict": "reject",
            "bus_frames": [],
            "emitted_own": [],
            "suite": "suite_climate",
            "target_sha256": None,
            "source_tsv": "",
        },
        {
            "product": "MH200N",
            "version": "010108",
            "reply": "silent",
            "verdict": "drop",
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

    md = oracle.format_verdict_markdown("*1*1*12##", sample_verdicts)
    assert "| Gateway | Firmware | Reply | Verdict | Bus Frames Emitted | Emitted OWN | Suite | Target SHA |" in md
    assert "**MH200N**" in md
    assert "`010108`" in md
    assert "`ACK (*#*1##)`" in md
    assert "`NACK (*#*0##)`" in md
    assert "`SILENT`" in md
    assert "`custom_response`" in md
    assert "Dispatched 1 SCS bus telegram(s)" in md
    assert "Dispatched 2 SCS bus telegram(s)" in md
    assert "No SCS bus telegrams emitted." in md
    assert "Gateway acknowledged the command (`*#*1##`)." in md
    assert "Gateway refused/rejected the command (`*#*0##`)." in md
    assert "Gateway returned: `silent`." in md
    assert "Gateway returned: `custom_response`." in md
    assert "Provenance: suite `suite_lighting`" in md


def test_oracle_status():
    oracle = FirmwareOracle()
    st = oracle.status()
    assert st["loaded"] is True
    assert st["generator"] == "own-firmware-oracle"
    assert st["total_unique_inputs"] > 0
    assert st["total_verdicts"] > 0
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
