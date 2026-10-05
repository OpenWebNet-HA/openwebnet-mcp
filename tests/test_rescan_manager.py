"""Tests for RescanManager."""

import pytest
from openwebnet_mcp.ast_indexer import AstIndexer
from openwebnet_mcp.doc_indexer import DocIndexer
from openwebnet_mcp.firmware_oracle import FirmwareOracle
from openwebnet_mcp.kb import MachineKB
from openwebnet_mcp.rescan_manager import RescanManager
from openwebnet_mcp.who_catalog import WhoCatalog


def test_rescan_manager_execution():
    cat = WhoCatalog()
    doc_idx = DocIndexer()
    ast_idx = AstIndexer()
    kb = MachineKB()
    oracle = FirmwareOracle()

    manager = RescanManager(cat, doc_idx, ast_idx, kb=kb, oracle=oracle)
    res = manager.rescan()

    assert res["status"] == "success"
    assert res["who_families_loaded"] >= 20
    assert res["doc_sections"]["after"] > 0
    assert res["ast_symbols"]["after"] > 0
    assert "oracle" in res
    assert res["oracle"]["loaded"] is True
    assert res["oracle"]["verdicts"] > 0
