"""Tests for RescanManager."""

import pytest
from openwebnet_mcp.ast_indexer import AstIndexer
from openwebnet_mcp.doc_indexer import DocIndexer
from openwebnet_mcp.rescan_manager import RescanManager
from openwebnet_mcp.who_catalog import WhoCatalog


def test_rescan_manager_execution():
    cat = WhoCatalog()
    doc_idx = DocIndexer()
    ast_idx = AstIndexer()

    manager = RescanManager(cat, doc_idx, ast_idx)
    res = manager.rescan()

    assert res["status"] == "success"
    assert res["who_families_loaded"] >= 20
    assert res["doc_sections"]["after"] > 0
    assert res["ast_symbols"]["after"] > 0
